"""
Blog Post Deployer

Commits approved blog post MDX files and hero images to the goslated.com
GitHub repository, triggering Vercel auto-deployment (~60 seconds).

Workflow:
1. Reads approved blog posts from Google Sheets content queue
2. Commits MDX files to content/blog/ in the goslated.com repo
3. Commits hero images to public/assets/blog/ in the goslated.com repo
4. Verifies each blog post URL is live after deployment
5. Updates the Google Sheet with confirmed live URLs
6. Loads approved pins into the posting schedule
7. Appends new entries to data/content-log.jsonl
8. Sends Slack notification on completion/failure

Blog posts must be live before any pins linking to them are posted.
Content generation runs Monday; daily posting starts Tuesday.
"""

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.apis.github_api import GitHubAPI
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GENERATED_BLOG_DIR = DATA_DIR / "generated" / "blog"
GENERATED_PINS_DIR = DATA_DIR / "generated" / "pins"

# Base URL for verifying deployments
BLOG_BASE_URL = "https://goslated.com/blog"

# Deployment verification timeout
DEPLOY_VERIFY_TIMEOUT = 180  # seconds
DEPLOY_VERIFY_RETRY_DELAY = 15  # seconds between retries


class BlogDeployerError(Exception):
    """Raised when blog deployment fails."""
    pass


