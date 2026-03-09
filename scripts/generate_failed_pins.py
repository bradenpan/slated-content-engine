"""
One-time script: generate the 12 W11 pins that failed due to OpenAI billing limit.

Loads the W11 plan, filters to only the failed pin IDs, runs copy generation +
image sourcing + Puppeteer rendering, and merges results into the existing
pin-generation-results.json (appends to 'generated', removes from 'failures').

Must run in CI (needs Puppeteer) or locally with Node.js + puppeteer installed.

Usage:
    python -m scripts.generate_failed_pins
"""

import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

from src.shared.apis.claude_api import ClaudeAPI
from src.shared.apis.image_gen import ImageGenAPI
from src.pinterest.pin_assembler import PinAssembler
from src.pinterest.generate_pin_content import (
    _generate_all_copy,
    _load_board_id_map,
    _resolve_blog_slug,
    build_template_context,
    load_keyword_targets,
    load_used_image_ids,
    source_ai_image,
)
from src.shared.paths import DATA_DIR, PIN_OUTPUT_DIR
from src.shared.config import BLOG_BASE_URL
from src.shared.utils.plan_utils import find_latest_plan, load_plan
from src.shared.utils.strategy_utils import load_brand_voice
from src.shared.utils.safe_get import safe_get

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Load current pin-generation-results.json
    results_path = DATA_DIR / "pin-generation-results.json"
    if not results_path.exists():
        logger.error("pin-generation-results.json not found")
        sys.exit(1)

    pin_results = json.loads(results_path.read_text(encoding="utf-8"))
    existing_generated = pin_results.get("generated", [])
    existing_failures = pin_results.get("failures", [])

    failed_ids = {f["pin_id"] for f in existing_failures if "pin_id" in f}
    if not failed_ids:
        logger.info("No failed pins found. Nothing to do.")
        return

    logger.info("Found %d failed pins: %s", len(failed_ids), sorted(failed_ids))

    # Load the plan and filter to failed pins only
    plan_path = find_latest_plan()
    if not plan_path:
        logger.error("No plan found")
        sys.exit(1)

    plan = load_plan(plan_path)
    all_pin_specs = safe_get(plan, "pins", [])
    failed_specs = [s for s in all_pin_specs if safe_get(s, "pin_id", "") in failed_ids]

    if len(failed_specs) != len(failed_ids):
        found = {safe_get(s, "pin_id", "") for s in failed_specs}
        missing = failed_ids - found
        logger.warning("Could not find plan specs for: %s", sorted(missing))

    if not failed_specs:
        logger.error("No matching pin specs found in plan")
        sys.exit(1)

    logger.info("Generating %d pins", len(failed_specs))

    # Load blog context (needed for recipe-pull pin copy)
    blog_results_path = DATA_DIR / "blog-generation-results.json"
    blog_posts = {}
    if blog_results_path.exists():
        blog_posts = json.loads(blog_results_path.read_text(encoding="utf-8"))

    # Load strategy context
    brand_voice = load_brand_voice()
    keyword_targets = load_keyword_targets()
    used_image_ids = load_used_image_ids()
    board_id_map = _load_board_id_map()

    # Build plan-level metadata for pillar/content_type fallback
    plan_post_meta = {}
    for post in safe_get(plan, "blog_posts", []):
        pid = safe_get(post, "post_id", "")
        if pid:
            plan_post_meta[pid] = {
                "pillar": safe_get(post, "pillar"),
                "content_type": safe_get(post, "content_type"),
            }

    # Initialize API clients
    claude = ClaudeAPI()
    image_gen_api = ImageGenAPI()
    assembler = PinAssembler()

    PIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate copy for the failed pins
    all_pin_copy = _generate_all_copy(
        claude=claude,
        pin_specs=failed_specs,
        blog_posts=blog_posts,
        brand_voice=brand_voice,
        keyword_targets=keyword_targets,
    )

    # Step 2: Source images and assemble pins
    new_generated = []
    new_failures = []

    for i, pin_spec in enumerate(failed_specs):
        pin_id = safe_get(pin_spec, "pin_id", f"pin-{i}")

        try:
            pin_copy = all_pin_copy.get(pin_id, {})
            if not pin_copy:
                logger.warning("No copy generated for pin %s, skipping", pin_id)
                new_failures.append({"pin_id": pin_id, "error": "No copy generated"})
                continue

            # Alt text hint for image sourcing
            alt_text = safe_get(pin_copy, "alt_text", "")
            if alt_text:
                visual_desc = alt_text.split(".")[0].strip()
                pin_spec["_image_subject_hint"] = visual_desc

            # Source image
            pin_template = safe_get(pin_spec, "pin_template", "")
            if pin_template == "infographic-pin":
                image_path, image_source, image_id, quality_meta = None, "template", "", {}
            else:
                image_path, image_source, image_id, quality_meta = source_ai_image(
                    pin_spec, claude, image_gen_api, PIN_OUTPUT_DIR
                )

            if image_id:
                used_image_ids.append(f"{image_source}:{image_id}")

            # Assemble rendered pin
            template_type = safe_get(pin_spec, "pin_template", "recipe-pin")
            text_overlay = safe_get(pin_copy, "text_overlay", {})

            if isinstance(text_overlay, dict):
                headline = safe_get(text_overlay, "headline", "")
                subtitle = safe_get(text_overlay, "sub_text", "")
            else:
                headline = str(text_overlay) if text_overlay else ""
                subtitle = safe_get(pin_copy, "subtitle", "")

            extra_context = build_template_context(
                template_type, pin_copy, pin_spec, image_path,
            )

            rendered_pin_path = assembler.assemble_pin(
                template_type=template_type,
                hero_image_path=image_path,
                headline=headline,
                subtitle=subtitle,
                variant=safe_get(pin_spec, "template_variant", 1),
                output_path=PIN_OUTPUT_DIR / f"{pin_id}.png",
                extra_context=extra_context,
            )

            # Save slug-named hero copy for blog_deployer
            blog_slug = _resolve_blog_slug(pin_spec, blog_posts)
            if blog_slug and image_path and Path(image_path).exists():
                slug_hero = PIN_OUTPUT_DIR / f"{blog_slug}-hero{Path(image_path).suffix}"
                if not slug_hero.exists():
                    shutil.copy2(image_path, slug_hero)
                    logger.info("Saved slug-named hero copy: %s", slug_hero.name)

            board_name = safe_get(pin_spec, "target_board", "")
            link = f"{BLOG_BASE_URL}/{blog_slug}" if blog_slug else BLOG_BASE_URL

            pin_data = {
                "pin_id": pin_id,
                "title": safe_get(pin_copy, "title", ""),
                "description": safe_get(pin_copy, "description", ""),
                "alt_text": safe_get(pin_copy, "alt_text", ""),
                "text_overlay": text_overlay,
                "image_path": str(rendered_pin_path),
                "hero_image_path": str(image_path) if image_path else None,
                "board_name": board_name,
                "board_id": safe_get(board_id_map, board_name, ""),
                "link": link,
                "blog_slug": blog_slug,
                "scheduled_date": safe_get(pin_spec, "scheduled_date", ""),
                "scheduled_slot": safe_get(pin_spec, "scheduled_slot", ""),
                "image_source": image_source,
                "image_id": image_id,
                "pillar": safe_get(pin_spec, "pillar"),
                "pin_type": safe_get(pin_spec, "pin_type", "primary"),
                "template": template_type,
                "content_type": safe_get(pin_spec, "content_type"),
                "primary_keyword": safe_get(pin_spec, "primary_keyword", ""),
                "secondary_keywords": safe_get(pin_spec, "secondary_keywords", []),
                "treatment_number": safe_get(pin_spec, "treatment_number", 1),
                "source_post_id": safe_get(pin_spec, "source_post_id", ""),
                "funnel_layer": safe_get(pin_spec, "funnel_layer", "discovery"),
                "image_retries": safe_get(quality_meta, "image_retries", 0),
            }

            # Inherit pillar/content_type from parent blog post if missing
            if pin_data["pillar"] is None or pin_data["content_type"] is None:
                source_id = safe_get(pin_spec, "source_post_id", "")
                parent = blog_posts.get(source_id) or plan_post_meta.get(source_id) or {}
                if pin_data["pillar"] is None:
                    pin_data["pillar"] = safe_get(parent, "pillar")
                if pin_data["content_type"] is None:
                    pin_data["content_type"] = safe_get(parent, "content_type")

            new_generated.append(pin_data)
            logger.info("Generated pin %s: %s", pin_id, safe_get(pin_copy, "title", "")[:60])

        except Exception as e:
            logger.error("Failed to generate pin %s: %s", pin_id, e)
            new_failures.append({"pin_id": pin_id, "error": str(e)})

    # Merge results into existing pin-generation-results.json
    # - Add new successes to 'generated'
    # - Remove newly succeeded pins from 'failures'
    # - Add any new failures to 'failures'
    new_success_ids = {p["pin_id"] for p in new_generated}
    merged_generated = existing_generated + new_generated
    merged_failures = [
        f for f in existing_failures
        if f.get("pin_id") not in new_success_ids
    ] + new_failures

    merged_results = {
        "generated": merged_generated,
        "failures": merged_failures,
        "generated_count": len(merged_generated),
        "failure_count": len(merged_failures),
        "generated_at": datetime.now().isoformat(),
    }

    # Atomic write
    tmp = results_path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(merged_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(results_path)
        logger.info("Saved merged results: %d generated, %d failures",
                     len(merged_generated), len(merged_failures))
    except OSError as e:
        logger.error("Failed to save results: %s", e)
        tmp.unlink(missing_ok=True)
        sys.exit(1)

    # Summary
    print(f"\nGenerated {len(new_generated)} pins ({len(new_failures)} failed)")
    print(f"Total: {len(merged_generated)} generated, {len(merged_failures)} failures")

    if new_failures:
        print("Still failing:")
        for f in new_failures:
            print(f"  {f['pin_id']}: {f['error'][:100]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
