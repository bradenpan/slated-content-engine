"""
Pin Content Generator

Generates pin assets (copy + images) for all pins in the approved
weekly content plan. Runs as part of the generate-content.yml workflow,
triggered after plan approval.

For each pin in the plan:
1. Generate pin copy via Claude (title, description, alt text, text overlay)
2. Generate AI image prompt and generate image via gpt-image-1.5
3. Assemble final pin image via pin_assembler.py

Copy is informed by the blog post content -- recipe-pull pins excerpt
from the parent plan post. Pins are batched 5-7 per Claude API call.

For "new content" pins: blog post URL derived from generated slug.
For "fresh treatment" pins: URL is the existing blog post URL from content log.
"""

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from src.apis.claude_api import ClaudeAPI
from src.apis.image_gen import ImageGenAPI
from src.image_cleaner import clean_image
from src.pin_assembler import PinAssembler
from src.paths import DATA_DIR, STRATEGY_DIR, PIN_OUTPUT_DIR
from src.config import BLOG_BASE_URL, COPY_BATCH_SIZE

logger = logging.getLogger(__name__)


def generate_pin_content(
    plan_path: Optional[str] = None,
    blog_posts: Optional[dict] = None,
) -> list[dict]:
    """
    Generate pin content (copy + images) for all pins in the plan.

    This is the main entry point called by the generate-content.yml workflow.

    Args:
        plan_path: Path to the approved weekly plan JSON file.
                   If None, loads the most recent plan from data/.
        blog_posts: Dict of post_id -> generated blog post data
                    (used for recipe-pull pin copy context).
                    If None, loads from blog-generation-results.json.

    Returns:
        list[dict]: Generated pin data ready for posting, with fields:
            - pin_id, title, description, alt_text, text_overlay
            - image_path (rendered pin PNG)
            - board_id, board_name, link (blog post URL with UTM params)
            - scheduled_date, scheduled_slot
            - image_source, image_id
    """
    logger.info("Starting pin content generation")

    # Load the plan
    plan = _load_plan(plan_path)
    if not plan:
        logger.error("No plan found for pin content generation")
        return []

    pins_specs = plan.get("pins", [])
    if not pins_specs:
        logger.warning("No pins in the plan")
        return []

    logger.info("Generating content for %d pins", len(pins_specs))

    # Load blog post data if not provided
    if blog_posts is None:
        blog_posts = _load_blog_generation_results()

    # Load strategy context
    brand_voice = _load_brand_voice()
    keyword_targets = _load_keyword_targets()
    used_image_ids = load_used_image_ids()
    board_id_map = _load_board_id_map()

    # Initialize API clients
    claude = ClaudeAPI()
    image_gen_api = ImageGenAPI()
    assembler = PinAssembler()

    # Ensure output directory exists
    PIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate copy for all pins in batches
    all_pin_copy = _generate_all_copy(
        claude=claude,
        pin_specs=pins_specs,
        blog_posts=blog_posts,
        brand_voice=brand_voice,
        keyword_targets=keyword_targets,
    )

    # Step 2: Source images and assemble pins
    generated_pins = []
    failures = []

    for i, pin_spec in enumerate(pins_specs):
        pin_id = pin_spec.get("pin_id", f"pin-{i}")

        try:
            # Get the copy for this pin
            pin_copy = all_pin_copy.get(pin_id, {})
            if not pin_copy:
                logger.warning("No copy generated for pin %s, skipping", pin_id)
                failures.append({"pin_id": pin_id, "error": "No copy generated"})
                continue

            # Add alt_text visual description for image sourcing
            alt_text = pin_copy.get("alt_text", "")
            if alt_text:
                # First sentence is the visual description; second is SEO keywords
                visual_desc = alt_text.split(".")[0].strip()
                pin_spec["_image_subject_hint"] = visual_desc

            # Source the image
            pin_template = pin_spec.get("pin_template", "")
            if pin_template == "infographic-pin":
                # Infographic template is text-only, no image needed
                image_path, image_source, image_id, quality_meta = None, "template", "", {}
            else:
                # All other templates get an AI-generated image
                image_path, image_source, image_id, quality_meta = _source_ai_image(
                    pin_spec, claude, image_gen_api, PIN_OUTPUT_DIR
                )

            # Track the used image
            if image_id:
                used_image_ids.append(f"{image_source}:{image_id}")

            # Assemble the final pin image
            template_type = pin_spec.get("pin_template", "recipe-pin")
            text_overlay = pin_copy.get("text_overlay", {})

            # Extract headline/subtitle from text_overlay (may be dict or str)
            if isinstance(text_overlay, dict):
                headline = text_overlay.get("headline", "")
                subtitle = text_overlay.get("sub_text", "")
            else:
                headline = str(text_overlay) if text_overlay else ""
                subtitle = pin_copy.get("subtitle", "")

            # Build template-specific context for non-recipe templates
            extra_context = build_template_context(
                template_type, pin_copy, pin_spec, image_path,
            )

            rendered_pin_path = assembler.assemble_pin(
                template_type=template_type,
                hero_image_path=image_path,
                headline=headline,
                subtitle=subtitle,
                variant=pin_spec.get("template_variant", 1),
                output_path=PIN_OUTPUT_DIR / f"{pin_id}.png",
                extra_context=extra_context,
            )

            # Save a slug-named copy of the hero image so blog_deployer.py
            # can find it (deployer looks for {slug}-hero.{ext}, not {pin_id}-hero.{ext})
            blog_slug = _resolve_blog_slug(pin_spec, blog_posts)
            if blog_slug and image_path and Path(image_path).exists():
                slug_hero = PIN_OUTPUT_DIR / f"{blog_slug}-hero{Path(image_path).suffix}"
                if not slug_hero.exists():
                    import shutil
                    shutil.copy2(image_path, slug_hero)
                    logger.info("Saved slug-named hero copy: %s", slug_hero.name)

            # Build the blog post link (bare URL — UTM params added at posting
            # time by post_pins.py:construct_utm_link to avoid double-tagging)
            board_name = pin_spec.get("target_board", "")
            link = f"{BLOG_BASE_URL}/{blog_slug}" if blog_slug else BLOG_BASE_URL

            # Build the complete pin data
            pin_data = {
                "pin_id": pin_id,
                "title": pin_copy.get("title", ""),
                "description": pin_copy.get("description", ""),
                "alt_text": pin_copy.get("alt_text", ""),
                "text_overlay": text_overlay,
                "image_path": str(rendered_pin_path),
                "hero_image_path": str(image_path) if image_path else None,
                "board_name": board_name,
                "board_id": board_id_map.get(board_name, ""),
                "link": link,
                "blog_slug": blog_slug,
                "scheduled_date": pin_spec.get("scheduled_date", ""),
                "scheduled_slot": pin_spec.get("scheduled_slot", ""),
                "image_source": image_source,
                "image_id": image_id,
                "pillar": pin_spec.get("pillar"),
                "pin_type": pin_spec.get("pin_type", "primary"),
                "template": template_type,
                "content_type": pin_spec.get("content_type"),
                "primary_keyword": pin_spec.get("primary_keyword", ""),
                "secondary_keywords": pin_spec.get("secondary_keywords", []),
                "treatment_number": pin_spec.get("treatment_number", 1),
                "source_post_id": pin_spec.get("source_post_id", ""),
                "funnel_layer": pin_spec.get("funnel_layer", "discovery"),
                "image_retries": quality_meta.get("image_retries", 0),
            }

            generated_pins.append(pin_data)
            logger.info("Generated pin %s: %s", pin_id, pin_copy.get("title", "")[:60])

        except Exception as e:
            logger.error("Failed to generate pin %s: %s", pin_id, e)
            failures.append({"pin_id": pin_id, "error": str(e)})

    # Log summary
    logger.info(
        "Pin generation complete: %d succeeded, %d failed out of %d total",
        len(generated_pins), len(failures), len(pins_specs),
    )

    # Content Queue sheet write and Slack notification handled by
    # publish_content_queue.py (runs after git commit so image URLs resolve)

    # Save pin generation results for downstream steps
    _save_pin_results(generated_pins, failures)

    return generated_pins


