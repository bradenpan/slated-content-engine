"""
Pin Content Generator

Generates pin assets (copy + images) for all pins in the approved
weekly content plan. Runs as part of the generate-content.yml workflow,
triggered after plan approval.

For each pin in the plan:
1. Generate pin copy via Claude (title, description, alt text, text overlay)
2. Generate stock photo search queries or AI image prompts
3. Source images (Tier 1 stock / Tier 2 AI / Tier 3 template-only)
4. Assemble final pin image via pin_assembler.py

Copy is informed by the blog post content -- recipe-pull pins excerpt
from the parent plan post. Pins are batched 5-7 per Claude API call.

For "new content" pins: blog post URL derived from generated slug.
For "fresh treatment" pins: URL is the existing blog post URL from content log.
"""

import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from src.apis.claude_api import ClaudeAPI
from src.apis.image_stock import ImageStockAPI
from src.apis.image_gen import ImageGenAPI
from src.pin_assembler import PinAssembler

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STRATEGY_DIR = PROJECT_ROOT / "strategy"
PIN_OUTPUT_DIR = DATA_DIR / "generated" / "pins"

# Base URL for blog posts
BLOG_BASE_URL = "https://goslated.com/blog"

# Batch size for Claude API calls (pin copy generation)
COPY_BATCH_SIZE = 6


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
    stock_api = ImageStockAPI()
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

            # Determine image source tier
            image_tier = pin_spec.get("image_source_tier", "stock")

            # Source the image
            image_path, image_source, image_id = _source_pin_image(
                pin_spec=pin_spec,
                pin_copy=pin_copy,
                image_tier=image_tier,
                claude=claude,
                stock_api=stock_api,
                image_gen_api=image_gen_api,
                used_image_ids=used_image_ids,
                output_dir=PIN_OUTPUT_DIR,
            )

            # Track the used image
            if image_id:
                used_image_ids.append(f"{image_source}:{image_id}")

            # Assemble the final pin image
            template_type = pin_spec.get("pin_template", "recipe-pin")
            text_overlay = pin_copy.get("text_overlay", "")
            subtitle = pin_copy.get("subtitle", "")

            rendered_pin_path = assembler.assemble_pin(
                template_type=template_type,
                hero_image_path=image_path,
                headline=text_overlay,
                subtitle=subtitle,
                variant=pin_spec.get("template_variant", 1),
                output_path=PIN_OUTPUT_DIR / f"{pin_id}.png",
            )

            # Build the blog post link with UTM params
            blog_slug = _resolve_blog_slug(pin_spec, blog_posts)
            board_name = pin_spec.get("target_board", "")
            link = build_utm_link(blog_slug, board_name, pin_id)

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


def source_image(
    pin_spec: dict,
    image_tier: str,
    claude: ClaudeAPI,
    stock_api: ImageStockAPI,
    image_gen_api: ImageGenAPI,
    used_image_ids: list[str],
    output_dir: Path,
) -> tuple[Optional[Path], str, str]:
    """
    Source an image based on the specified tier.

    Args:
        pin_spec: Pin specification with topic and image requirements.
        image_tier: "stock", "ai", or "template".
        claude: ClaudeAPI for generating search queries or image prompts.
        stock_api: Stock photo API client.
        image_gen_api: AI image generation API client.
        used_image_ids: List of recently used image IDs for dedup.
        output_dir: Directory to save downloaded/generated images.

    Returns:
        tuple: (image_path, image_source, image_id)
               image_path may be None for template-only pins.
    """
    pin_id = pin_spec.get("pin_id", "unknown")

    if image_tier == "stock" or image_tier == "Tier 1":
        return _source_stock_image(
            pin_spec, claude, stock_api, used_image_ids, output_dir
        )
    elif image_tier == "ai" or image_tier == "Tier 2":
        return _source_ai_image(
            pin_spec, claude, image_gen_api, output_dir
        )
    elif image_tier == "template" or image_tier == "Tier 3":
        # No image sourcing needed for template-only pins
        logger.info("Pin %s uses template-only (Tier 3), no image to source", pin_id)
        return None, "template", ""
    else:
        logger.warning(
            "Unknown image tier '%s' for pin %s, defaulting to stock",
            image_tier, pin_id,
        )
        return _source_stock_image(
            pin_spec, claude, stock_api, used_image_ids, output_dir
        )


