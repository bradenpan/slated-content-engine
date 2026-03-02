"""One-time recovery script for W9-21 through W9-28 pin images.

DELETE THIS FILE after W9 pins have been successfully posted (by Mar 4, 2026).
It is a one-time recovery tool, not part of the ongoing pipeline.

W9 pin posting failed because W10 content generation deleted ALL W* images
from GCS (the old delete_old_images(prefix="W") behavior). This script
re-downloads hero images, re-renders the 8 affected pins, uploads them
to GCS, and updates pin-schedule.json with the new URLs.

Requirements:
    - UNSPLASH_ACCESS_KEY env var (for downloading 5 Unsplash hero images)
    - GOOGLE_SHEETS_CREDENTIALS_JSON env var (for GCS upload)
    - ANTHROPIC_API_KEY + OPENAI_API_KEY (only if W9-24 AI image needs re-gen)
    - Node.js + Playwright/Chromium (for pin rendering via PinAssembler)

Usage:
    python -m src.recover_w9_pins
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional, Union

import requests

from src.paths import PROJECT_ROOT, DATA_DIR, PIN_OUTPUT_DIR
from src.pin_assembler import PinAssembler
from src.apis.gcs_api import GcsAPI
from src.utils.safe_get import safe_get

logger = logging.getLogger(__name__)

# Pins to recover
RECOVERY_PIN_IDS = [f"W9-{i}" for i in range(21, 29)]

# Full git commit hash for pin generation results
GIT_COMMIT = "10b5ba6677a5cec6a4775cb79966030856df30c7"

# Image download settings
DOWNLOAD_TIMEOUT = 30

# Sentinel to distinguish "no image needed" from "download failed".
# Only compared via `is` identity checks — never used as an actual path.
_IMAGE_NOT_NEEDED = object()


def _check_dependencies() -> list[str]:
    """Check that required env vars and modules are available.

    Returns:
        list of missing dependency descriptions (empty if all OK).
    """
    missing = []
    if not os.environ.get("UNSPLASH_ACCESS_KEY"):
        missing.append("UNSPLASH_ACCESS_KEY env var (needed for Unsplash image downloads)")
    if not os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON"):
        missing.append("GOOGLE_SHEETS_CREDENTIALS_JSON env var (needed for GCS upload)")
    try:
        from src.generate_pin_content import build_template_context  # noqa: F401
    except ImportError as e:
        missing.append(f"Pipeline dependency: {e}")
    return missing


def extract_w9_data_from_git() -> dict[str, dict]:
    """Extract W9-21 through W9-28 pin data from git history.

    Returns:
        dict: pin_id -> pin data dict
    """
    logger.info("Extracting W9 pin data from git commit %s", GIT_COMMIT[:10])

    result = subprocess.run(
        ["git", "show", f"{GIT_COMMIT}:data/pin-generation-results.json"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to extract pin data from git: {result.stderr}"
        )

    data = json.loads(result.stdout)

    # Handle both list and dict-with-generated-key formats
    if isinstance(data, dict):
        pins = safe_get(data, "generated", [])
    else:
        pins = data

    pin_map = {}
    for pin in pins:
        pin_id = safe_get(pin, "pin_id", "")
        if pin_id in RECOVERY_PIN_IDS:
            pin_map[pin_id] = pin

    found = sorted(pin_map.keys())
    logger.info("Found %d/%d pins in git history: %s", len(pin_map), len(RECOVERY_PIN_IDS), found)

    missing = set(RECOVERY_PIN_IDS) - set(pin_map.keys())
    if missing:
        logger.warning("Missing pins in git history: %s", sorted(missing))

    return pin_map


def _download_to_path(url: str, output_path: Path) -> Path:
    """Download a URL to a local file atomically.

    Writes to a temp file first, then renames on success to avoid
    leaving corrupt partial files on disk.

    Raises:
        requests.RequestException: on download failure.
        ValueError: if downloaded file is suspiciously small.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in the same directory (same filesystem for atomic rename)
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(output_path.parent),
        suffix=output_path.suffix,
    )
    tmp_path = Path(tmp_path_str)
    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        resp.raise_for_status()

        with os.fdopen(fd, "wb") as f:
            fd = -1  # os.fdopen took ownership; don't double-close in except
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = tmp_path.stat().st_size
        if file_size < 1000:
            raise ValueError(
                f"Downloaded file suspiciously small ({file_size} bytes), likely invalid"
            )

        # Atomic rename
        tmp_path.replace(output_path)
        return output_path

    except BaseException:
        # Clean up temp file on any failure
        if fd >= 0:
            os.close(fd)
        tmp_path.unlink(missing_ok=True)
        raise


