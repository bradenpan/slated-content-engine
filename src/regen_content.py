"""
Content Regeneration Script

Reads regen requests from the Content Queue (rows where status starts with
'regen'), regenerates the flagged images and/or copy, updates the Sheet
rows in-place, and sends a Slack notification.

Regen types:
- regen_image: Re-source image + re-render pin with existing text overlay.
- regen_copy:  Re-generate copy + re-render pin with existing hero image.
- regen:       Both — new image + new copy + full re-render.

Blog rows support regen_image only (re-source hero photo, upload to GCS).
Blog copy regen is not supported — blog text lives in MDX files.

User feedback from column L is incorporated into the regeneration prompts
so the new output addresses the reviewer's specific concerns.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.apis.claude_api import ClaudeAPI
from src.apis.drive_api import DriveAPI
from src.apis.gcs_api import GcsAPI
from src.apis.image_gen import ImageGenAPI
from src.apis.image_stock import ImageStockAPI
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify
from src.generate_pin_content import (
    generate_copy_batch,
    load_used_image_ids,
    source_image,
    _load_brand_voice,
    _load_keyword_targets,
    build_template_context,
)
from src.pin_assembler import PinAssembler

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PIN_OUTPUT_DIR = DATA_DIR / "generated" / "pins"


def regen() -> None:
    """
    Main entry point for the regeneration workflow.

    1. Read regen requests from the Content Queue.
    2. Load pin-generation-results.json for canonical pin data.
    3. Regenerate image, copy, or both for each flagged item.
    4. Update the Sheet row in-place with new content.
    5. Update pin-generation-results.json.
    6. Reset the regen trigger and send Slack notification.
    """
    # Initialize API clients
    sheets = SheetsAPI()
    claude = ClaudeAPI()
    stock_api = ImageStockAPI()
    image_gen_api = ImageGenAPI()
    assembler = PinAssembler()
    gcs = GcsAPI()
    drive = DriveAPI()
    slack = SlackNotify()

    used_image_ids = load_used_image_ids()
    brand_voice = _load_brand_voice()
    keyword_targets = _load_keyword_targets()

    # Step 1: Read regen requests
    requests = sheets.read_regen_requests()
    if not requests:
        logger.info("No regen requests found. Nothing to do.")
        sheets.reset_regen_trigger()
        return

    logger.info("Processing %d regen requests", len(requests))

    # Step 2: Load canonical pin data
    pin_results_path = DATA_DIR / "pin-generation-results.json"
    pin_results: dict = {}
    if pin_results_path.exists():
        try:
            pin_results = json.loads(pin_results_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load pin generation results: %s", e)

    generated_pins = pin_results.get("generated", [])
    pin_index = {p["pin_id"]: p for p in generated_pins if "pin_id" in p}

    # Load blog generation results (for blog image regen)
    blog_results_path = DATA_DIR / "blog-generation-results.json"
    blog_results: dict = {}
    blog_results_dirty = False
    if blog_results_path.exists():
        try:
            blog_results = json.loads(blog_results_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load blog generation results: %s", e)

    # Step 3: Process each regen request
    regen_results: list[dict] = []

    for req in requests:
        item_id = req["id"]
        regen_type = req["status"]  # regen_image, regen_copy, or regen
        feedback = req.get("feedback", "")
        item_type = req.get("type", "pin")
        row_index = req["row_index"]

        logger.info(
            "Regenerating %s for %s (type=%s, feedback='%s')",
            regen_type, item_id, item_type, feedback[:80],
        )

        # --- Blog image regen ---
        if item_type == "blog":
            # Blog copy regen is not supported (blog text is MDX)
            if regen_type == "regen_copy":
                logger.warning("Blog copy regen not supported for %s", item_id)
                try:
                    sheets.update_content_row(
                        row_index=row_index,
                        status="pending_review",
                        notes="Blog copy regen not supported — only image regen available",
                        feedback="",
                    )
                except Exception as e:
                    logger.error("Failed to update blog row %s: %s", item_id, e)
                regen_results.append({
                    "pin_id": item_id,
                    "type": item_type,
                    "regen_type": regen_type,
                    "old_score": None,
                    "new_score": None,
                    "error": "Blog copy regen not supported",
                })
                continue

            # For "regen" (both), treat as regen_image with a note
            effective_regen_type = "regen_image"

            blog_data = blog_results.get(item_id)
            if not blog_data:
                logger.warning("Blog data not found for %s in blog-generation-results.json", item_id)
                try:
                    sheets.update_content_row(
                        row_index=row_index,
                        status="pending_review",
                        notes="Regen failed — blog data not found in results JSON",
                        feedback="",
                    )
                except Exception:
                    pass
                regen_results.append({
                    "pin_id": item_id,
                    "type": item_type,
                    "regen_type": regen_type,
                    "old_score": None,
                    "new_score": None,
                    "error": "Blog data not found",
                })
                continue

            try:
                blog_result = _regen_blog_image(
                    blog_data=blog_data,
                    post_id=item_id,
                    feedback=feedback,
                    claude=claude,
                    stock_api=stock_api,
                    image_gen_api=image_gen_api,
                    gcs=gcs,
                    used_image_ids=used_image_ids,
                )
            except Exception as e:
                logger.error("Failed to regenerate blog image for %s: %s", item_id, e)
                try:
                    sheets.update_content_row(
                        row_index=row_index,
                        status="pending_review",
                        notes=f"Blog regen failed — {str(e)[:100]}",
                        feedback="",
                    )
                except Exception:
                    pass
                regen_results.append({
                    "pin_id": item_id,
                    "type": item_type,
                    "regen_type": effective_regen_type,
                    "old_score": None,
                    "new_score": None,
                    "error": str(e)[:200],
                })
                continue

            new_image_url = blog_result.get("image_url")
            new_score = blog_result.get("quality_score")

            # Update blog_results in-place for later save
            if blog_result.get("image_source"):
                blog_data["_hero_image_source"] = blog_result["image_source"]
                blog_data["_hero_image_id"] = blog_result.get("image_id", "")
                blog_data["_hero_quality_score"] = new_score
                blog_data["_hero_regen_feedback"] = feedback
                blog_data["_hero_regen_timestamp"] = datetime.now().isoformat()
                blog_results_dirty = True

            # Update Content Queue row
            update_kwargs: dict = {
                "row_index": row_index,
                "status": "pending_review",
                "feedback": "",
            }
            if new_score is not None:
                update_kwargs["notes"] = f"Blog regen {new_score:.1f}"
            else:
                update_kwargs["notes"] = "Blog regen"
            if regen_type == "regen":
                update_kwargs["notes"] += " (image only — blog copy regen N/A)"

            if new_image_url:
                update_kwargs["thumbnail"] = f'=IMAGE("{new_image_url}")'

            try:
                sheets.update_content_row(**update_kwargs)
            except Exception as e:
                logger.error("Failed to update Sheet row for blog %s: %s", item_id, e)

            regen_results.append({
                "pin_id": item_id,
                "type": item_type,
                "regen_type": effective_regen_type,
                "old_score": None,
                "new_score": new_score,
            })
            continue

        # --- Pin regen ---
        pin_data = pin_index.get(item_id)
        if not pin_data:
            logger.warning(
                "Pin data not found for %s in pin-generation-results.json, skipping",
                item_id,
            )
            try:
                sheets.update_content_row(
                    row_index=row_index,
                    status="pending_review",
                    notes="Regen failed — pin data not found in results JSON",
                    feedback="",
                )
            except Exception:
                pass
            regen_results.append({
                "pin_id": item_id,
                "type": item_type,
                "regen_type": regen_type,
                "old_score": None,
                "new_score": None,
                "error": "Pin data not found",
            })
            continue

        old_score = pin_data.get("image_quality_score")

        try:
            result = _regen_item(
                pin_data=pin_data,
                regen_type=regen_type,
                feedback=feedback,
                claude=claude,
                stock_api=stock_api,
                image_gen_api=image_gen_api,
                assembler=assembler,
                gcs=gcs,
                drive=drive,
                used_image_ids=used_image_ids,
                brand_voice=brand_voice,
                keyword_targets=keyword_targets,
            )
        except Exception as e:
            logger.error("Failed to regenerate %s: %s", item_id, e)
            try:
                sheets.update_content_row(
                    row_index=row_index,
                    status="pending_review",
                    notes=f"Regen failed — {str(e)[:100]}",
                    feedback="",
                )
            except Exception:
                pass
            regen_results.append({
                "pin_id": item_id,
                "type": item_type,
                "regen_type": regen_type,
                "old_score": old_score,
                "new_score": None,
                "error": str(e)[:200],
            })
            continue

        new_pin_data = result["pin_data"]
        new_image_url = result.get("image_url")
        new_score = new_pin_data.get("image_quality_score")

        # Step 4: Update pin-generation-results.json in-place
        _update_pin_results(pin_data, new_pin_data, regen_type, feedback)

        # Step 5: Update Content Queue row
        update_kwargs: dict = {
            "row_index": row_index,
            "status": "pending_review",
            "feedback": "",  # Clear feedback after regen
        }

        # Build quality note for the Notes column
        quality_note = _build_regen_quality_note(new_pin_data)
        if new_pin_data.get("_copy_regen_no_rerender"):
            quality_note += " | WARNING: copy updated but pin image not re-rendered (hero unavailable)"
        if new_pin_data.get("_copy_regen_failed"):
            quality_note += " | WARNING: copy regen failed, original copy retained"
            update_kwargs["feedback"] = feedback  # preserve feedback for retry
        update_kwargs["notes"] = quality_note

        if regen_type in ("regen_image", "regen") and new_image_url:
            update_kwargs["thumbnail"] = f'=IMAGE("{new_image_url}")'

        if regen_type in ("regen_copy", "regen"):
            update_kwargs["title"] = new_pin_data.get("title", pin_data.get("title", ""))
            desc = new_pin_data.get("description", pin_data.get("description", ""))
            alt_text = new_pin_data.get("alt_text", "")
            if alt_text:
                desc = f"{desc}\n\nAlt: {alt_text}"
            update_kwargs["description"] = desc

        try:
            sheets.update_content_row(**update_kwargs)
        except Exception as e:
            logger.error("Failed to update Sheet row for %s: %s", item_id, e)

        warning = None
        if new_pin_data.get("_copy_regen_no_rerender"):
            warning = "Copy updated but pin image not re-rendered (hero unavailable)"
        if new_pin_data.get("_copy_regen_failed"):
            warning = "Copy regen failed, original copy retained"
        regen_results.append({
            "pin_id": item_id,
            "type": item_type,
            "regen_type": regen_type,
            "old_score": old_score,
            "new_score": new_score,
            "warning": warning,
        })

    # Step 6: Save updated pin results
    try:
        pin_results_path.write_text(
            json.dumps(pin_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved updated pin generation results")
    except OSError as e:
        logger.error("Failed to save pin generation results: %s", e)

    # Save updated blog results (if any blog regens ran)
    if blog_results_dirty:
        try:
            blog_results_path.write_text(
                json.dumps(blog_results, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Saved updated blog generation results")
        except OSError as e:
            logger.error("Failed to save blog generation results: %s", e)

    # Step 7: Reset trigger and notify
    try:
        sheets.reset_regen_trigger()
    except Exception as e:
        logger.warning("Failed to reset regen trigger: %s", e)

    if regen_results:
        try:
            slack.notify_regen_complete(regen_results)
        except Exception as e:
            logger.warning("Failed to send Slack notification: %s", e)

    succeeded = sum(1 for r in regen_results if not r.get("error"))
    failed = sum(1 for r in regen_results if r.get("error"))
    logger.info(
        "Regen complete: %d succeeded, %d failed out of %d requests",
        succeeded, failed, len(requests),
    )


def _regen_item(
    pin_data: dict,
    regen_type: str,
    feedback: str,
    claude: ClaudeAPI,
    stock_api: ImageStockAPI,
    image_gen_api: ImageGenAPI,
    assembler: PinAssembler,
    gcs: GcsAPI,
    drive: DriveAPI,
    used_image_ids: list[str],
    brand_voice: str,
    keyword_targets: dict,
) -> dict:
    """
    Regenerate a single content item (image, copy, or both).

    Returns:
        dict with "pin_data" (updated pin dict) and optional "image_url"
        (new public URL for the thumbnail, from GCS or Drive).
    """
    pin_id = pin_data["pin_id"]
    new_pin_data = dict(pin_data)
    new_image_url: Optional[str] = None

    # Build a pin_spec-like dict for the generation functions
    pin_spec = {
        "pin_id": pin_id,
        "pin_topic": pin_data.get("title", ""),
        "target_board": pin_data.get("board_name", ""),
        "pillar": pin_data.get("pillar"),
        "primary_keyword": pin_data.get("primary_keyword", ""),
        "secondary_keywords": pin_data.get("secondary_keywords", []),
        "pin_template": pin_data.get("template", "recipe-pin"),
        "template_variant": pin_data.get("template_variant", 1),
        "content_type": pin_data.get("content_type"),
        "funnel_layer": pin_data.get("funnel_layer", "discovery"),
        "image_source_tier": pin_data.get("image_source", "stock"),
    }

    if feedback:
        pin_spec["_regen_feedback"] = feedback

    # Determine what to regenerate
    do_image = regen_type in ("regen_image", "regen")
    do_copy = regen_type in ("regen_copy", "regen")

    # --- Regenerate copy ---
    if do_copy:
        logger.info("Regenerating copy for %s", pin_id)

        # Add feedback as copy guidance
        copy_spec = dict(pin_spec)
        if feedback:
            copy_spec["_copy_feedback"] = feedback

        try:
            copy_results = generate_copy_batch(
                claude=claude,
                pin_specs=[copy_spec],
                blog_context={},
                brand_voice=brand_voice,
                keyword_targets=keyword_targets,
            )
            if copy_results:
                new_copy = copy_results[0]
                new_pin_data["title"] = new_copy.get("title", new_pin_data.get("title", ""))
                new_pin_data["description"] = new_copy.get("description", new_pin_data.get("description", ""))
                new_pin_data["alt_text"] = new_copy.get("alt_text", new_pin_data.get("alt_text", ""))
                new_pin_data["text_overlay"] = new_copy.get("text_overlay", new_pin_data.get("text_overlay", ""))
                logger.info("Copy regenerated for %s: '%s'", pin_id, new_pin_data["title"][:60])
        except Exception as e:
            logger.error("Copy regeneration failed for %s: %s", pin_id, e)
            new_pin_data["_copy_regen_failed"] = True

    # --- Regenerate image ---
    if do_image:
        logger.info("Regenerating image for %s", pin_id)

        # Normalize image_source_tier for source_image()
        original_source = pin_data.get("image_source", "stock")
        if original_source in ("unsplash", "pexels", "stock"):
            image_tier = "stock"
        elif original_source == "ai_generated":
            image_tier = "ai"
        else:
            image_tier = "stock"

        PIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        image_path, image_source, image_id, quality_meta = source_image(
            pin_spec=pin_spec,
            image_tier=image_tier,
            claude=claude,
            stock_api=stock_api,
            image_gen_api=image_gen_api,
            used_image_ids=used_image_ids,
            output_dir=PIN_OUTPUT_DIR,
        )

        if image_path:
            new_pin_data["hero_image_path"] = str(image_path)
            new_pin_data["image_source"] = image_source
            new_pin_data["image_id"] = image_id
            new_pin_data["image_quality_score"] = quality_meta.get("image_quality_score")
            new_pin_data["image_retries"] = quality_meta.get("image_retries", 0)
            new_pin_data["image_low_confidence"] = quality_meta.get("image_low_confidence", False)
            new_pin_data["image_quality_issues"] = quality_meta.get("image_quality_issues", [])

            if image_id:
                used_image_ids.append(f"{image_source}:{image_id}")

    # --- Resolve hero image (download from GCS/Drive if not on disk) ---
    hero_path_str = new_pin_data.get("hero_image_path")
    hero_path = Path(hero_path_str) if hero_path_str else None

    if hero_path and not hero_path.exists():
        # Hero image not on disk (fresh runner). Try downloading.
        image_url = pin_data.get("_drive_image_url", "")
        PIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        downloaded = False

        # Try GCS download first (URL starts with storage.googleapis.com)
        if image_url and gcs.client and "storage.googleapis.com" in image_url:
            object_name = gcs.extract_object_name(image_url)
            if object_name:
                hero_path = PIN_OUTPUT_DIR / f"{pin_id}-hero-downloaded.png"
                result = gcs.download_image(object_name, hero_path)
                if result:
                    new_pin_data["hero_image_path"] = str(hero_path)
                    logger.info("Downloaded hero image from GCS for %s", pin_id)
                    downloaded = True
                else:
                    hero_path = None

        # Fall back to Drive download
        if not downloaded and image_url:
            drive_file_id = _extract_drive_file_id(image_url)
            if drive_file_id:
                try:
                    hero_path = PIN_OUTPUT_DIR / f"{pin_id}-hero-downloaded.png"
                    drive.download_image(drive_file_id, hero_path)
                    new_pin_data["hero_image_path"] = str(hero_path)
                    logger.info("Downloaded hero image from Drive for %s", pin_id)
                    downloaded = True
                except Exception as e:
                    logger.warning("Failed to download hero from Drive for %s: %s", pin_id, e)
                    hero_path = None

        if not downloaded:
            if not image_url:
                logger.warning("No image URL stored for %s, cannot re-render", pin_id)
            hero_path = None

    # --- Re-render the pin ---
    if hero_path and hero_path.exists():
        template_type = new_pin_data.get("template", "recipe-pin")
        text_overlay = new_pin_data.get("text_overlay", "")

        # Extract headline/subtitle from text_overlay (may be dict or str)
        if isinstance(text_overlay, dict):
            headline = text_overlay.get("headline", "")
            subtitle = text_overlay.get("sub_text", "")
        else:
            headline = str(text_overlay) if text_overlay else ""
            subtitle = new_pin_data.get("subtitle", "")

        # Build template-specific context for non-recipe templates
        pin_copy_like = {
            "title": new_pin_data.get("title", ""),
            "description": new_pin_data.get("description", ""),
            "text_overlay": text_overlay,
        }
        extra_context = build_template_context(
            template_type, pin_copy_like, pin_spec, hero_path,
        )

        try:
            rendered_pin_path = assembler.assemble_pin(
                template_type=template_type,
                hero_image_path=hero_path,
                headline=headline,
                subtitle=subtitle,
                variant=new_pin_data.get("template_variant", 1),
                output_path=PIN_OUTPUT_DIR / f"{pin_id}.png",
                extra_context=extra_context,
            )
            new_pin_data["image_path"] = str(rendered_pin_path)

            # Upload new rendered pin (GCS first, Drive fallback)
            old_image_url = pin_data.get("_drive_image_url", "")

            if gcs.client:
                # Delete old GCS object if it was stored there
                old_object_name = gcs.extract_object_name(old_image_url)
                if old_object_name:
                    try:
                        gcs.bucket.blob(old_object_name).delete()
                        logger.debug("Deleted old GCS object %s for %s", old_object_name, pin_id)
                    except Exception as e:
                        logger.warning("Failed to delete old GCS object for %s: %s", pin_id, e)

                new_image_url = gcs.upload_image(rendered_pin_path)
                if new_image_url:
                    # GCS URLs work for both preview and download
                    new_pin_data["_drive_image_url"] = new_image_url
                    new_pin_data["_drive_download_url"] = new_image_url
                    logger.info("Uploaded regen pin %s to GCS: %s", pin_id, new_image_url)

            if not new_image_url:
                # Fall back to Drive upload
                old_drive_file_id = _extract_drive_file_id(old_image_url)
                try:
                    new_image_url = drive.upload_image(rendered_pin_path)
                except Exception as e:
                    logger.warning("Drive upload also failed for %s: %s", pin_id, e)

                if old_drive_file_id:
                    try:
                        drive.drive.files().delete(fileId=old_drive_file_id).execute()
                        logger.debug("Deleted old Drive image %s for %s", old_drive_file_id, pin_id)
                    except Exception as e:
                        logger.warning("Failed to delete old Drive image for %s: %s", pin_id, e)

                if new_image_url and "id=" in new_image_url:
                    _fid = new_image_url.split("id=")[1].split("&")[0]
                    new_pin_data["_drive_image_url"] = (
                        f"https://drive.google.com/thumbnail?id={_fid}&sz=w400"
                    )
                    new_pin_data["_drive_download_url"] = (
                        f"https://drive.google.com/uc?id={_fid}&export=download"
                    )
                elif new_image_url:
                    new_pin_data["_drive_image_url"] = new_image_url
                if new_image_url:
                    logger.info("Uploaded regen pin %s to Drive: %s", pin_id, new_image_url)
        except Exception as e:
            logger.error("Pin assembly/upload failed for %s: %s", pin_id, e)
    else:
        logger.warning("No hero image available for %s, skipping re-render", pin_id)
        if do_copy:
            new_pin_data["_copy_regen_no_rerender"] = True

    return {"pin_data": new_pin_data, "image_url": new_image_url}


def _extract_drive_file_id(drive_url: str) -> str:
    """Extract the file ID from a Drive thumbnail URL."""
    # Format: https://drive.google.com/thumbnail?id=FILE_ID&sz=w400
    if "id=" not in drive_url:
        return ""
    try:
        file_id = drive_url.split("id=")[1].split("&")[0]
        return file_id
    except (IndexError, ValueError):
        return ""


def _regen_blog_image(
    blog_data: dict,
    post_id: str,
    feedback: str,
    claude: ClaudeAPI,
    stock_api: ImageStockAPI,
    image_gen_api: ImageGenAPI,
    gcs: GcsAPI,
    used_image_ids: list[str],
) -> dict:
    """
    Regenerate the hero image for a blog post.

    Blog images are raw stock/AI photos (not rendered through pin templates).
    The hero is saved with a slug-based filename so blog_deployer.py can
    find it at deploy time.

    Returns:
        dict with "image_url" (GCS public URL), "quality_score", "image_source",
        "image_id".  image_url is None if upload failed.
    """
    slug = blog_data.get("slug", "")
    title = blog_data.get("title", "")

    if not slug:
        raise ValueError(f"Blog {post_id} has no slug in blog-generation-results.json")

    logger.info("Regenerating blog hero image for %s (slug=%s)", post_id, slug)

    # Build a pin_spec-like dict for source_image()
    pin_spec = {
        "pin_id": post_id,
        "pin_topic": title,
        "content_type": blog_data.get("content_type", ""),
        "pillar": blog_data.get("pillar"),
        "primary_keyword": title,  # Use title as primary keyword for blog heroes
        "pin_template": "recipe-pin",  # Default template context for image search
    }

    if feedback:
        pin_spec["_regen_feedback"] = feedback

    # Determine image tier from previous source, defaulting to stock
    prev_source = blog_data.get("_hero_image_source", "stock")
    if prev_source in ("unsplash", "pexels", "stock"):
        image_tier = "stock"
    elif prev_source == "ai_generated":
        image_tier = "ai"
    else:
        image_tier = "stock"

    PIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    image_path, image_source, image_id, quality_meta = source_image(
        pin_spec=pin_spec,
        image_tier=image_tier,
        claude=claude,
        stock_api=stock_api,
        image_gen_api=image_gen_api,
        used_image_ids=used_image_ids,
        output_dir=PIN_OUTPUT_DIR,
    )

    result: dict = {
        "image_url": None,
        "quality_score": quality_meta.get("image_quality_score"),
        "image_source": image_source,
        "image_id": image_id,
    }

    if not image_path:
        logger.error("Image sourcing failed for blog %s — no image returned", post_id)
        return result

    # Save hero with slug name so blog_deployer.py can find it
    slug_hero = PIN_OUTPUT_DIR / f"{slug}-hero{Path(image_path).suffix}"
    if str(image_path) != str(slug_hero):
        import shutil
        shutil.copy2(image_path, slug_hero)
        logger.info("Saved blog hero as %s", slug_hero.name)

    if image_id:
        used_image_ids.append(f"{image_source}:{image_id}")

    # Upload the raw hero image to GCS (not a rendered pin)
    # Use a timestamped name to bust Google Sheets =IMAGE() cache
    if gcs.client:
        ts = int(time.time())
        remote_name = f"{post_id}-hero-{ts}{Path(image_path).suffix}"
        image_url = gcs.upload_image(image_path, remote_name=remote_name)
        if image_url:
            result["image_url"] = image_url
            logger.info("Uploaded blog hero %s to GCS: %s", post_id, image_url)
        else:
            logger.error("GCS upload failed for blog hero %s", post_id)
    else:
        logger.warning("GCS client not available, cannot upload blog hero for %s", post_id)

    return result


def _update_pin_results(
    pin_data: dict,
    new_pin_data: dict,
    regen_type: str,
    feedback: str,
) -> None:
    """
    Update the pin_data dict in-place with new values and regen history.

    Modifies pin_data directly (which is a reference into the
    pin-generation-results.json 'generated' list).
    """
    # Record history entry before overwriting
    history_entry = {
        "regen_type": regen_type,
        "feedback": feedback,
        "timestamp": datetime.now().isoformat(),
        "previous_score": pin_data.get("image_quality_score"),
        "previous_image_source": pin_data.get("image_source"),
        "previous_title": pin_data.get("title"),
    }

    regen_history = pin_data.get("_regen_history", [])
    regen_history.append(history_entry)

    # Copy new values over
    keys_to_update = [
        "title", "description", "alt_text", "text_overlay",
        "image_path", "hero_image_path", "image_source", "image_id",
        "image_quality_score", "image_retries", "image_low_confidence",
        "image_quality_issues", "_drive_image_url", "_drive_download_url",
    ]
    for key in keys_to_update:
        if key in new_pin_data:
            pin_data[key] = new_pin_data[key]

    pin_data["_regen_history"] = regen_history


def _build_regen_quality_note(pin_data: dict) -> str:
    """Build a quality note for a regenerated pin's Notes column."""
    score = pin_data.get("image_quality_score")
    if score is None:
        return "Regen"

    parts = [f"Regen {score:.1f}"]

    if pin_data.get("image_low_confidence"):
        parts.append("LOW CONFIDENCE")

    issues = pin_data.get("image_quality_issues", [])
    if issues:
        parts.append(", ".join(str(i) for i in issues[:3]))

    return " | ".join(parts)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    regen()