class BlogDeployer:
    """Deploys approved blog posts to goslated.com via GitHub."""

    def __init__(
        self,
        github: Optional[GitHubAPI] = None,
        sheets: Optional[SheetsAPI] = None,
        slack: Optional[SlackNotify] = None,
    ):
        """
        Initialize the blog deployer.

        Args:
            github: GitHubAPI instance. Creates one if not provided.
            sheets: SheetsAPI instance. Creates one if not provided.
            slack: SlackNotify instance. Creates one if not provided.
        """
        self.github = github or GitHubAPI()
        self.sheets = sheets or SheetsAPI()
        self.slack = slack or SlackNotify()

    def deploy_approved_content(self, plan_path: Optional[str] = None) -> dict:
        """
        Deploy all approved content. Main entry point.

        Steps:
        1. Read content statuses from Google Sheets Content Queue
        2. Filter to approved blog posts and pins
        3. Commit blog posts to goslated.com via GitHub
        4. Wait for Vercel deployment and verify URLs
        5. Update Google Sheet with live URLs
        6. Load approved pins into posting schedule
        7. Append entries to content-log.jsonl
        8. Send Slack notification

        Args:
            plan_path: Optional path to the plan JSON for loading pin data.

        Returns:
            dict: Deployment results with blog_deployed, pins_scheduled,
                  failures, and verification_results.
        """
        logger.info("Starting approved content deployment")

        results = {
            "blog_deployed": [],
            "blog_failed": [],
            "pins_scheduled": 0,
            "verification_results": {},
            "content_log_entries": 0,
        }

        # Step 1: Read content approvals from Google Sheets
        try:
            approvals = self.sheets.read_content_approvals()
        except Exception as e:
            logger.error("Failed to read content approvals: %s", e)
            try:
                self.slack.notify_failure(
                    "deploy_approved_content",
                    f"Cannot read content approvals from Google Sheets: {e}. "
                    f"Deployment halted. Please retry when Sheets is accessible.",
                )
            except Exception:
                pass
            raise

        # Step 2: Filter to approved blog posts
        approved_blogs = [
            item for item in approvals
            if item.get("type") == "blog"
            and item.get("status") in ("approved", "use_ai_image")
        ]

        approved_pins = [
            item for item in approvals
            if item.get("type") == "pin"
            and item.get("status") in ("approved", "use_ai_image")
        ]

        logger.info(
            "Approved content: %d blog posts, %d pins",
            len(approved_blogs), len(approved_pins),
        )

        # Step 3: Deploy blog posts
        if approved_blogs:
            deploy_result = self._deploy_blog_posts(approved_blogs)
            results["blog_deployed"] = deploy_result["deployed"]
            results["blog_failed"] = deploy_result["failed"]
        else:
            logger.info("No approved blog posts to deploy")

        # Step 4: Verify deployment URLs
        deployed_slugs = [b["slug"] for b in results["blog_deployed"]]
        if deployed_slugs:
            results["verification_results"] = self.verify_urls(
                deployed_slugs, max_wait=DEPLOY_VERIFY_TIMEOUT
            )

            # Log any verification failures
            failed_verifications = [
                slug for slug, ok in results["verification_results"].items()
                if not ok
            ]
            if failed_verifications:
                logger.warning(
                    "Some blog post URLs failed verification: %s",
                    failed_verifications,
                )
                # Retry once for failed URLs
                retry_results = self.verify_urls(failed_verifications, max_wait=60)
                results["verification_results"].update(retry_results)

                still_failed = [s for s, ok in retry_results.items() if not ok]
                if still_failed:
                    logger.error(
                        "URLs still failing after retry: %s", still_failed
                    )
                    try:
                        self.slack.notify_failure(
                            "blog_deployment",
                            f"Blog post URLs failed to resolve after retry: {still_failed}",
                        )
                    except Exception:
                        pass

        # Step 5: Update Google Sheet with live URLs
        try:
            for slug in deployed_slugs:
                if results["verification_results"].get(slug, False):
                    live_url = f"{BLOG_BASE_URL}/{slug}"
                    self.sheets.update_pin_status(
                        pin_id=slug,
                        status="deployed",
                        pinterest_pin_id=live_url,
                    )
        except Exception as e:
            logger.error("Failed to update Sheet with live URLs: %s", e)

        # Step 6: Load approved pins into the posting schedule
        if approved_pins:
            results["pins_scheduled"] = self._create_pin_schedule(
                approved_pins, plan_path
            )

        # Step 7: Append entries to content-log.jsonl
        results["content_log_entries"] = self._append_to_content_log(
            blog_results=results["blog_deployed"],
            pin_data=approved_pins,
        )

        # Step 8: Send Slack notification
        try:
            self.slack.notify_week_live(
                num_pins_scheduled=results["pins_scheduled"],
                num_blog_posts_deployed=len(results["blog_deployed"]),
            )
        except Exception as e:
            logger.error("Failed to send Slack notification: %s", e)

        logger.info(
            "Deployment complete: %d blog posts deployed, %d pins scheduled, "
            "%d blog failures",
            len(results["blog_deployed"]),
            results["pins_scheduled"],
            len(results["blog_failed"]),
        )

        return results

    def deploy_to_preview(self) -> dict:
        """
        Deploy approved content to the develop branch for preview review.

        This is Phase 1 of the two-phase deployment:
        1. Commits blog posts to develop branch (Vercel preview deploy)
        2. Saves approved pin data for later scheduling
        3. Writes PRODUCTION status to Sheet for promotion approval
        4. Sends Slack notification with review instructions

        Returns:
            dict: Deployment results.
        """
        logger.info("Starting preview deployment to develop branch")

        results = {
            "blog_deployed": [],
            "blog_failed": [],
            "pins_saved": 0,
        }

        # Read content approvals from Google Sheets
        try:
            approvals = self.sheets.read_content_approvals()
        except Exception as e:
            logger.error("Failed to read content approvals: %s", e)
            try:
                self.slack.notify_failure(
                    "deploy_to_preview",
                    f"Cannot read content approvals from Google Sheets: {e}. "
                    f"Preview deployment halted. Please retry when Sheets is accessible.",
                )
            except Exception:
                pass
            raise

        approved_blogs = [
            item for item in approvals
            if item.get("type") == "blog"
            and item.get("status") in ("approved", "use_ai_image")
        ]
        approved_pins = [
            item for item in approvals
            if item.get("type") == "pin"
            and item.get("status") in ("approved", "use_ai_image")
        ]

        logger.info(
            "Approved content: %d blog posts, %d pins",
            len(approved_blogs), len(approved_pins),
        )

        # Deploy blog posts to develop branch
        if approved_blogs:
            deploy_result = self._deploy_blog_posts(approved_blogs)
            results["blog_deployed"] = deploy_result["deployed"]
            results["blog_failed"] = deploy_result["failed"]
        else:
            logger.info("No approved blog posts to deploy")

        # Save approved pin count for reference
        results["pins_saved"] = len(approved_pins)

        # Write PRODUCTION status to Sheet for promotion approval
        try:
            self.sheets.write_deploy_status(
                status="pending_review",
                preview_url="Check Vercel dashboard for preview URL",
            )
        except Exception as e:
            logger.error("Failed to write deploy status to Sheet: %s", e)

        # Send Slack notification
        try:
            deployed_count = len(results["blog_deployed"])
            failed_count = len(results["blog_failed"])
            self.slack.notify(
                f"Preview deploy complete: {deployed_count} blog posts on develop branch, "
                f"{results['pins_saved']} pins ready to schedule.\n"
                f"Review the blog posts on your Vercel preview deployment.\n"
                f"When ready, go to the Google Sheet > Weekly Review tab > "
                f"change cell B4 from 'pending_review' to 'approved' to push to production.",
                level="success" if failed_count == 0 else "warning",
            )
        except Exception as e:
            logger.error("Failed to send Slack notification: %s", e)

        logger.info(
            "Preview deploy complete: %d blogs deployed, %d failed, %d pins saved",
            len(results["blog_deployed"]),
            len(results["blog_failed"]),
            results["pins_saved"],
        )

        return results

    def promote_to_production(self) -> dict:
        """
        Merge develop to main, verify URLs, and schedule pins.

        This is Phase 2 of the two-phase deployment:
        1. Merges develop into main (triggers Vercel production deploy)
        2. Verifies blog post URLs are live on production
        3. Creates pin posting schedule
        4. Appends entries to content-log.jsonl
        5. Updates Sheet and sends Slack notification

        Returns:
            dict: Promotion results.
        """
        logger.info("Starting production promotion: merging develop -> main")

        results = {
            "merge_sha": "",
            "verification_results": {},
            "pins_scheduled": 0,
            "content_log_entries": 0,
        }

        # Step 1: Merge develop into main
        try:
            merge_sha = self.github.merge_develop_to_main(
                commit_message=f"Deploy blog posts to production ({date.today().isoformat()})"
            )
            results["merge_sha"] = merge_sha
            logger.info("Merged develop -> main: %s", merge_sha[:8] if merge_sha else "already in sync")
        except Exception as e:
            logger.error("Failed to merge develop into main: %s", e)
            try:
                self.slack.notify_failure(
                    "promote_to_production",
                    f"Merge develop -> main failed: {e}",
                )
            except Exception:
                pass
            raise

        # Step 2: Read approvals to get blog slugs and pin data
        try:
            approvals = self.sheets.read_content_approvals()
        except Exception as e:
            logger.error("Failed to read content approvals: %s", e)
            try:
                self.slack.notify_failure(
                    "promote_to_production",
                    f"Cannot read content approvals from Google Sheets: {e}. "
                    f"Production promotion halted. Please retry when Sheets is accessible.",
                )
            except Exception:
                pass
            raise

        approved_blogs = [
            item for item in approvals
            if item.get("type") == "blog"
            and item.get("status") in ("approved", "use_ai_image")
        ]
        approved_pins = [
            item for item in approvals
            if item.get("type") == "pin"
            and item.get("status") in ("approved", "use_ai_image")
        ]

        # Step 3: Verify blog post URLs on production
        deployed_slugs = [
            b.get("slug") or b.get("id", "") for b in approved_blogs
        ]
        if deployed_slugs:
            results["verification_results"] = self.verify_urls(
                deployed_slugs, max_wait=DEPLOY_VERIFY_TIMEOUT
            )

            failed_verifications = [
                slug for slug, ok in results["verification_results"].items()
                if not ok
            ]
            if failed_verifications:
                logger.warning("URLs failed verification: %s", failed_verifications)
                retry_results = self.verify_urls(failed_verifications, max_wait=60)
                results["verification_results"].update(retry_results)

                still_failed = [s for s, ok in retry_results.items() if not ok]
                if still_failed:
                    logger.error("URLs still failing after retry: %s", still_failed)
                    try:
                        self.slack.notify_failure(
                            "promote_to_production",
                            f"Blog post URLs failed to resolve: {still_failed}",
                        )
                    except Exception:
                        pass

        # Step 4: Update Sheet with live URLs
        try:
            for slug in deployed_slugs:
                if results["verification_results"].get(slug, False):
                    live_url = f"{BLOG_BASE_URL}/{slug}"
                    self.sheets.update_pin_status(
                        pin_id=slug,
                        status="deployed",
                        pinterest_pin_id=live_url,
                    )
        except Exception as e:
            logger.error("Failed to update Sheet with live URLs: %s", e)

        # Step 4b: Process use_ai_image pins — swap AI hero into primary slot
        use_ai_pins = [p for p in approved_pins if p.get("status") == "use_ai_image"]
        if use_ai_pins:
            # Load full pin data for swap processing
            pin_results_path = DATA_DIR / "pin-generation-results.json"
            full_pin_data = {}
            if pin_results_path.exists():
                try:
                    pin_results = json.loads(pin_results_path.read_text(encoding="utf-8"))
                    for pin in pin_results.get("generated", []):
                        full_pin_data[pin["pin_id"]] = pin
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Could not load pin generation results for swap: %s", e)

            if full_pin_data:
                self._process_ai_image_swaps(use_ai_pins, full_pin_data)
                # Save updated pin data back
                try:
                    pin_results_path.write_text(
                        json.dumps(pin_results, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    logger.info("Saved updated pin data after AI image swaps")
                except OSError as e:
                    logger.error("Failed to save pin data after swaps: %s", e)

        # Step 5: Create pin schedule
        if approved_pins:
            results["pins_scheduled"] = self._create_pin_schedule(
                approved_pins, plan_path=None
            )

        # Step 6: Append to content log
        results["content_log_entries"] = self._append_to_content_log(
            blog_results=[{"slug": s} for s in deployed_slugs],
            pin_data=approved_pins,
        )

        # Step 7: Update deploy status
        try:
            self.sheets.write_deploy_status(status="deployed")
        except Exception as e:
            logger.error("Failed to update deploy status: %s", e)

        # Step 8: Slack notification
        try:
            verified_count = sum(1 for ok in results["verification_results"].values() if ok)
            self.slack.notify(
                f"Content is live on goslated.com! "
                f"{verified_count} blog posts verified, "
                f"{results['pins_scheduled']} pins scheduled for this week. "
                f"First pins post tomorrow.",
                level="success",
            )
        except Exception as e:
            logger.error("Failed to send Slack notification: %s", e)

        logger.info(
            "Production promotion complete: merge=%s, %d pins scheduled",
            results["merge_sha"][:8] if results["merge_sha"] else "n/a",
            results["pins_scheduled"],
        )

        return results

    def deploy_approved_posts(self, posts_dir: Path) -> dict:
        """
        Deploy all approved blog posts from a specific directory.

        Alternative entry point that reads MDX files from a directory
        rather than relying on Sheets approvals.

        Args:
            posts_dir: Directory containing generated MDX files and images.

        Returns:
            dict: Deployment results with counts and any errors.
        """
        logger.info("Deploying blog posts from %s", posts_dir)

        if not posts_dir.exists():
            logger.error("Posts directory does not exist: %s", posts_dir)
            return {"deployed": [], "failed": []}

        # Find all MDX files
        mdx_files = list(posts_dir.glob("*.mdx"))
        if not mdx_files:
            logger.warning("No MDX files found in %s", posts_dir)
            return {"deployed": [], "failed": []}

        # Build post data for deployment
        posts_to_deploy = []
        for mdx_file in mdx_files:
            slug = mdx_file.stem
            mdx_content = mdx_file.read_text(encoding="utf-8")

            # Check for hero image
            hero_image_path = None
            for ext in [".jpg", ".jpeg", ".png", ".webp"]:
                candidate = posts_dir / f"{slug}{ext}"
                if candidate.exists():
                    hero_image_path = candidate
                    break

            # Update heroImage frontmatter to match actual image extension
            if hero_image_path:
                actual_ext = Path(hero_image_path).suffix
                mdx_content = re.sub(
                    r'(heroImage:\s*"/assets/blog/' + re.escape(slug) + r')\.[a-z]+"',
                    rf'\1{actual_ext}"',
                    mdx_content,
                )

            posts_to_deploy.append({
                "slug": slug,
                "mdx_content": mdx_content,
                "hero_image_path": hero_image_path,
            })

        # Commit all posts in a single batch commit
        try:
            commit_sha = self.github.commit_multiple_posts(
                posts=posts_to_deploy,
                commit_message=f"Deploy {len(posts_to_deploy)} blog posts for week of {date.today().isoformat()}",
            )
            logger.info("Committed %d blog posts (SHA: %s)", len(posts_to_deploy), commit_sha)

            deployed = [{"slug": p["slug"]} for p in posts_to_deploy]
            return {"deployed": deployed, "failed": [], "commit_sha": commit_sha}

        except Exception as e:
            logger.error("Batch commit failed: %s", e)
            return {
                "deployed": [],
                "failed": [{"slug": p["slug"], "error": str(e)} for p in posts_to_deploy],
            }

    def verify_urls(self, slugs: list[str], max_wait: int = 180) -> dict:
        """
        Verify that blog post URLs are live after deployment.

        Calls github_api.verify_deployment() for each slug.

        Args:
            slugs: List of blog post slugs to verify.
            max_wait: Max seconds to wait per URL.

        Returns:
            dict: slug -> bool (True if live, False if not).
        """
        results = {}
        for slug in slugs:
            try:
                is_live = self.github.verify_deployment(
                    slug,
                    max_wait_seconds=max_wait,
                )
                results[slug] = is_live
                if is_live:
                    logger.info("Verified: %s/%s is live", BLOG_BASE_URL, slug)
                else:
                    logger.warning("Not live: %s/%s", BLOG_BASE_URL, slug)
            except Exception as e:
                logger.error("Verification error for %s: %s", slug, e)
                results[slug] = False

        return results

    def _deploy_blog_posts(self, approved_blogs: list[dict]) -> dict:
        """
        Commit approved blog posts to the goslated.com repository.

        Args:
            approved_blogs: List of approved blog post items from Sheets.

        Returns:
            dict: {"deployed": [...], "failed": [...]}
        """
        deployed = []
        failed = []

        # Build the list of posts for batch commit
        posts_for_commit = []
        for blog_item in approved_blogs:
            slug = blog_item.get("slug") or blog_item.get("id", "")

            # Read the generated MDX file
            mdx_path = GENERATED_BLOG_DIR / f"{slug}.mdx"
            if not mdx_path.exists():
                logger.error("Generated MDX file not found: %s", mdx_path)
                failed.append({"slug": slug, "error": "MDX file not found"})
                continue

            mdx_content = mdx_path.read_text(encoding="utf-8")

            # Extract frontmatter slug (may differ from file slug for weekly plans)
            fm_slug_match = re.search(r'^slug:\s*"(.+?)"', mdx_content, re.MULTILINE)
            fm_slug = fm_slug_match.group(1) if fm_slug_match else slug

            # Check for hero image on disk first
            hero_image_path = None
            for ext in [".jpg", ".jpeg", ".png", ".webp"]:
                candidate_paths = [
                    GENERATED_BLOG_DIR / f"{slug}{ext}",
                    GENERATED_PINS_DIR / f"{slug}-hero{ext}",
                ]
                for candidate in candidate_paths:
                    if candidate.exists():
                        hero_image_path = candidate
                        break
                if hero_image_path:
                    break

            if not hero_image_path:
                logger.warning("No hero image found for blog %s", slug)

            # Update heroImage frontmatter to match actual image extension
            if hero_image_path:
                actual_ext = Path(hero_image_path).suffix
                mdx_content = re.sub(
                    r'(heroImage:\s*"/assets/blog/' + re.escape(fm_slug) + r')\.[a-z]+"',
                    rf'\1{actual_ext}"',
                    mdx_content,
                )

            posts_for_commit.append({
                "slug": slug,
                "image_slug": fm_slug,
                "mdx_content": mdx_content,
                "hero_image_path": hero_image_path,
            })

        if not posts_for_commit:
            logger.warning("No valid blog posts to commit")
            return {"deployed": deployed, "failed": failed}

        # Try batch commit first
        try:
            commit_sha = self.github.commit_multiple_posts(
                posts=posts_for_commit,
                commit_message=(
                    f"Add {len(posts_for_commit)} blog posts "
                    f"({date.today().isoformat()})"
                ),
            )
            logger.info(
                "Batch committed %d blog posts (SHA: %s)",
                len(posts_for_commit), commit_sha,
            )
            deployed = [{"slug": p["slug"], "commit_sha": commit_sha} for p in posts_for_commit]

        except Exception as batch_error:
            logger.warning(
                "Batch commit failed (%s), falling back to individual commits",
                batch_error,
            )
            # Fall back to individual commits
            for post in posts_for_commit:
                try:
                    commit_sha = self.github.commit_blog_post(
                        slug=post["slug"],
                        image_slug=post.get("image_slug"),
                        mdx_content=post["mdx_content"],
                        hero_image_path=post.get("hero_image_path"),
                    )
                    deployed.append({"slug": post["slug"], "commit_sha": commit_sha})
                    logger.info("Committed %s (SHA: %s)", post["slug"], commit_sha)
                except Exception as e:
                    logger.error("Failed to commit %s: %s", post["slug"], e)
                    failed.append({"slug": post["slug"], "error": str(e)})

        return {"deployed": deployed, "failed": failed}

    def _create_pin_schedule(
        self,
        approved_pins: list[dict],
        plan_path: Optional[str] = None,
    ) -> int:
        """
        Create the pin posting schedule from approved pins.

        Writes a JSON file that post_pins.py reads to know what to post
        and when.

        Args:
            approved_pins: Approved pin items from Sheets.
            plan_path: Optional path to load full pin data.

        Returns:
            int: Number of pins scheduled.
        """
        # Load full pin generation results for complete data
        pin_results_path = DATA_DIR / "pin-generation-results.json"
        full_pin_data = {}
        if pin_results_path.exists():
            try:
                pin_results = json.loads(pin_results_path.read_text(encoding="utf-8"))
                for pin in pin_results.get("generated", []):
                    full_pin_data[pin["pin_id"]] = pin
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Could not load pin generation results: %s", e)

        # Build the schedule
        schedule = []
        for pin_item in approved_pins:
            pin_id = pin_item.get("id") or pin_item.get("pin_id", "")
            full_data = full_pin_data.get(pin_id, {})

            schedule_entry = {
                "pin_id": pin_id,
                "title": full_data.get("title", pin_item.get("title", "")),
                "description": full_data.get("description", ""),
                "alt_text": full_data.get("alt_text", ""),
                "board_id": full_data.get("board_id", ""),
                "board_name": full_data.get("board_name", ""),
                "link": full_data.get("link", ""),
                "image_path": full_data.get("image_path", ""),
                "image_url": full_data.get("_drive_download_url", ""),
                "scheduled_date": full_data.get("scheduled_date", ""),
                "scheduled_slot": full_data.get("scheduled_slot", ""),
                "pillar": full_data.get("pillar"),
                "pin_type": full_data.get("pin_type", "primary"),
                "primary_keyword": full_data.get("primary_keyword", ""),
                "secondary_keywords": full_data.get("secondary_keywords", []),
                "blog_slug": full_data.get("blog_slug", ""),
                "content_type": full_data.get("content_type", ""),
                "funnel_layer": full_data.get("funnel_layer", "discovery"),
                "template": full_data.get("template", ""),
                "treatment_number": full_data.get("treatment_number", 1),
                "source_post_id": full_data.get("source_post_id", ""),
                "image_source": full_data.get("image_source", ""),
                "image_id": full_data.get("image_id", ""),
                "status": "scheduled",
            }
            schedule.append(schedule_entry)

        # Write the schedule file
        schedule_path = DATA_DIR / "pin-schedule.json"
        schedule_path.write_text(
            json.dumps(schedule, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Created pin schedule with %d pins at %s", len(schedule), schedule_path)

        return len(schedule)

    def _process_ai_image_swaps(
        self,
        use_ai_pins: list[dict],
        full_pin_data: dict,
    ) -> None:
        """
        For pins marked use_ai_image, swap the AI hero image into the
        primary slot, re-render the pin, and upload to GCS.

        Args:
            use_ai_pins: Approved pin items with status "use_ai_image".
            full_pin_data: Dict of pin_id -> full pin data (modified in-place).
        """
        from src.pin_assembler import PinAssembler
        from src.apis.gcs_api import GcsAPI

        assembler = PinAssembler()
        gcs = GcsAPI()

        for pin_item in use_ai_pins:
            pin_id = pin_item.get("id") or pin_item.get("pin_id", "")
            pin_data = full_pin_data.get(pin_id, {})
            ai_image_url = pin_data.get("_ai_image_url", "")

            if not ai_image_url:
                logger.warning("No AI image URL for %s, skipping swap", pin_id)
                try:
                    self.slack.notify(
                        f"Warning: Pin {pin_id} was set to use_ai_image but no AI image "
                        f"was available. This pin will use the original stock image instead.",
                        level="warning",
                    )
                except Exception:
                    pass
                continue

            try:
                import requests

                # Download AI hero image from GCS
                ai_hero_path = GENERATED_PINS_DIR / f"{pin_id}-ai-hero.png"
                response = requests.get(ai_image_url, timeout=30)
                response.raise_for_status()
                ai_hero_path.write_bytes(response.content)

                # Re-render pin template with AI hero
                template_type = pin_data.get("template", "recipe-pin")
                text_overlay = pin_data.get("text_overlay", {})
                headline = text_overlay.get("headline", "") if isinstance(text_overlay, dict) else str(text_overlay)
                subtitle = text_overlay.get("sub_text", "") if isinstance(text_overlay, dict) else ""

                rendered_path = assembler.assemble_pin(
                    template_type=template_type,
                    hero_image_path=ai_hero_path,
                    headline=headline,
                    subtitle=subtitle,
                    variant=pin_data.get("treatment_number", 1),
                    output_path=GENERATED_PINS_DIR / f"{pin_id}.png",
                    extra_context={"background_image_url": str(ai_hero_path)},
                )

                # Upload re-rendered pin to GCS
                new_url = gcs.upload_single_image(
                    rendered_path, f"{pin_id}.png"
                )

                # Update pin_data in-place
                pin_data["hero_image_path"] = str(ai_hero_path)
                pin_data["image_path"] = str(rendered_path)
                pin_data["image_source"] = "ai_generated"
                if new_url:
                    pin_data["_drive_image_url"] = new_url
                    pin_data["_drive_download_url"] = new_url

                logger.info("Swapped AI image for pin %s", pin_id)

            except Exception as e:
                logger.error("Failed to swap AI image for pin %s: %s", pin_id, e)

    def _append_to_content_log(
        self,
        blog_results: list[dict],
        pin_data: list[dict],
    ) -> int:
        """
        Append new entries to data/content-log.jsonl.

        Creates content log entries with initial performance metrics = 0.

        Args:
            blog_results: Deployed blog post data.
            pin_data: Approved pin data.

        Returns:
            int: Number of entries appended.
        """
        log_path = DATA_DIR / "content-log.jsonl"
        today_str = date.today().isoformat()

        # Load existing entry IDs to avoid duplicates on rerun
        # Collect both schedule_id (per-pin, new entries) and source_post_id (old entries)
        existing_ids = set()
        if log_path.exists():
            try:
                for line in log_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        existing_entry = json.loads(line)
                        for key in ("schedule_id", "source_post_id"):
                            val = existing_entry.get(key, "")
                            if val:
                                existing_ids.add(val)
                    except json.JSONDecodeError:
                        continue
            except OSError:
                pass

        # Load full pin generation results for complete data
        pin_results_path = DATA_DIR / "pin-generation-results.json"
        full_pin_data = {}
        if pin_results_path.exists():
            try:
                pin_results = json.loads(pin_results_path.read_text(encoding="utf-8"))
                for pin in pin_results.get("generated", []):
                    full_pin_data[pin["pin_id"]] = pin
            except (json.JSONDecodeError, KeyError):
                pass

        entries_written = 0
        skipped_dupes = 0

        with open(log_path, "a", encoding="utf-8") as f:
            for pin_item in pin_data:
                pin_id = pin_item.get("id") or pin_item.get("pin_id", "")
                full = full_pin_data.get(pin_id, {})

                # Skip if already logged (dedup for reruns)
                source_post = full.get("source_post_id", "")
                if (pin_id and pin_id in existing_ids) or (source_post and source_post in existing_ids):
                    skipped_dupes += 1
                    continue

                entry = {
                    "date": today_str,
                    "posted_date": today_str,  # weekly_analysis.py filters on this field
                    "schedule_id": pin_id,  # Per-pin unique ID (e.g., "W9-01") for dedup
                    "pin_id": None,  # Set when actually posted to Pinterest
                    "blog_slug": full.get("blog_slug", ""),
                    "blog_title": full.get("title", pin_item.get("title", "")),
                    "topic_summary": _build_topic_summary(full),
                    "pillar": full.get("pillar", pin_item.get("pillar")),
                    "content_type": full.get("content_type", ""),
                    "funnel_layer": full.get("funnel_layer", "discovery"),
                    "template": full.get("template", ""),
                    "board": full.get("board_name", ""),
                    "primary_keyword": full.get("primary_keyword", ""),
                    "secondary_keywords": full.get("secondary_keywords", []),
                    "image_source": full.get("image_source", ""),
                    "image_id": full.get("image_id", ""),
                    "pin_type": full.get("pin_type", "primary"),
                    "treatment_number": full.get("treatment_number", 1),
                    "source_post_id": full.get("source_post_id", ""),
                    "impressions": 0,
                    "saves": 0,
                    "outbound_clicks": 0,
                }

                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                entries_written += 1

        if skipped_dupes:
            logger.info("Skipped %d duplicate entries in content-log.jsonl", skipped_dupes)
        logger.info("Appended %d entries to content-log.jsonl", entries_written)
        return entries_written


def deploy_approved_content(plan_path: Optional[str] = None) -> dict:
    """
    Module-level convenience function for deploying approved content.

    Creates a BlogDeployer and runs the deployment.

    Args:
        plan_path: Optional path to the weekly plan JSON.

    Returns:
        dict: Deployment results.
    """
    deployer = BlogDeployer()
    return deployer.deploy_approved_content(plan_path)


def _build_topic_summary(pin_data: dict) -> str:
    """
    Build a topic summary string from pin data for the content log.

    Args:
        pin_data: Full pin data dict.

    Returns:
        str: Brief topic summary.
    """
    parts = []

    title = pin_data.get("title", "")
    if title:
        parts.append(title)

    primary_kw = pin_data.get("primary_keyword", "")
    if primary_kw and primary_kw.lower() not in title.lower():
        parts.append(primary_kw)

    return ", ".join(parts)[:200] if parts else ""


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    deployer = BlogDeployer()

    if mode == "preview":
        print("Deploying approved content to preview (develop branch)...")
        results = deployer.deploy_to_preview()
        print(
            f"Preview deploy: {len(results.get('blog_deployed', []))} blog posts to develop, "
            f"{results.get('pins_saved', 0)} pins saved for scheduling"
        )
    elif mode == "promote":
        print("Promoting content to production (main branch)...")
        results = deployer.promote_to_production()
        print(
            f"Production: merged develop -> main, "
            f"{results.get('pins_scheduled', 0)} pins scheduled"
        )
    else:
        print(f"Unknown mode: {mode}. Use 'preview' or 'promote'.")
        sys.exit(1)