def _download_unsplash(photo_id: str, output_path: Path) -> Path:
    """Download an Unsplash photo using the Unsplash API.

    The short photo ID (e.g., 'H-D-0UOgzMc') cannot be used directly as a CDN
    path. We must call the Unsplash API to resolve the actual CDN download URL.

    Requires UNSPLASH_ACCESS_KEY env var.

    Raises:
        RuntimeError: if API key missing or API call fails.
    """
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if not access_key:
        raise RuntimeError("UNSPLASH_ACCESS_KEY env var not set")

    # Get photo metadata including CDN URLs
    api_url = f"https://api.unsplash.com/photos/{photo_id}"
    resp = requests.get(
        api_url,
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=DOWNLOAD_TIMEOUT,
    )
    resp.raise_for_status()
    photo_data = resp.json()

    # Use the "regular" size (1080px wide) — good for 1000x1500 pin rendering.
    # Guard against null fields in the API response (or → {} avoids chained None).
    urls = photo_data.get("urls") or {}
    cdn_url = urls.get("regular") or ""
    if not cdn_url:
        # Fall back to raw URL with size parameters
        cdn_url = urls.get("raw") or ""
        if cdn_url:
            cdn_url = f"{cdn_url}&w=1080&h=1620&fit=crop&q=80"

    if not cdn_url:
        raise RuntimeError(f"No download URL found for Unsplash photo {photo_id}")

    logger.info("Unsplash API resolved %s -> %s", photo_id, cdn_url[:80])
    return _download_to_path(cdn_url, output_path)


def _download_pexels(photo_id: str, output_path: Path) -> Path:
    """Download a Pexels photo.

    Uses the Pexels API (GET /v1/photos/{id}) if PEXELS_API_KEY is set to get
    the verified CDN URL. Falls back to the common CDN path format if no key.

    Raises:
        requests.RequestException: on download failure.
        RuntimeError: if API call fails and fallback also fails.
    """
    pexels_key = os.environ.get("PEXELS_API_KEY", "")

    if pexels_key:
        # Use the API to get the verified download URL
        logger.info("Pexels API: resolving photo %s", photo_id)
        resp = requests.get(
            f"https://api.pexels.com/v1/photos/{photo_id}",
            headers={"Authorization": pexels_key},
            timeout=DOWNLOAD_TIMEOUT,
        )
        resp.raise_for_status()
        photo_data = resp.json()
        url = (photo_data.get("src") or {}).get("large2x") or ""
        if not url:
            url = (photo_data.get("src") or {}).get("original") or ""
        if not url:
            raise RuntimeError(f"Pexels API returned no download URL for photo {photo_id}")
        logger.info("Pexels API resolved %s -> %s", photo_id, url[:80])
    else:
        # Fall back to common CDN path format (works for most photos)
        url = (
            f"https://images.pexels.com/photos/{photo_id}/"
            f"pexels-photo-{photo_id}.jpeg?w=1000&h=1500&fit=crop&q=80"
        )
        logger.info("Downloading Pexels photo %s (no API key, using CDN guess)", photo_id)

    return _download_to_path(url, output_path)