def generate_copy_batch(
    claude: ClaudeAPI,
    pin_specs: list[dict],
    blog_context: dict,
    brand_voice: str,
    keyword_targets: dict,
) -> list[dict]:
    """
    Generate copy for a batch of pins in a single Claude call.

    Args:
        claude: ClaudeAPI instance.
        pin_specs: Batch of pin specifications (up to COPY_BATCH_SIZE).
        blog_context: Relevant blog post content for context.
        brand_voice: Brand voice guidelines text.
        keyword_targets: Per-pillar keyword targets.

    Returns:
        list[dict]: Pin copy with title, description, alt_text,
                    text_overlay, subtitle for each pin in the batch.
    """
    # Build context for each pin in the batch
    enriched_specs = []
    for spec in pin_specs:
        enriched = dict(spec)

        # Add blog post content context if available
        source_id = spec.get("source_post_id", "")
        if source_id and source_id in blog_context:
            post_data = blog_context[source_id]
            # Include a summary of the blog post for context
            mdx_content = post_data.get("mdx_content", "")
            if mdx_content:
                # Truncate to first 500 chars of body for context
                body_start = mdx_content.find("---", 3)
                if body_start > 0:
                    body = mdx_content[body_start + 3:body_start + 503].strip()
                    enriched["blog_excerpt"] = body

        enriched_specs.append(enriched)

    # Call Claude API for batch copy generation
    results = claude.generate_pin_copy(
        pin_specs=enriched_specs,
        brand_voice=brand_voice,
        keyword_targets=keyword_targets,
    )

    return results