def build_utm_link(blog_slug: str, board_name: str, pin_id: str) -> str:
    """
    Build a blog post URL with UTM parameters.

    Format: goslated.com/blog/{slug}?utm_source=pinterest&utm_medium=organic
            &utm_campaign={board_name}&utm_content={pin_id}

    Args:
        blog_slug: Blog post URL slug.
        board_name: Pinterest board name.
        pin_id: Internal pin ID.

    Returns:
        str: Full URL with UTM parameters.
    """
    if not blog_slug:
        return BLOG_BASE_URL

    base = f"{BLOG_BASE_URL}/{blog_slug}"

    # URL-encode the board name for the campaign parameter
    campaign = quote_plus(board_name.lower().replace(" ", "-")) if board_name else "general"
    content = quote_plus(pin_id) if pin_id else ""

    utm_params = (
        f"utm_source=pinterest"
        f"&utm_medium=organic"
        f"&utm_campaign={campaign}"
        f"&utm_content={content}"
    )

    return f"{base}?{utm_params}"


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
                entry_date_str = entry.get("date", "")
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


def _source_pin_image(
    pin_spec: dict,
    pin_copy: dict,
    image_tier: str,
    claude: ClaudeAPI,
    stock_api: ImageStockAPI,
    image_gen_api: ImageGenAPI,
    used_image_ids: list[str],
    output_dir: Path,
) -> tuple[Optional[Path], str, str]:
    """
    Source an image for a pin, dispatching to the appropriate tier.

    Returns:
        tuple: (image_path, image_source, image_id)
    """
    return source_image(
        pin_spec=pin_spec,
        image_tier=image_tier,
        claude=claude,
        stock_api=stock_api,
        image_gen_api=image_gen_api,
        used_image_ids=used_image_ids,
        output_dir=output_dir,
    )


def _source_stock_image(
    pin_spec: dict,
    claude: ClaudeAPI,
    stock_api: ImageStockAPI,
    used_image_ids: list[str],
    output_dir: Path,
) -> tuple[Optional[Path], str, str]:
    """
    Source an image from stock photo APIs (Tier 1).

    Steps:
    1. Generate search query via Claude
    2. Search Unsplash + Pexels
    3. Filter out previously used images
    4. Download the best match

    Returns:
        tuple: (image_path, source_name, image_id)
    """
    pin_id = pin_spec.get("pin_id", "unknown")

    # Generate search query
    search_query = claude.generate_image_prompt(pin_spec, image_source="stock")
    logger.info("Stock search query for %s: '%s'", pin_id, search_query[:80])

    # Search for candidates
    candidates = stock_api.search(
        query=search_query,
        num_results=10,
        orientation="portrait",
    )

    if not candidates:
        logger.warning("No stock photos found for pin %s, trying AI generation", pin_id)
        return _source_ai_image(pin_spec, claude, ImageGenAPI(), output_dir)

    # Filter out previously used images
    filtered = stock_api.filter_previously_used(candidates, used_image_ids)

    if not filtered:
        logger.warning(
            "All stock candidates for pin %s were previously used, using first unfiltered result",
            pin_id,
        )
        filtered = candidates[:1]

    # Select the best candidate (first result after filtering)
    selected = filtered[0]

    # Download the image
    image_filename = f"{pin_id}-hero.jpg"
    output_path = output_dir / image_filename

    downloaded_path = stock_api.download_image(
        image=selected,
        output_path=output_path,
        width=1000,
    )

    source_name = selected.get("source", "stock")
    image_id = selected.get("id", "")

    logger.info("Downloaded stock image for %s: %s:%s", pin_id, source_name, image_id)
    return downloaded_path, source_name, image_id


def _source_ai_image(
    pin_spec: dict,
    claude: ClaudeAPI,
    image_gen_api: ImageGenAPI,
    output_dir: Path,
) -> tuple[Optional[Path], str, str]:
    """
    Source an image via AI generation (Tier 2).

    Steps:
    1. Generate image prompt via Claude
    2. Call image generation API
    3. Validate and save the result

    Returns:
        tuple: (image_path, "ai_generated", prompt_hash)
    """
    pin_id = pin_spec.get("pin_id", "unknown")

    # Generate image prompt
    image_prompt = claude.generate_image_prompt(pin_spec, image_source="ai")
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

    # Use a hash of the prompt as the image ID for tracking
    prompt_hash = hashlib.md5(image_prompt.encode()).hexdigest()[:12]

    logger.info("Generated AI image for %s: %s", pin_id, generated_path)
    return generated_path, "ai_generated", f"ai_{prompt_hash}"


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