def download_hero_image(
    pin_id: str, pin_data: dict, output_dir: Path,
) -> Union[Path, object, None]:
    """Download the hero image for a pin from its original source.

    Args:
        pin_id: Pin identifier (e.g., "W9-21").
        pin_data: Pin data dict from git history.
        output_dir: Directory to save downloaded images.

    Returns:
        Path to downloaded image, _IMAGE_NOT_NEEDED sentinel if no image
        required, or None if download failed.
    """
    image_source = safe_get(pin_data, "image_source", "")
    image_id = safe_get(pin_data, "image_id", "")
    template = safe_get(pin_data, "template", "")

    # Infographic/template pins don't need hero images
    if template == "infographic-pin" or image_source == "template":
        logger.info("%s: infographic/template pin — no hero image needed", pin_id)
        return _IMAGE_NOT_NEEDED

    output_dir.mkdir(parents=True, exist_ok=True)

    # Warn about W9-24 data inconsistency
    if image_source == "ai_generated" and image_id and not image_id.startswith("ai_"):
        logger.warning(
            "%s: data inconsistency — image_source='ai_generated' but image_id='%s'. "
            "The AI hero from GCS is lost. Will attempt AI re-generation.",
            pin_id, image_id,
        )

    if image_source == "unsplash" and image_id.startswith("unsplash:"):
        photo_id = image_id.split(":", 1)[1]
        output_path = output_dir / f"{pin_id}-hero.jpg"
        try:
            return _download_unsplash(photo_id, output_path)
        except Exception as e:
            logger.error("%s: Unsplash download failed: %s", pin_id, e)
            return None

    elif image_source == "pexels" and image_id.startswith("pexels:"):
        photo_id = image_id.split(":", 1)[1]
        output_path = output_dir / f"{pin_id}-hero.jpg"
        try:
            return _download_pexels(photo_id, output_path)
        except Exception as e:
            logger.error("%s: Pexels download failed: %s", pin_id, e)
            return None

    elif image_source == "ai_generated":
        logger.info("%s: AI-generated image — will re-generate", pin_id)
        return _regenerate_ai_image(pin_id, pin_data, output_dir)

    else:
        logger.warning("%s: unknown image source '%s', skipping hero download", pin_id, image_source)
        return None


def _regenerate_ai_image(pin_id: str, pin_data: dict, output_dir: Path) -> Optional[Path]:
    """Re-generate an AI hero image for a pin.

    Requires ClaudeAPI and ImageGenAPI to be configured with valid API keys.
    """
    try:
        from src.apis.claude_api import ClaudeAPI
        from src.apis.image_gen import ImageGenAPI
        from src.generate_pin_content import source_ai_image

        claude = ClaudeAPI()
        image_gen = ImageGenAPI()

        pin_spec = {
            "pin_id": pin_id,
            "pin_template": safe_get(pin_data, "template", ""),
            "primary_keyword": safe_get(pin_data, "primary_keyword", ""),
            "secondary_keywords": safe_get(pin_data, "secondary_keywords", []),
            "pin_topic": safe_get(pin_data, "title", ""),
        }

        image_path, _, _, _ = source_ai_image(pin_spec, claude, image_gen, output_dir)
        return image_path

    except ImportError as e:
        logger.error(
            "%s: AI re-generation requires anthropic + openai packages: %s",
            pin_id, e,
        )
        return None
    except Exception as e:
        logger.error("%s: AI image re-generation failed: %s", pin_id, e)
        logger.info(
            "%s: manually place a hero image at %s/%s-hero.png and re-run",
            pin_id, output_dir, pin_id,
        )
        return None