def load_used_image_ids() -> list[str]:
    """
    Load image IDs used in the last 90 days from content-log.jsonl.

    Returns:
        list[str]: Image IDs in "source:id" format (e.g., "unsplash:abc123").
    """
    log_path = DATA_DIR / "content-log.jsonl"
    if not log_path.exists():
        return []

    ninety_days_ago = date.today() - timedelta(days=90)
    image_ids = []

    try:
        for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry_date_str = entry.get("posted_date", entry.get("date", ""))
                try:
                    entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    continue

                if entry_date >= ninety_days_ago:
                    source = entry.get("image_source", "")
                    img_id = entry.get("image_id", "")
                    if source and img_id:
                        image_ids.append(f"{source}:{img_id}")
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        pass

    return image_ids


# =========================================================================
# Private helper functions
# =========================================================================


def _load_plan(plan_path: Optional[str] = None) -> dict:
    """Load the weekly plan from a file or find the most recent one."""
    if plan_path:
        path = Path(plan_path)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        logger.error("Plan file not found: %s", path)
        return {}

    plan_files = sorted(DATA_DIR.glob("weekly-plan-*.json"), reverse=True)
    if not plan_files:
        return {}

    latest = plan_files[0]
    logger.info("Loading most recent plan: %s", latest)
    return json.loads(latest.read_text(encoding="utf-8"))


