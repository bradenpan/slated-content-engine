"""TikTok Content-Level Regeneration Orchestrator.

Handles image regeneration for rendered carousel slides based on reviewer
feedback in the Content Queue tab. When a reviewer sets a carousel's status
to regen_image_N or regen (with optional feedback in col P), this script:

1. Reads regen requests from the Content Queue sheet
2. Loads the current plan JSON from disk
3. Parses regen status to determine target slides
4. Translates column-position N to actual slide_index
5. Generates new AI images (or modifies prompt with feedback)
6. Re-renders the full carousel via CarouselAssembler
7. Uploads changed slides to GCS (cache-bust for Sheet refresh)
8. Updates Content Queue row with new =IMAGE() URLs
9. Saves updated plan JSON to disk
10. Resets R1 trigger to idle
11. Sends Slack notification

Regen status values:
- regen_image_0       -> regenerate hook slide's AI image
- regen_image_2       -> regenerate content slide 2's AI image
- regen_image_0,regen_image_3 -> comma-separated multiple slides
- regen               -> regenerate ALL AI images + full re-render

Column-position numbering (Content Queue D-L):
  0=hook (D), 1-7=content slides (E-K), 8=CTA (L)
  Translated to slide_index using content_slides length.

Triggered by:
- Apps Script: Content Queue R1 = "run" -> repository_dispatch
- GitHub Actions: tiktok-regen-content.yml workflow
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

from src.shared.apis.gcs_api import GcsAPI
from src.shared.apis.image_gen import ImageGenAPI
from src.shared.apis.sheets_api import SheetsAPI
from src.shared.apis.slack_notify import SlackNotify
from src.shared.image_cleaner import clean_image
from src.shared.paths import TIKTOK_DATA_DIR, TIKTOK_OUTPUT_DIR
from src.shared.utils.plan_utils import find_latest_plan, load_plan
from src.tiktok.carousel_assembler import CarouselAssembler
from src.tiktok.generate_carousels import (
    IMAGE_GEN_HEIGHT,
    IMAGE_GEN_WIDTH,
    build_slides_for_render,
)

logger = logging.getLogger(__name__)


def _parse_regen_status(status: str) -> list[int] | None:
    """Parse regen status into a list of column-position targets.

    Returns:
        List of column-position ints (0=hook, 1-7=content, 8=CTA),
        or None for full regen.
    """
    status = status.strip().lower()
    if status == "regen":
        return None  # Full regen

    targets = []
    for part in status.split(","):
        part = part.strip()
        if part.startswith("regen_image_"):
            try:
                n = int(part.split("_")[-1])
                targets.append(n)
            except ValueError:
                logger.warning("Could not parse regen target: %s", part)
    return targets if targets else None


def _col_position_to_slide_index(col_pos: int, content_slide_count: int) -> int | None:
    """Translate Content Queue column-position to actual slide_index.

    Column-position is a fixed layout (0=hook, 1-7=content, 8=CTA).
    slide_index is the carousel's actual ordering (0=hook, 1..N=content, N+1=CTA).

    Returns None if col_pos is out of range for this carousel.
    """
    if col_pos == 0:
        return 0  # Hook is always slide_index 0
    if col_pos == 8:
        return content_slide_count + 1  # CTA
    if 1 <= col_pos <= content_slide_count:
        return col_pos  # Content slide (1-based matches slide_index)
    return None  # Out of range


def _find_image_prompt(image_prompts: list[dict], slide_index: int) -> dict | None:
    """Find the image_prompt entry for a given slide_index."""
    for ip in image_prompts:
        if ip.get("slide_index") == slide_index:
            return ip
    return None


def regen_content(
    sheets: SheetsAPI | None = None,
    slack: SlackNotify | None = None,
) -> None:
    """Main orchestration function for TikTok content-level regeneration."""
    logger.info("Starting TikTok content-level regeneration...")

    # Step 1: Read regen requests from Sheet
    tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
    if not tiktok_sheet_id:
        raise ValueError("TIKTOK_SPREADSHEET_ID env var not set.")
    sheets = sheets or SheetsAPI(sheet_id=tiktok_sheet_id)
    regen_requests = sheets.read_tiktok_content_regen_requests()

    if not regen_requests:
        logger.info("No TikTok content regen requests found. Nothing to do.")
        sheets.reset_tiktok_content_regen_trigger()
        return

    logger.info(
        "Found %d regen requests: %s",
        len(regen_requests),
        [r["carousel_id"] for r in regen_requests],
    )

    # Step 2: Load current plan from disk
    plan_path = find_latest_plan(data_dir=TIKTOK_DATA_DIR)
    if not plan_path:
        raise FileNotFoundError(
            "No TikTok weekly plan files found in data/tiktok/. "
            "Run generate_weekly_plan.py --generate-content first."
        )
    plan = load_plan(plan_path)
    carousels = plan.get("carousels", [])
    carousel_by_id = {c.get("carousel_id", ""): c for c in carousels}

    # Step 3: Initialize services
    image_gen = ImageGenAPI(provider="openai")
    assembler = CarouselAssembler()
    try:
        gcs = GcsAPI()
    except Exception as e:
        logger.warning("Could not initialize GcsAPI: %s", e)
        gcs = None

    # Step 4: Process each regen request
    successes = []
    failures = []
    skipped = []
    cache_bust = f"?t={int(time.time())}"

    for req in regen_requests:
        cid = req["carousel_id"]
        if cid not in carousel_by_id:
            logger.warning("Carousel %s not found in plan, skipping", cid)
            skipped.append(cid)
            continue

        spec = carousel_by_id[cid]
        image_prompts = spec.get("image_prompts") or []
        content_slides = spec.get("content_slides") or []
        content_slide_count = len(content_slides)
        feedback = req.get("feedback", "")

        # Parse targets
        targets = _parse_regen_status(req["status"])
        if targets is None:
            # Full regen: target all slides that have image_prompts
            slide_indices = [ip["slide_index"] for ip in image_prompts]
        else:
            # Targeted regen: translate column-positions to slide_indices
            slide_indices = []
            for col_pos in targets:
                si = _col_position_to_slide_index(col_pos, content_slide_count)
                if si is None:
                    logger.warning(
                        "Carousel %s: column-position %d is out of range "
                        "(carousel has %d content slides), skipping",
                        cid, col_pos, content_slide_count,
                    )
                    continue
                # Check if this slide has an image prompt
                ip = _find_image_prompt(image_prompts, si)
                if ip is None:
                    logger.info(
                        "Carousel %s: slide_index %d (col-pos %d) has no image prompt — no-op",
                        cid, si, col_pos,
                    )
                    continue
                slide_indices.append(si)

        if not slide_indices:
            notes = f"No image prompts found for requested slides — nothing to regenerate."
            sheets.update_tiktok_content_row(cid, status="pending_review", notes=notes)
            skipped.append(cid)
            logger.info("Carousel %s: no valid image targets, skipping", cid)
            continue

        try:
            carousel_output = TIKTOK_OUTPUT_DIR / cid
            carousel_output.mkdir(parents=True, exist_ok=True)

            # Step 5: Generate new images for target slides
            new_image_paths: dict[int, Path] = {}
            for si in slide_indices:
                ip = _find_image_prompt(image_prompts, si)
                prompt = ip["prompt"]
                # Append feedback to prompt if provided
                if feedback:
                    prompt = f"{prompt}\n\nReviewer feedback: {feedback}"
                    # Update the image prompt in the spec for audit trail
                    ip["prompt"] = prompt

                img_path = carousel_output / f"bg-slide-{si}.png"
                generated = image_gen.generate(
                    prompt=prompt,
                    width=IMAGE_GEN_WIDTH,
                    height=IMAGE_GEN_HEIGHT,
                    output_path=img_path,
                    style="natural",
                )
                cleaned = clean_image(generated, add_noise=False)
                new_image_paths[si] = cleaned
                logger.info("Regenerated image for %s slide %d", cid, si)

            # Step 6: Collect ALL image paths (existing + new)
            # Load existing images from the plan's render data
            all_image_paths: dict[int, Path] = {}
            for ip in image_prompts:
                si = ip["slide_index"]
                existing_path = carousel_output / f"bg-slide-{si}.png"
                if existing_path.exists():
                    all_image_paths[si] = existing_path
            # Overwrite with newly generated images
            all_image_paths.update(new_image_paths)

            # Step 7: Re-render the full carousel
            taxonomy_family = spec.get("template_family", "clean_educational")
            assembler_family = taxonomy_family.replace("_", "-")
            slides = build_slides_for_render(spec, all_image_paths)

            rendered_paths = assembler.render_carousel(
                family=assembler_family,
                slides=slides,
                output_dir=carousel_output,
                carousel_id=cid,
            )

            # Clean rendered PNGs
            cleaned_paths = []
            for rp in rendered_paths:
                cleaned = clean_image(rp, add_noise=True, noise_sigma=1.5)
                cleaned_paths.append(cleaned)

            # Step 8: Upload changed slides to GCS
            new_urls: dict[int, str] = {}
            if gcs and gcs.is_available:
                for i, slide_path in enumerate(cleaned_paths):
                    remote_name = f"tiktok/{cid}/slide-{i}.png"
                    url = gcs.upload_image(slide_path, remote_name)
                    if url:
                        new_urls[i] = url + cache_bust

                logger.info(
                    "Uploaded %d slides for %s to GCS",
                    len(new_urls), cid,
                )
            else:
                logger.warning("GCS not available, skipping slide re-upload for %s", cid)

            # Step 9: Update Content Queue row
            regen_desc = ", ".join(f"slide {si}" for si in slide_indices)
            notes = f"Regenerated images: {regen_desc}"
            if feedback:
                notes += f" (feedback: {feedback[:100]})"

            slide_urls_for_row = None
            if new_urls:
                # Build full URL list for all slides (with cache-bust on changed ones)
                slide_urls_for_row = []
                for i in range(len(cleaned_paths)):
                    if i in new_urls:
                        slide_urls_for_row.append(new_urls[i])
                    elif gcs and gcs.is_available:
                        # Existing slide — use URL without cache bust
                        slide_urls_for_row.append(
                            gcs.get_public_url(f"tiktok/{cid}/slide-{i}.png")
                        )
                    else:
                        slide_urls_for_row.append("")

            sheets.update_tiktok_content_row(
                cid,
                status="pending_review",
                notes=notes,
                slide_urls=slide_urls_for_row,
            )

            successes.append((cid, slide_indices))
            logger.info("Content regen complete for %s (slides: %s)", cid, slide_indices)

        except Exception as e:
            failures.append((cid, str(e)))
            logger.error("Content regen failed for %s: %s", cid, e)

    # Step 10: Save updated plan JSON (image prompts may have been modified)
    tmp = plan_path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(plan_path)
        logger.info("Saved updated plan to %s", plan_path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    # Step 11: Reset R1 trigger
    try:
        sheets.reset_tiktok_content_regen_trigger()
    except Exception as e:
        logger.warning("Failed to reset R1 trigger (non-fatal): %s", e)

    # Step 12: Slack notification
    summary_parts = []
    if successes:
        details = [f"{cid}({len(sls)} slides)" for cid, sls in successes]
        summary_parts.append(f"{len(successes)} regenerated ({', '.join(details)})")
    if failures:
        failed_ids = [cid for cid, _ in failures]
        summary_parts.append(f"{len(failures)} FAILED ({', '.join(failed_ids)})")
    if skipped:
        summary_parts.append(f"{len(skipped)} skipped")

    try:
        slack = slack or SlackNotify()
        slack.notify(
            f"TikTok content regen complete: {' + '.join(summary_parts)}. "
            f"Review updated slides in Content Queue tab.",
        )
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    logger.info(
        "TikTok content regen complete: %d successes, %d failures, %d skipped.",
        len(successes), len(failures), len(skipped),
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        regen_content()
    except Exception as e:
        logger.error("TikTok content regen failed: %s", e, exc_info=True)
        sys.exit(1)