def render_pin(
    pin_id: str,
    pin_data: dict,
    hero_image_path: Optional[Path],
    assembler: PinAssembler,
    output_dir: Path,
) -> Optional[Path]:
    """Re-render a single pin image.

    Args:
        pin_id: Pin identifier.
        pin_data: Pin data from git history.
        hero_image_path: Path to the hero image, _IMAGE_NOT_NEEDED for
            template-only pins, or None if download failed.
        assembler: PinAssembler instance.
        output_dir: Directory for rendered pin PNGs.

    Returns:
        Path to the rendered PNG, or None on failure.
    """
    template_type = safe_get(pin_data, "template", "recipe-pin")
    text_overlay = safe_get(pin_data, "text_overlay", {})

    # Determine actual hero path (None for template-only, None on failure)
    needs_hero = template_type != "infographic-pin"
    if hero_image_path is _IMAGE_NOT_NEEDED:
        actual_hero = None
    elif hero_image_path is None and needs_hero:
        logger.error(
            "%s: skipping render — hero image download failed and %s template requires one",
            pin_id, template_type,
        )
        return None
    else:
        actual_hero = hero_image_path

    # Extract headline/subtitle from text_overlay
    if isinstance(text_overlay, dict):
        headline = safe_get(text_overlay, "headline", "")
        subtitle = safe_get(text_overlay, "sub_text", "")
    else:
        headline = str(text_overlay) if text_overlay else ""
        subtitle = ""

    from src.generate_pin_content import build_template_context

    # Build template-specific context (reusing the pipeline's logic)
    pin_copy = {
        "title": safe_get(pin_data, "title", ""),
        "description": safe_get(pin_data, "description", ""),
        "alt_text": safe_get(pin_data, "alt_text", ""),
        "text_overlay": text_overlay,
    }
    pin_spec = {
        "pin_id": pin_id,
        "pin_template": template_type,
        "primary_keyword": safe_get(pin_data, "primary_keyword", ""),
        "pin_topic": safe_get(pin_data, "title", ""),
        "template_variant": 1,
    }

    extra_context = build_template_context(template_type, pin_copy, pin_spec, actual_hero)

    output_path = output_dir / f"{pin_id}.png"
    logger.info("%s: rendering %s pin -> %s", pin_id, template_type, output_path.name)

    try:
        rendered_path = assembler.assemble_pin(
            template_type=template_type,
            hero_image_path=str(actual_hero) if actual_hero else None,
            headline=headline,
            subtitle=subtitle,
            variant=1,
            output_path=output_path,
            extra_context=extra_context,
        )

        if not rendered_path.exists():
            logger.error("%s: render produced no output file", pin_id)
            return None

        logger.info("%s: rendered successfully (%d bytes)", pin_id, rendered_path.stat().st_size)
        return rendered_path

    except Exception as e:
        logger.error("%s: rendering failed: %s", pin_id, e)
        return None


def upload_pins_to_gcs(rendered_pins: dict[str, Path], gcs: GcsAPI) -> dict[str, str]:
    """Upload rendered pin images to GCS individually (no bulk delete).

    Args:
        rendered_pins: pin_id -> local path mapping.
        gcs: GcsAPI instance.

    Returns:
        dict: pin_id -> public GCS URL mapping.
    """
    url_map: dict[str, str] = {}

    for pin_id, local_path in sorted(rendered_pins.items()):
        logger.info("%s: uploading to GCS...", pin_id)
        url = gcs.upload_image(local_path)
        if url:
            url_map[pin_id] = url
            logger.info("%s: uploaded -> %s", pin_id, url)
        else:
            logger.error("%s: GCS upload failed", pin_id)

    return url_map