def _load_blog_generation_results() -> dict:
    """Load blog generation results from the metadata file."""
    results_path = DATA_DIR / "blog-generation-results.json"
    if not results_path.exists():
        logger.warning("No blog generation results found at %s", results_path)
        return {}

    try:
        return json.loads(results_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in blog generation results: %s", e)
        return {}


def _load_brand_voice() -> str:
    """Load brand voice guidelines."""
    brand_voice_path = STRATEGY_DIR / "brand-voice.md"
    try:
        return brand_voice_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("brand-voice.md not found")
        return ""


def _load_keyword_targets() -> dict:
    """Load keyword targets from strategy."""
    kw_path = STRATEGY_DIR / "keyword-lists.json"
    try:
        return json.loads(kw_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("keyword-lists.json not found or invalid")
        return {}


def _load_board_id_map() -> dict:
    """
    Build a board name -> board ID mapping.

    In practice, board IDs come from the Pinterest API (boards are created
    and their IDs stored). For now, this returns an empty map since the
    boards haven't been created yet. The pipeline will need to be run
    after boards are created and their IDs stored.
    """
    # Look for a stored board ID mapping file
    board_ids_path = DATA_DIR / "board-ids.json"
    if board_ids_path.exists():
        try:
            return json.loads(board_ids_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    logger.info("No board ID mapping found -- board IDs will need to be resolved at posting time")
    return {}


def _generate_all_copy(
    claude: ClaudeAPI,
    pin_specs: list[dict],
    blog_posts: dict,
    brand_voice: str,
    keyword_targets: dict,
) -> dict:
    """
    Generate copy for all pins in batches.

    Args:
        claude: ClaudeAPI instance.
        pin_specs: All pin specifications from the plan.
        blog_posts: Blog post generation results.
        brand_voice: Brand voice text.
        keyword_targets: Keyword targets dict.

    Returns:
        dict: pin_id -> copy dict.
    """
    all_copy: dict = {}

    # Process in batches of COPY_BATCH_SIZE
    for batch_start in range(0, len(pin_specs), COPY_BATCH_SIZE):
        batch = pin_specs[batch_start:batch_start + COPY_BATCH_SIZE]
        batch_ids = [p.get("pin_id", f"pin-{batch_start + i}") for i, p in enumerate(batch)]

        logger.info(
            "Generating copy for batch %d-%d: %s",
            batch_start, batch_start + len(batch), batch_ids,
        )

        try:
            batch_results = generate_copy_batch(
                claude=claude,
                pin_specs=batch,
                blog_context=blog_posts,
                brand_voice=brand_voice,
                keyword_targets=keyword_targets,
            )

            # Map results back to pin IDs
            for spec, result in zip(batch, batch_results):
                pin_id = spec.get("pin_id", "")
                if pin_id and result:
                    all_copy[pin_id] = result
        except Exception as e:
            logger.error(
                "Batch copy generation failed for pins %s: %s", batch_ids, e
            )
            # Generate copy individually as fallback
            for spec in batch:
                pin_id = spec.get("pin_id", "")
                try:
                    individual_results = generate_copy_batch(
                        claude=claude,
                        pin_specs=[spec],
                        blog_context=blog_posts,
                        brand_voice=brand_voice,
                        keyword_targets=keyword_targets,
                    )
                    if individual_results:
                        all_copy[pin_id] = individual_results[0]
                except Exception as inner_e:
                    logger.error("Individual copy generation failed for %s: %s", pin_id, inner_e)

    logger.info("Generated copy for %d/%d pins", len(all_copy), len(pin_specs))
    return all_copy


def build_template_context(
    template_type: str,
    pin_copy: dict,
    pin_spec: dict,
    image_path: Optional[Path],
) -> dict:
    """Build template-specific context variables for pin assembly.

    The pin copy prompt produces: title, description, alt_text, and
    text_overlay (with headline + sub_text). Non-recipe templates need
    additional variables (bullets, list items, steps, etc.) that are
    derived from the pin copy and pin spec data.

    Args:
        template_type: Template name (e.g. "tip-pin", "listicle-pin").
        pin_copy: Pin copy dict from Claude (title, description, text_overlay, etc).
        pin_spec: Pin specification from the weekly plan.
        image_path: Path to the sourced hero/background image, or None.

    Returns:
        dict of extra context variables to merge into the render context.
    """
    context: dict = {}

    # Non-recipe templates use background_image_url instead of (or in addition to)
    # hero_image_url. The base assemble_pin() sets hero_image_url from hero_image_path,
    # so we also need to provide background_image_url for templates that expect it.
    if template_type != "recipe-pin" and image_path:
        context["background_image_url"] = str(image_path)

    text_overlay = pin_copy.get("text_overlay", {})
    if isinstance(text_overlay, dict):
        overlay_headline = text_overlay.get("headline", "")
        overlay_sub_text = text_overlay.get("sub_text", "")
    else:
        overlay_headline = str(text_overlay) if text_overlay else ""
        overlay_sub_text = ""

    description = pin_copy.get("description", "")
    pin_topic = pin_spec.get("pin_topic", "")

    if template_type == "recipe-pin":
        # Time badge — rendered in recipe-pin time badge element
        if isinstance(text_overlay, dict) and text_overlay.get("time_badge"):
            context["time_badge"] = text_overlay["time_badge"]
        # CTA text
        if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
            context["cta_text"] = text_overlay["cta_text"]

    elif template_type == "tip-pin":
        # Prefer structured bullets from text_overlay
        if isinstance(text_overlay, dict) and text_overlay.get("bullet_1"):
            for i in range(1, 4):
                context[f"bullet_{i}"] = text_overlay.get(f"bullet_{i}", "")
        else:
            # Fallback: extract from description
            bullets = _extract_bullets(description, overlay_sub_text, pin_topic)
            for i, bullet in enumerate(bullets[:3], 1):
                context[f"bullet_{i}"] = bullet
        # Category label — injected into {{category_label}} in tip-pin template
        if isinstance(text_overlay, dict) and text_overlay.get("category_label"):
            context["category_label"] = text_overlay["category_label"]
        else:
            context["category_label"] = "Tips & Advice"
        # CTA text (new field)
        if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
            context["cta_text"] = text_overlay["cta_text"]

    elif template_type == "listicle-pin":
        # Prefer structured list_items from text_overlay
        if isinstance(text_overlay, dict) and text_overlay.get("list_items"):
            items = text_overlay["list_items"]
            # Enforce max 5 items on pin (with "...and more" for longer lists)
            if len(items) > 5:
                context["has_more_items"] = True
                items = items[:5]
            context["list_items"] = items
        else:
            # Fallback: extract from description
            context["list_items"] = _extract_list_items(description, pin_topic)

        # Number: prefer explicit field, fall back to extraction from headline
        if isinstance(text_overlay, dict) and text_overlay.get("number"):
            context["number"] = str(text_overlay["number"])
        else:
            context["number"] = _extract_leading_number(overlay_headline)

        # CTA text
        if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
            context["cta_text"] = text_overlay["cta_text"]

    elif template_type == "problem-solution-pin":
        # Prefer explicit problem_text/solution_text from text_overlay
        if isinstance(text_overlay, dict) and text_overlay.get("problem_text"):
            context["problem_text"] = text_overlay["problem_text"]
            context["solution_text"] = text_overlay.get("solution_text", overlay_sub_text or "")
        else:
            # Fallback: headline = problem, sub_text = solution
            context["problem_text"] = overlay_headline
            context["solution_text"] = overlay_sub_text or pin_copy.get("title", "")
        # Section labels — injected into {{problem_label}} / {{solution_label}} in template
        # (defaults ensure labels never render empty)
        context["problem_label"] = text_overlay.get("problem_label", "The Problem") if isinstance(text_overlay, dict) else "The Problem"
        context["solution_label"] = text_overlay.get("solution_label", "The Answer") if isinstance(text_overlay, dict) else "The Answer"
        # CTA text
        if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
            context["cta_text"] = text_overlay["cta_text"]

    elif template_type == "infographic-pin":
        context["title"] = overlay_headline or pin_copy.get("title", "")
        # Prefer structured steps from text_overlay
        if isinstance(text_overlay, dict) and text_overlay.get("steps"):
            steps = text_overlay["steps"]
            # Ensure each step is a dict with number and text
            if isinstance(steps, list) and all(isinstance(s, dict) for s in steps):
                context["steps"] = steps[:6]  # Max 6 steps
            else:
                context["steps"] = _extract_steps(description)
        else:
            context["steps"] = _extract_steps(description)
        # Footer text: prefer explicit field
        if isinstance(text_overlay, dict) and text_overlay.get("footer_text"):
            context["footer_text"] = text_overlay["footer_text"]
        else:
            context["footer_text"] = overlay_sub_text or ""
        # Category label — injected into {{category_label}} in infographic-pin template
        if isinstance(text_overlay, dict) and text_overlay.get("category_label"):
            context["category_label"] = text_overlay["category_label"]
        else:
            context["category_label"] = "Step by Step"
        # CTA text
        if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
            context["cta_text"] = text_overlay["cta_text"]

    return context


def _extract_bullets(description: str, sub_text: str, pin_topic: str) -> list[str]:
    """Extract up to 3 bullet points from description text.

    Splits description on sentence boundaries and returns the most
    useful short phrases.
    """
    bullets: list[str] = []

    # If sub_text exists, use it as the first bullet
    if sub_text:
        bullets.append(sub_text)

    # Split description into sentences and pick short, punchy ones
    sentences = [s.strip() for s in re.split(r'[.!?]+', description) if s.strip()]
    for sentence in sentences:
        if len(bullets) >= 3:
            break
        # Skip very long sentences (not good for bullets) and very short ones
        if 10 < len(sentence) < 80:
            bullets.append(sentence)

    return bullets[:3]


def _extract_leading_number(headline: str) -> str:
    """Extract a leading number from a headline like '7 Easy Dinners'."""
    match = re.match(r'^(\d+)', headline.strip())
    return match.group(1) if match else ""


def _extract_list_items(description: str, pin_topic: str) -> list[str]:
    """Extract list items from description text.

    Splits on sentence boundaries to produce a list of short items.
    """
    sentences = [s.strip() for s in re.split(r'[.!?]+', description) if s.strip()]
    # Filter to reasonable-length items and cap at 5
    items = [s for s in sentences if 8 < len(s) < 100]
    return items[:5]


def _extract_steps(description: str) -> list[dict]:
    """Extract numbered steps from description text.

    Returns list of {"number": str, "text": str} dicts.
    """
    sentences = [s.strip() for s in re.split(r'[.!?]+', description) if s.strip()]
    steps = []
    for i, sentence in enumerate(sentences, 1):
        if len(sentence) < 8:
            continue
        steps.append({"number": str(i), "text": sentence})
        if len(steps) >= 6:
            break
    return steps






def _source_ai_image(
    pin_spec: dict,
    claude: ClaudeAPI,
    image_gen_api: ImageGenAPI,
    output_dir: Path,
) -> tuple[Optional[Path], str, str, dict]:
    """
    Source an image via AI generation (generate prompt -> generate image -> done).

    Human review in the Content Queue is the quality gate.

    Args:
        pin_spec: Pin specification.
        claude: ClaudeAPI instance.
        image_gen_api: Image generation API client.
        output_dir: Output directory for generated images.

    Returns:
        tuple: (image_path, "ai_generated", "ai_{hash}", quality_meta)
    """
    pin_id = pin_spec.get("pin_id", "unknown")
    quality_meta: dict = {"image_retries": 0}

    # Generate image prompt (template returns JSON with image_prompt field)
    regen_feedback = pin_spec.get("_regen_feedback", "")
    image_prompt_raw = claude.generate_image_prompt(
        pin_spec, regen_feedback=regen_feedback,
    )
    try:
        # Strip markdown code fences if present (GPT-5 Mini may wrap JSON)
        cleaned = image_prompt_raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (with optional language tag like ```json)
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and "image_prompt" in parsed:
            image_prompt = parsed["image_prompt"]
        else:
            image_prompt = image_prompt_raw
    except (json.JSONDecodeError, KeyError):
        image_prompt = image_prompt_raw

    # If reviewer feedback exists, append it as critical guidance
    if regen_feedback:
        image_prompt = (
            f"{image_prompt}\n\nCRITICAL — previous image was rejected: {regen_feedback}"
        )

    logger.info("AI image prompt for %s: '%s'", pin_id, image_prompt[:100])

    # Generate the image
    image_filename = f"{pin_id}-hero.png"
    output_path = output_dir / image_filename

    generated_path = image_gen_api.generate(
        prompt=image_prompt,
        width=1000,
        height=1500,
        output_path=output_path,
        style="natural",
    )

    # Strip AI metadata and apply anti-detection post-processing
    clean_image(generated_path)

    # Use a hash of the prompt as the image ID for tracking
    prompt_hash = hashlib.md5(image_prompt.encode()).hexdigest()[:12]

    logger.info("AI image generated for %s: %s", pin_id, generated_path)
    return generated_path, "ai_generated", f"ai_{prompt_hash}", quality_meta


def _resolve_blog_slug(pin_spec: dict, blog_posts: dict) -> str:
    """
    Resolve the blog slug for a pin.

    For new content pins, the slug comes from the generated blog post.
    For fresh treatment pins, the slug comes from the pin spec or content log.

    Args:
        pin_spec: Pin specification.
        blog_posts: Blog generation results.

    Returns:
        str: Blog slug, or empty string if not resolved.
    """
    # Check if pin has an explicit blog_slug
    slug = pin_spec.get("blog_slug", "")
    if slug:
        return slug

    # Try to resolve from source_post_id
    source_id = pin_spec.get("source_post_id", "")
    if source_id and source_id in blog_posts:
        return blog_posts[source_id].get("slug", "")

    # For fresh treatments, the slug should be in the pin spec
    return pin_spec.get("existing_slug", "")


def _save_pin_results(generated_pins: list[dict], failures: list[dict]) -> None:
    """
    Save pin generation results for downstream pipeline steps.

    Args:
        generated_pins: Successfully generated pin data.
        failures: Failed pin data.
    """
    results = {
        "generated": generated_pins,
        "failures": failures,
        "generated_count": len(generated_pins),
        "failure_count": len(failures),
        "generated_at": datetime.now().isoformat(),
    }

    results_path = DATA_DIR / "pin-generation-results.json"
    results_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved pin generation results to %s", results_path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    print("Starting pin content generation...")
    results = generate_pin_content()
    print(f"Generated {len(results)} pins")
