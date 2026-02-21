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
    try:
        drive = DriveAPI()
        pin_image_urls = drive.upload_pin_images(generated_pins, PIN_OUTPUT_DIR)
    except DriveAPIError as e:
        logger.error(
            "Drive upload failed, Content Queue will not have image previews: %s", e
        )

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

    except Exception as e:
        logger.error("Failed to write Content Queue to Google Sheets: %s", e)

    # Send Slack notification
    try:
        slack = SlackNotify()
        slack.notify_content_ready(
            num_pins=len(generated_pins),
            num_blog_posts=len(blog_entries),
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    publish()