def update_pin_schedule(new_urls: dict[str, str]) -> None:
    """Update pin-schedule.json with new GCS image URLs.

    Uses atomic write (tmp + rename) to avoid corruption on failure.
    Warns about any pin_ids in new_urls that are missing from the schedule.

    Args:
        new_urls: pin_id -> new GCS URL mapping.
    """
    schedule_path = DATA_DIR / "pin-schedule.json"
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))

    updated = 0
    found_ids: set[str] = set()
    for pin in schedule:
        pin_id = safe_get(pin, "pin_id", "")
        if pin_id in new_urls:
            pin["image_url"] = new_urls[pin_id]
            updated += 1
            found_ids.add(pin_id)
            logger.info("%s: image_url updated", pin_id)

    # Warn about pins not found in schedule
    missing_from_schedule = set(new_urls.keys()) - found_ids
    for pin_id in sorted(missing_from_schedule):
        logger.warning("%s: not found in pin-schedule.json — URL not saved", pin_id)

    if updated:
        tmp = schedule_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(schedule, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp.replace(schedule_path)
        logger.info("Updated %d pin URLs in %s", updated, schedule_path.name)
    else:
        logger.warning("No pins updated in pin-schedule.json")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    print("=" * 60)
    print("W9 Pin Recovery — Re-render & Re-upload W9-21 through W9-28")
    print("=" * 60)
    print()

    # Warn if past the expected deletion date
    if date.today() > date(2026, 3, 4):
        print("WARNING: This script was intended for use by Mar 4, 2026.")
        print("         If W9 pins posted successfully, delete this file.\n")

    # Check dependencies early
    missing = _check_dependencies()
    if missing:
        print("ERROR: Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nSet the required env vars and try again.")
        sys.exit(1)

    # Step 1: Extract pin data from git history
    print("[Step 1/5] Extracting pin data from git history...")
    pin_data_map = extract_w9_data_from_git()
    if not pin_data_map:
        print("ERROR: No W9 pin data found in git history. Aborting.")
        sys.exit(1)
    print(f"  Found {len(pin_data_map)} pins\n")

    # Ensure output directory exists
    PIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 2: Download hero images
    print("[Step 2/5] Downloading hero images...")
    hero_images: dict[str, Union[Path, object, None]] = {}
    for pin_id in sorted(pin_data_map.keys()):
        pin_data = pin_data_map[pin_id]
        hero_path = download_hero_image(pin_id, pin_data, PIN_OUTPUT_DIR)
        hero_images[pin_id] = hero_path

    # Report download results
    downloaded = sum(1 for p in hero_images.values() if p and p is not _IMAGE_NOT_NEEDED)
    not_needed = sum(1 for p in hero_images.values() if p is _IMAGE_NOT_NEEDED)
    failed = sum(1 for p in hero_images.values() if p is None)
    print(f"  Downloaded: {downloaded}, Not needed: {not_needed}, Failed: {failed}\n")

    # Step 3: Re-render pins
    print("[Step 3/5] Rendering pin images...")
    assembler = PinAssembler()
    rendered_pins: dict[str, Path] = {}
    for pin_id in sorted(pin_data_map.keys()):
        pin_data = pin_data_map[pin_id]
        hero_path = hero_images.get(pin_id)
        rendered = render_pin(pin_id, pin_data, hero_path, assembler, PIN_OUTPUT_DIR)
        if rendered:
            rendered_pins[pin_id] = rendered
    print(f"  Rendered {len(rendered_pins)}/{len(pin_data_map)} pins\n")

    if not rendered_pins:
        print("ERROR: No pins rendered successfully. Aborting.")
        sys.exit(1)

    # Step 4: Upload to GCS
    print("[Step 4/5] Uploading to GCS...")
    gcs = GcsAPI()
    if not gcs.is_available:
        print("ERROR: GCS client not available. Check GOOGLE_SHEETS_CREDENTIALS_JSON env var.")
        print("Rendered pins are saved locally in:", PIN_OUTPUT_DIR)
        sys.exit(1)

    new_urls = upload_pins_to_gcs(rendered_pins, gcs)
    print(f"  Uploaded {len(new_urls)}/{len(rendered_pins)} pins\n")

    # Print preview URLs and summary
    print("Preview URLs:")
    print("-" * 60)
    for pin_id in sorted(new_urls.keys()):
        print(f"  {pin_id}: {new_urls[pin_id]}")
    print()

    failed_pins = set(pin_data_map.keys()) - set(new_urls.keys())
    if failed_pins:
        print(f"WARNING: {len(failed_pins)} pins failed: {sorted(failed_pins)}")
        print()

    # Write GitHub Actions job summary if running in CI
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as sf:
            sf.write("## W9 Pin Recovery Results\n\n")
            sf.write(f"**Rendered:** {len(rendered_pins)}/{len(pin_data_map)} pins\n\n")
            sf.write(f"**Uploaded:** {len(new_urls)}/{len(rendered_pins)} pins\n\n")
            if failed_pins:
                sf.write(f"**Failed:** {sorted(failed_pins)}\n\n")
            sf.write("### Pin Preview URLs\n\n")
            sf.write("| Pin ID | GCS Image URL |\n")
            sf.write("|--------|---------------|\n")
            for pin_id in sorted(new_urls.keys()):
                url = new_urls[pin_id]
                sf.write(f"| {pin_id} | [View Image]({url}) |\n")
            sf.write("\n")

    # Step 5: Update pin-schedule.json
    ci_mode = os.environ.get("CI", "") == "true"
    if ci_mode:
        print("[Step 5/5] Updating pin-schedule.json (CI mode, auto-confirm)...")
        update_pin_schedule(new_urls)
        print("  pin-schedule.json updated successfully!")
    else:
        print("[Step 5/5] Update pin-schedule.json?")
        answer = input("  Type 'yes' to update, anything else to skip: ").strip().lower()
        if answer == "yes":
            update_pin_schedule(new_urls)
            print("  pin-schedule.json updated successfully!")
        else:
            print("  Skipped. You can manually update pin-schedule.json later.")
            print("  URLs to use:")
            for pin_id, url in sorted(new_urls.items()):
                print(f"    {pin_id}: {url}")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
