"""
GitHub API Wrapper for Blog Post Deployment

Commits generated blog post files (MDX + hero images) to the goslated.com
repository, which triggers Vercel auto-deployment within ~60 seconds.

Uses the PyGithub library for the Git Data API (tree-based commits for
multi-file atomic operations).

Workflow:
1. Content generation produces MDX files + hero images
2. This module commits them to the goslated.com repo's content/blog/ directory
3. Vercel detects the commit and auto-deploys
4. Blog post URLs become live before any pins are posted

Target repository structure on goslated.com:
    content/
    |-- blog/
    |   |-- 30-minute-chicken-stir-fry.mdx
    |   |-- how-to-meal-plan-for-a-family-of-4.mdx
    |   +-- ...
    public/
    |-- assets/
    |   +-- blog/
    |       |-- 30-minute-chicken-stir-fry.jpg
    |       +-- ...

Environment variables required:
- GOSLATED_GITHUB_TOKEN (personal access token with repo write permissions)
- GOSLATED_REPO (e.g., "your-org/goslated.com")
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional

import requests

from src.shared.config import GOSLATED_BASE_URL

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Raised when GitHub API operations fail."""
    pass


class GitHubAPI:
    """Client for committing files to the goslated.com repository."""

    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
    ):
        """
        Initialize the GitHub API client using PyGithub.

        Args:
            token: GitHub personal access token. Falls back to GOSLATED_GITHUB_TOKEN env var.
            repo: Repository in "owner/repo" format. Falls back to GOSLATED_REPO env var.
        """
        self.token = token or os.environ.get("GOSLATED_GITHUB_TOKEN", "")
        self.repo_name = repo or os.environ.get("GOSLATED_REPO", "")

        if not self.token:
            raise GitHubAPIError(
                "GitHub token not provided. Set GOSLATED_GITHUB_TOKEN env var."
            )
        if not self.repo_name:
            raise GitHubAPIError(
                "GitHub repo not provided. Set GOSLATED_REPO env var (format: 'owner/repo')."
            )

        try:
            from github import Github
            self.github = Github(self.token, timeout=30)
            self.repo = self.github.get_repo(self.repo_name)
            logger.info("GitHub API initialized for repo: %s", self.repo_name)
        except ImportError as e:
            raise GitHubAPIError(
                "PyGithub not installed. Install: pip install PyGithub"
            ) from e
        except Exception as e:
            raise GitHubAPIError(f"Failed to initialize GitHub API: {e}") from e

    def commit_blog_post(
        self,
        slug: str,
        mdx_content: str,
        hero_image_path: Optional[Path] = None,
        commit_message: Optional[str] = None,
        image_slug: Optional[str] = None,
    ) -> str:
        """
        Commit a single blog post. Delegates to commit_multiple_posts().

        Args:
            slug: Blog post slug for the MDX file name.
            mdx_content: Complete MDX file content with frontmatter.
            hero_image_path: Local path to the hero image file.
            commit_message: Custom commit message. Auto-generated if None.
            image_slug: Slug for the deployed image path. Defaults to slug.

        Returns:
            str: The commit SHA.

        Raises:
            GitHubAPIError: If the commit fails.
        """
        return self.commit_multiple_posts(
            posts=[{
                "slug": slug,
                "mdx_content": mdx_content,
                "hero_image_path": hero_image_path,
                "image_slug": image_slug or slug,
            }],
            commit_message=commit_message or f"Add blog post: {slug}",
        )

    def commit_multiple_posts(
        self,
        posts: list[dict],
        commit_message: Optional[str] = None,
    ) -> str:
        """
        Commit multiple blog posts in a single commit using the Git tree API.

        More efficient than individual commits for batch deployments.

        Args:
            posts: List of dicts with keys: slug, mdx_content, hero_image_path (optional),
                   image_slug (optional, defaults to slug — used for the deployed image path
                   when the frontmatter slug differs from the file slug).
            commit_message: Commit message. Auto-generated if None.

        Returns:
            str: The commit SHA.
        """
        files = []

        for post in posts:
            slug = post["slug"]
            image_slug = post.get("image_slug", slug)
            files.append({
                "path": f"content/blog/{slug}.mdx",
                "content": post["mdx_content"],
            })

            hero_path = post.get("hero_image_path")
            if hero_path and Path(hero_path).exists():
                with open(hero_path, "rb") as f:
                    image_data = f.read()
                extension = Path(hero_path).suffix or ".jpg"
                files.append({
                    "path": f"public/assets/blog/{image_slug}{extension}",
                    "content": image_data,
                    "is_binary": True,
                })

        if not commit_message:
            slugs = [p["slug"] for p in posts]
            commit_message = f"Add {len(posts)} blog posts: {', '.join(slugs[:3])}"
            if len(slugs) > 3:
                commit_message += f" +{len(slugs) - 3} more"

        return self._commit_files(files, commit_message)

    def verify_deployment(
        self,
        slug_or_urls: str | list[str],
        max_wait_seconds: int = 120,
    ) -> bool:
        """
        Verify that blog post URL(s) are live after Vercel deployment.

        Polls with exponential backoff until URL returns 200 or timeout.

        Args:
            slug_or_urls: Either a single slug (e.g., "chicken-stir-fry")
                          or a list of full URLs to verify.
            max_wait_seconds: Maximum time to wait for deployment.

        Returns:
            bool: True if all URL(s) are live.
        """
        # Normalize to list of URLs
        if isinstance(slug_or_urls, str):
            if slug_or_urls.startswith("http"):
                urls = [slug_or_urls]
            else:
                urls = [f"{GOSLATED_BASE_URL}/blog/{slug_or_urls}"]
        else:
            urls = []
            for item in slug_or_urls:
                if item.startswith("http"):
                    urls.append(item)
                else:
                    urls.append(f"{GOSLATED_BASE_URL}/blog/{item}")

        logger.info("Verifying deployment of %d URL(s), max wait %ds...", len(urls), max_wait_seconds)

        start_time = time.time()
        poll_interval = 5  # Start with 5 seconds
        verified = set()

        while time.time() - start_time < max_wait_seconds:
            for url in urls:
                if url in verified:
                    continue

                try:
                    response = requests.get(url, timeout=10, allow_redirects=True)
                    if response.status_code == 200:
                        verified.add(url)
                        logger.info("URL is live: %s", url)
                except requests.RequestException:
                    pass  # Not ready yet

            if len(verified) == len(urls):
                logger.info("All %d URL(s) verified live.", len(urls))
                return True

            remaining = [u for u in urls if u not in verified]
            logger.debug(
                "Waiting for %d URL(s): %s",
                len(remaining),
                [u.split("/")[-1] for u in remaining[:3]],
            )

            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 20)  # Exponential backoff, cap at 20s

        unverified = [u for u in urls if u not in verified]
        logger.warning(
            "Deployment verification timed out. %d/%d URL(s) not live: %s",
            len(unverified), len(urls), unverified,
        )
        return False

    def merge_develop_to_main(self, commit_message: Optional[str] = None) -> str:
        """
        Merge the develop branch into main for production deployment.

        Uses GitHub's merge API to create a merge commit.

        Args:
            commit_message: Custom merge commit message.

        Returns:
            str: The merge commit SHA.

        Raises:
            GitHubAPIError: If the merge fails (e.g., conflicts).
        """
        if not commit_message:
            commit_message = "Merge develop into main (pinterest pipeline deploy)"

        try:
            merge_result = self.repo.merge(
                base="main",
                head="develop",
                commit_message=commit_message,
            )
            if merge_result is None:
                # No merge needed — branches already in sync
                logger.info("No merge needed, develop and main are already in sync.")
                ref = self.repo.get_git_ref("heads/main")
                return ref.object.sha

            logger.info("Merged develop into main: SHA %s", merge_result.sha[:8])
            return merge_result.sha
        except Exception as e:
            raise GitHubAPIError(f"Failed to merge develop into main: {e}") from e

    def _commit_files(
        self,
        files: list[dict],
        commit_message: str,
        branch: str = "develop",
    ) -> str:
        """
        Commit multiple files atomically using the Git Data API (tree + commit).

        This is more efficient than individual file updates and ensures all
        files appear in a single commit.

        Args:
            files: List of dicts with keys: path, content, is_binary (optional).
            commit_message: Commit message.
            branch: Target branch.

        Returns:
            str: The commit SHA.
        """
        from github import InputGitTreeElement

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                # Get the current HEAD commit and tree
                ref = self.repo.get_git_ref(f"heads/{branch}")
                head_sha = ref.object.sha
                base_tree = self.repo.get_git_tree(head_sha)

                # Build tree elements for each file
                tree_elements = []
                for file_info in files:
                    path = file_info["path"]
                    content = file_info["content"]
                    is_binary = file_info.get("is_binary", False)

                    if is_binary:
                        # Binary files need to be created as blobs first
                        import base64 as b64
                        if isinstance(content, bytes):
                            blob = self.repo.create_git_blob(
                                b64.b64encode(content).decode("ascii"),
                                "base64",
                            )
                        else:
                            blob = self.repo.create_git_blob(content, "base64")

                        tree_elements.append(
                            InputGitTreeElement(
                                path=path,
                                mode="100644",
                                type="blob",
                                sha=blob.sha,
                            )
                        )
                    else:
                        tree_elements.append(
                            InputGitTreeElement(
                                path=path,
                                mode="100644",
                                type="blob",
                                content=content if isinstance(content, str) else content.decode("utf-8"),
                            )
                        )

                # Create the new tree
                new_tree = self.repo.create_git_tree(tree_elements, base_tree)

                # Create the commit
                parent = self.repo.get_git_commit(head_sha)
                new_commit = self.repo.create_git_commit(
                    message=commit_message,
                    tree=new_tree,
                    parents=[parent],
                )

                # Update the branch ref
                ref.edit(sha=new_commit.sha)

                logger.info(
                    "Committed %d files to %s/%s: %s (SHA: %s)",
                    len(files), self.repo_name, branch,
                    commit_message[:60], new_commit.sha[:8],
                )

                return new_commit.sha

            except Exception as e:
                if attempt < max_attempts and hasattr(e, 'status') and getattr(e, 'status', 0) >= 429:
                    logger.warning("GitHub API error (attempt %d/%d): %s. Retrying...", attempt, max_attempts, e)
                    time.sleep(5 * attempt)
                    continue
                raise GitHubAPIError(
                    f"Failed to commit {len(files)} files: {e}"
                ) from e



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("GitHub API smoke test")
    print("=====================")

    try:
        gh = GitHubAPI()
        print(f"Connected to repo: {gh.repo_name}")
        print(f"Default branch: {gh.repo.default_branch}")

    except GitHubAPIError as e:
        print(f"GitHub API error: {e}")
    except Exception as e:
        print(f"Error: {e}")
