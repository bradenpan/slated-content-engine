"""
Content Queue Publisher

Reads generation results, uploads pin images to Google Drive for
inline preview, extracts blog post summaries, and writes the Content
Queue to Google Sheets with IMAGE() formulas. Sends Slack notification.

Runs as a separate workflow step after pin generation completes.
"""

import json
import logging
from pathlib import Path

import yaml

from src.apis.drive_api import DriveAPI, DriveAPIError
from src.apis.sheets_api import SheetsAPI, TAB_CONTENT_QUEUE
from src.apis.slack_notify import SlackNotify

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GENERATED_BLOG_DIR = DATA_DIR / "generated" / "blog"
PIN_OUTPUT_DIR = DATA_DIR / "generated" / "pins"


def publish() -> None:
    """
    Read generation results, upload pin images to Drive, write Content
    Queue with inline previews, and send Slack notification.
    """
    # Load blog generation results
    blog_results_path = DATA_DIR / "blog-generation-results.json"
    blog_results: dict = {}
    if blog_results_path.exists():
        try:
            blog_results = json.loads(blog_results_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load blog generation results: %s", e)

    # Load pin generation results
    pin_results_path = DATA_DIR / "pin-generation-results.json"
    pin_data: dict = {}
    if pin_results_path.exists():
        try:
            pin_data = json.loads(pin_results_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load pin generation results: %s", e)

    generated_pins = pin_data.get("generated", [])

    # Upload pin images to Google Drive for Sheet preview
    pin_image_urls: dict[str, str] = {}
    drive_failed = False
    try:
        drive = DriveAPI()
        pin_image_urls = drive.upload_pin_images(generated_pins, PIN_OUTPUT_DIR)

        # Save Drive URLs back to pin-generation-results.json so the regen
        # workflow can download hero images on a fresh runner
        if pin_image_urls:
            for pin in generated_pins:
                pid = pin.get("pin_id", "")
                if pid in pin_image_urls:
                    pin["_drive_image_url"] = pin_image_urls[pid]
            try:
                pin_results_path.write_text(
                    json.dumps(pin_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                logger.info("Saved Drive URLs back to pin-generation-results.json")
            except OSError as e:
                logger.error("Failed to save Drive URLs to pin results: %s", e)

    except DriveAPIError as e:
        logger.error(
            "Drive upload failed, Content Queue will not have image previews: %s", e
        )
        drive_failed = True

    # Extract blog content previews from MDX frontmatter
    blog_previews: dict[str, str] = {}
    for post_id, post_data in blog_results.items():
        if post_data.get("status") != "success":
            continue
        slug = post_data.get("slug", "")
        if not slug:
            continue
        mdx_path = GENERATED_BLOG_DIR / f"{slug}.mdx"
        if mdx_path.exists():
            preview = _extract_frontmatter_description(mdx_path)
            if preview:
                blog_previews[post_id] = preview

    # Build blog post entries for the Sheet
    blog_entries = [
        {
            "post_id": post_id,
            "title": pdata.get("title", ""),
            "slug": pdata.get("slug", ""),
            "pillar": str(pdata.get("pillar", "")),
            "content_type": pdata.get("content_type", ""),
        }
        for post_id, pdata in blog_results.items()
        if pdata.get("status") == "success"
    ]

    # Build per-pin quality notes from quality gate metadata
    for pin in generated_pins:
        pin["_quality_note"] = _build_quality_note(pin)

    # Compute quality gate summary stats
    quality_gate_stats = _compute_quality_stats(generated_pins)

    logger.info(
        "Publishing Content Queue: %d blog posts, %d pins, %d image URLs, %d blog previews",
        len(blog_entries), len(generated_pins),
        len(pin_image_urls), len(blog_previews),
    )

    # Write to Google Sheets with IMAGE() formulas
    try:
        sheets = SheetsAPI()
        sheets.write_content_queue(
            blog_posts=blog_entries,
            pins=generated_pins,
            pin_image_urls=pin_image_urls,
            blog_previews=blog_previews,
            quality_gate_stats=quality_gate_stats,
        )

        # Set row heights for pin rows so images are visible
        # Pins come after the header row (1) + blog rows
        pin_start_row = 2 + len(blog_entries)  # 1-based
        if generated_pins:
            sheets.set_row_heights(
                TAB_CONTENT_QUEUE,
                start_row=pin_start_row,
                num_rows=len(generated_pins),
                height_px=200,
            )

        # Write regen trigger cells: M1 = label, N1 = trigger value
        try:
            sheets.sheets.values().update(
                spreadsheetId=sheets.sheet_id,
                range=f"'{TAB_CONTENT_QUEUE}'!M1:N1",
                valueInputOption="RAW",
                body={"values": [["Regen \u2192", "idle"]]},
            ).execute()
        except Exception as e:
            logger.warning("Failed to write regen trigger cells: %s", e)

    except Exception as e:
        logger.error("Failed to write Content Queue to Google Sheets: %s", e)

    # Send Slack notification
    try:
        slack = SlackNotify()
        slack.notify_content_ready(
            num_pins=len(generated_pins),
            num_blog_posts=len(blog_entries),
        )
        if drive_failed:
            slack.notify(
                "Warning: Drive image upload failed. Pin image previews will NOT "
                "appear in the Content Queue. Check workflow logs for details.",
                level="warning",
            )
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    logger.info("Content Queue published successfully")


def _extract_frontmatter_description(mdx_path: Path) -> str:
    """
    Parse YAML frontmatter from an MDX file and return the description.

    Args:
        mdx_path: Path to the MDX file.

    Returns:
        str: The description field from frontmatter, or empty string.
    """
    try:
        content = mdx_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return ""

        # Find the closing --- of frontmatter
        end_idx = content.index("---", 3)
        frontmatter_text = content[3:end_idx]
        frontmatter = yaml.safe_load(frontmatter_text)

        if not isinstance(frontmatter, dict):
            return ""

        description = frontmatter.get("description", "")
        return str(description)[:500]

    except (ValueError, yaml.YAMLError, OSError) as e:
        logger.warning("Failed to extract frontmatter from %s: %s", mdx_path, e)
        return ""


def _build_quality_note(pin: dict) -> str:
    """
    Build a human-readable quality note for a pin's Notes column.

    Examples:
        "7.5"                                          — passed first try
        "6.8 | Retry: initial candidates scored < 6.5" — retried
        "5.2 | LOW CONFIDENCE | hands visible"         — below threshold after retry
    """
    score = pin.get("image_quality_score")
    retries = pin.get("image_retries", 0)
    low_confidence = pin.get("image_low_confidence", False)
    issues = pin.get("image_quality_issues", [])

    if score is None:
        return ""

    parts = [f"{score:.1f}"]

    if retries > 0:
        original_source = pin.get("image_source_original", "")
        if original_source == "stock" and pin.get("image_source") == "ai_generated":
            parts.append("Fallback: stock -> AI")
        elif retries == 1:
            parts.append("Retry: initial candidates scored < 6.5")
        else:
            parts.append(f"Retries: {retries}")

    if low_confidence:
        parts.append("LOW CONFIDENCE")

    if issues:
        parts.append(", ".join(str(i) for i in issues[:3]))

    return " | ".join(parts)


def _compute_quality_stats(pins: list[dict]) -> dict:
    """
    Compute aggregate quality gate statistics across all pins.

    Returns:
        dict with stock_summary and ai_summary strings for the summary row.
    """
    stock_ranked = 0
    stock_retried = 0
    stock_fell_back = 0
    ai_validated = 0
    ai_regenerated = 0
    ai_low_conf = 0

    for pin in pins:
        original = pin.get("image_source_original", pin.get("image_source", ""))
        source = pin.get("image_source", "")
        has_score = pin.get("image_quality_score") is not None

        if original == "stock":
            if has_score:
                stock_ranked += 1
            if pin.get("image_retries", 0) > 0 and source != "ai_generated":
                stock_retried += 1
            if source == "ai_generated":
                stock_fell_back += 1
        elif original == "ai" or source == "ai_generated":
            if has_score and original != "stock":
                ai_validated += 1
            if pin.get("image_retries", 0) > 0 and original != "stock":
                ai_regenerated += 1
            if pin.get("image_low_confidence") and original != "stock":
                ai_low_conf += 1

    return {
        "stock_summary": (
            f"Stock: {stock_ranked} ranked, {stock_retried} retried, "
            f"{stock_fell_back} fell back to AI"
        ),
        "ai_summary": (
            f"AI: {ai_validated} validated, {ai_regenerated} regenerated, "
            f"{ai_low_conf} low_confidence"
        ),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    publish()
