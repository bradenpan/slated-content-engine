"""
Content Queue Publisher

Reads generation results, uploads pin images and blog hero images to
Google Cloud Storage (or Google Drive as fallback) for inline preview,
extracts blog post summaries, and writes the Content Queue to Google
Sheets with IMAGE() formulas. Sends Slack notification.

Runs as a separate workflow step after pin generation completes.
"""

import json
import logging
from pathlib import Path

import yaml

from src.apis.gcs_api import GcsAPI
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
    Read generation results, upload pin images to GCS (or Drive as
    fallback), write Content Queue with inline previews, and send
    Slack notification.
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

    # Upload pin images for Sheet preview (GCS primary, Drive fallback)
    pin_image_urls: dict[str, str] = {}
    blog_image_urls: dict[str, str] = {}
    upload_failed = False
    upload_backend = "none"

    # Try GCS first
    gcs = GcsAPI()
    if gcs.client:
        try:
            logger.info(
                "GCS API initialized. Uploading %d pin images from %s",
                len(generated_pins), PIN_OUTPUT_DIR,
            )
            pin_image_urls = gcs.upload_pin_images(generated_pins, PIN_OUTPUT_DIR)
            upload_backend = "gcs"
            logger.info("GCS upload complete: %d pin image URLs obtained", len(pin_image_urls))
        except Exception as e:
            logger.error("GCS upload failed: %s (%s)", e, type(e).__name__)
            pin_image_urls = {}

    # Fall back to Drive if GCS didn't produce results
    drive: DriveAPI | None = None
    if not pin_image_urls:
        try:
            drive = DriveAPI()
            logger.info(
                "Falling back to Drive. Uploading %d pin images from %s",
                len(generated_pins), PIN_OUTPUT_DIR,
            )
            pin_image_urls = drive.upload_pin_images(generated_pins, PIN_OUTPUT_DIR)
            upload_backend = "drive"
            logger.info("Drive upload complete: %d pin image URLs obtained", len(pin_image_urls))
        except DriveAPIError as e:
            logger.error(
                "Drive upload failed — no image previews in Content Queue. "
                "Error: %s | Check that Google Drive API is enabled in your "
                "GCP project and the service account has access.", e
            )
            upload_failed = True
        except Exception as e:
            logger.error(
                "Unexpected error during Drive upload: %s (%s)", e, type(e).__name__
            )
            upload_failed = True

    # Save image URLs back to pin-generation-results.json so the regen
    # workflow can download hero images on a fresh runner
    if pin_image_urls:
        for pin in generated_pins:
            pid = pin.get("pin_id", "")
            if pid in pin_image_urls:
                url = pin_image_urls[pid]
                if upload_backend == "gcs":
                    # GCS URLs work for both preview and direct download
                    pin["_drive_image_url"] = url
                    pin["_drive_download_url"] = url
                else:
                    # Drive thumbnail URL
                    pin["_drive_image_url"] = url
                    if "id=" in url:
                        _fid = url.split("id=")[1].split("&")[0]
                        pin["_drive_download_url"] = (
                            f"https://drive.google.com/uc?id={_fid}&export=download"
                        )
        try:
            pin_results_path.write_text(
                json.dumps(pin_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Saved %s URLs back to pin-generation-results.json", upload_backend)
        except OSError as e:
            logger.error("Failed to save image URLs to pin results: %s", e)

    # Upload blog hero images for Sheet preview
    if upload_backend == "gcs" and gcs.client and blog_results:
        try:
            blog_image_urls = gcs.upload_blog_hero_images(blog_results, PIN_OUTPUT_DIR)
            logger.info("Uploaded %d blog hero images to GCS", len(blog_image_urls))
        except Exception as e:
            logger.warning("GCS blog hero image upload failed (non-critical): %s", e)
    elif drive and not upload_failed and blog_results:
        try:
            blog_image_urls = _upload_blog_hero_images(
                drive, blog_results, generated_pins, PIN_OUTPUT_DIR,
            )
            logger.info("Uploaded %d blog hero images to Drive", len(blog_image_urls))
        except Exception as e:
            logger.warning("Blog hero image upload failed (non-critical): %s", e)

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
        "Publishing Content Queue: %d blog posts, %d pins, %d pin image URLs, "
        "%d blog image URLs, %d blog previews",
        len(blog_entries), len(generated_pins),
        len(pin_image_urls), len(blog_image_urls), len(blog_previews),
    )

    # Write to Google Sheets with IMAGE() formulas
    try:
        sheets = SheetsAPI()
        sheets.write_content_queue(
            blog_posts=blog_entries,
            pins=generated_pins,
            pin_image_urls=pin_image_urls,
            blog_image_urls=blog_image_urls,
            blog_previews=blog_previews,
            quality_gate_stats=quality_gate_stats,
        )

        # Set row heights for rows with images so previews are visible
        # Blog rows with images come first (after header)
        blogs_with_images = sum(1 for e in blog_entries if e["post_id"] in blog_image_urls)
        if blogs_with_images:
            sheets.set_row_heights(
                TAB_CONTENT_QUEUE,
                start_row=2,  # First data row (1-based)
                num_rows=blogs_with_images,
                height_px=150,
            )

        # Pin rows come after all blog rows
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
        if upload_failed:
            slack.notify(
                "Warning: Image upload failed (GCS + Drive). Image previews will NOT "
                "appear in the Content Queue. Check workflow logs for details. "
                "Verify GCS bucket exists and service account has access.",
                level="warning",
            )
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    logger.info("Content Queue published successfully")


def _upload_blog_hero_images(
    drive: DriveAPI,
    blog_results: dict,
    generated_pins: list[dict],
    pins_dir: Path,
) -> dict[str, str]:
    """
    Upload blog hero images to Drive for Sheet preview thumbnails.

    For each blog post, find the hero image from the first associated pin's
    source image (saved as {pin_id}-hero.{ext} or {slug}-hero.{ext}).

    Args:
        drive: Initialized DriveAPI instance.
        blog_results: Blog generation results dict (post_id -> data).
        generated_pins: List of generated pin data dicts.
        pins_dir: Directory containing pin and hero images.

    Returns:
        dict: post_id -> public Drive thumbnail URL.
    """
    # Build post_id -> first pin mapping (each blog may have multiple pins)
    post_to_pin: dict[str, dict] = {}
    for pin in generated_pins:
        source_id = pin.get("source_post_id", "")
        if source_id and source_id not in post_to_pin:
            post_to_pin[source_id] = pin

    urls: dict[str, str] = {}
    for post_id, post_data in blog_results.items():
        if post_data.get("status") != "success":
            continue

        slug = post_data.get("slug", "")
        pin = post_to_pin.get(post_id)

        hero_path = _find_hero_image(slug, pin, pins_dir)
        if not hero_path:
            logger.debug("No hero image found for blog %s (slug=%s)", post_id, slug)
            continue

        try:
            url = drive.upload_image(hero_path, f"blog-hero-{slug}.jpg")
            urls[post_id] = url
            logger.debug("Uploaded blog hero for %s: %s", post_id, url[:60])
        except DriveAPIError as e:
            logger.warning("Failed to upload hero image for blog %s: %s", post_id, e)

    return urls


def _find_hero_image(
    slug: str,
    pin: dict | None,
    pins_dir: Path,
) -> Path | None:
    """
    Find the hero image file for a blog post.

    Searches for:
    1. {slug}-hero.{ext} in pins_dir (created by generate_pin_content.py)
    2. {pin_id}-hero.{ext} in pins_dir (original pin hero image)
    3. {slug}.{ext} in the blog output dir

    Args:
        slug: Blog post slug.
        pin: First associated pin data dict (may be None).
        pins_dir: Directory containing pin images.

    Returns:
        Path if found, None otherwise.
    """
    extensions = [".jpg", ".jpeg", ".png", ".webp"]

    # Try slug-named hero image first
    if slug:
        for ext in extensions:
            candidate = pins_dir / f"{slug}-hero{ext}"
            if candidate.exists():
                return candidate

    # Try pin_id-named hero image
    if pin:
        pin_id = pin.get("pin_id", "")
        if pin_id:
            for ext in extensions:
                candidate = pins_dir / f"{pin_id}-hero{ext}"
                if candidate.exists():
                    return candidate

        # Try the hero_image_path stored in pin data
        hero_path_str = pin.get("hero_image_path")
        if hero_path_str:
            hero_path = Path(hero_path_str)
            if hero_path.exists():
                return hero_path

    # Try slug-named image in blog output dir
    if slug:
        blog_dir = pins_dir.parent / "blog"
        for ext in extensions:
            candidate = blog_dir / f"{slug}{ext}"
            if candidate.exists():
                return candidate

    return None


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
