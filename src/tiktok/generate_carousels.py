"""TikTok Carousel Rendering + Image Generation Orchestrator.

Takes a weekly plan (list of carousel specs) and produces rendered slide PNGs:
1. For each carousel: generates per-slide AI images as specified by image_prompts
2. Renders all slides via CarouselAssembler (Puppeteer manifest mode)
3. Cleans rendered images (metadata strip + anti-detection noise)

image_prompts is an array of {slide_index, prompt} entries in the carousel spec.
Only slides listed in image_prompts get AI-generated backgrounds; others render
as pure text/CSS. Typically only photo_forward carousels have image_prompts.

This module handles the family name translation between the taxonomy
(underscores: "photo_forward") and CarouselAssembler (hyphens: "photo-forward").
"""

import logging
from pathlib import Path
from typing import Optional

from src.shared.apis.image_gen import ImageGenAPI
from src.shared.image_cleaner import clean_image
from src.shared.paths import TIKTOK_OUTPUT_DIR
from src.tiktok.carousel_assembler import CarouselAssembler

logger = logging.getLogger(__name__)

# TikTok portrait dimensions for image generation (closest OpenAI supports to 1080x1920)
IMAGE_GEN_WIDTH = 1024
IMAGE_GEN_HEIGHT = 1536


def _taxonomy_to_assembler_family(family: str) -> str:
    """Translate taxonomy family names (underscores) to assembler names (hyphens)."""
    return family.replace("_", "-")


def build_slides_for_render(
    spec: dict,
    image_paths_by_index: dict[int, Path | str] | None = None,
) -> list[dict]:
    """Build the slide context list for CarouselAssembler from a carousel spec.

    Shared by generate_carousels() (initial render) and regen_content.py
    (re-render after image regen).

    Args:
        spec: Carousel spec dict with hook_text, content_slides, cta_slide.
        image_paths_by_index: Optional mapping of slide_index -> image path.
            slide_index 0 = hook, 1..N = content slides, last = CTA.

    Returns:
        List of slide context dicts ready for CarouselAssembler.render_carousel().
    """
    image_paths_by_index = image_paths_by_index or {}
    carousel_id = spec.get("carousel_id", "unknown")
    slides = []

    # Hook slide
    hook_text = spec.get("hook_text") or ""
    hook_context = {
        "slide_type": "hook",
        "headline": hook_text,
    }
    bg = image_paths_by_index.get(0)
    if bg:
        hook_context["background_image_url"] = str(bg)
    slides.append(hook_context)

    # Content slides
    content_slides = spec.get("content_slides") or []
    if not isinstance(content_slides, list):
        logger.warning(
            "Carousel %s has non-list content_slides (%s), using empty",
            carousel_id, type(content_slides).__name__,
        )
        content_slides = []

    for i, content_slide in enumerate(content_slides):
        if not isinstance(content_slide, dict):
            logger.warning("Carousel %s content_slide %d is not a dict, skipping", carousel_id, i)
            continue
        slide_context = {
            "slide_type": "content",
            "headline": content_slide.get("headline") or "",
            "body_text": content_slide.get("body_text") or "",
        }
        if content_slide.get("list_items"):
            slide_context["list_items"] = content_slide["list_items"]
        # comparison-grid specific fields
        for field in ("left_label", "right_label", "left_text", "right_text"):
            if content_slide.get(field):
                slide_context[field] = content_slide[field]
        bg = image_paths_by_index.get(i + 1)  # content slides are 1-indexed
        if bg:
            slide_context["background_image_url"] = str(bg)
        slides.append(slide_context)

    # CTA slide
    cta = spec.get("cta_slide") or {}
    if not isinstance(cta, dict):
        logger.warning("Carousel %s cta_slide is not a dict, using defaults", carousel_id)
        cta = {}
    cta_index = 1 + len(content_slides)  # hook(0) + N content slides
    cta_context = {
        "slide_type": "cta",
        "cta_primary": cta.get("cta_primary") or "Follow @slatedapp",
        "cta_secondary": cta.get("cta_secondary") or "",
        "handle": "@slatedapp",
    }
    bg = image_paths_by_index.get(cta_index)
    if bg:
        cta_context["background_image_url"] = str(bg)
    slides.append(cta_context)

    return slides


def _generate_slide_images(
    spec: dict,
    image_gen: ImageGenAPI,
    output_dir: Path,
) -> dict[int, Path]:
    """Generate AI images for slides specified in image_prompts.

    Args:
        spec: Carousel spec with image_prompts array.
        image_gen: ImageGenAPI instance.
        output_dir: Directory to save generated images.

    Returns:
        Dict mapping slide_index -> cleaned image path.
    """
    carousel_id = spec.get("carousel_id", "unknown")
    image_prompts = spec.get("image_prompts") or []
    image_paths: dict[int, Path] = {}

    if not image_prompts:
        return image_paths

    output_dir.mkdir(parents=True, exist_ok=True)

    for ip in image_prompts:
        slide_index = ip.get("slide_index")
        prompt = ip.get("prompt", "")
        if slide_index is None or not prompt:
            logger.warning(
                "Carousel %s has image_prompt with missing slide_index or prompt, skipping",
                carousel_id,
            )
            continue

        try:
            img_path = output_dir / f"bg-slide-{slide_index}.png"
            generated = image_gen.generate(
                prompt=prompt,
                width=IMAGE_GEN_WIDTH,
                height=IMAGE_GEN_HEIGHT,
                output_path=img_path,
                style="natural",
            )
            # Strip metadata only (no noise) — rendered slides get noise later
            cleaned = clean_image(generated, add_noise=False)
            image_paths[slide_index] = cleaned
            logger.info(
                "Generated image for %s slide %d: %s",
                carousel_id, slide_index, cleaned,
            )
        except Exception as e:
            logger.error(
                "Failed to generate image for %s slide %d: %s",
                carousel_id, slide_index, e,
            )
            # Slide renders as text-only (no background image)

    return image_paths


def generate_carousels(
    plan: dict,
    image_gen: Optional[ImageGenAPI] = None,
    assembler: Optional[CarouselAssembler] = None,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> list[dict]:
    """Render all carousels in a weekly plan.

    For each carousel spec in the plan:
    1. Translate family name (underscore -> hyphen)
    2. Generate per-slide AI images as specified by image_prompts
    3. Build slide list via build_slides_for_render()
    4. Render via Puppeteer
    5. Clean rendered PNGs (preserve PNG format)

    Args:
        plan: Weekly plan dict with "carousels" key.
        image_gen: ImageGenAPI instance (created with provider="openai" if None).
        assembler: CarouselAssembler instance.
        output_dir: Base output directory for rendered slides.
        dry_run: If True, skip rendering and image generation.

    Returns:
        List of enriched carousel dicts with "rendered_slides" paths added.
    """
    output_dir = output_dir or TIKTOK_OUTPUT_DIR
    assembler = assembler or CarouselAssembler()
    carousels = plan.get("carousels", [])

    if not carousels:
        logger.warning("No carousels in plan")
        return []

    results = []

    for spec in carousels:
        carousel_id = spec.get("carousel_id", "unknown")
        taxonomy_family = spec.get("template_family", "clean_educational")
        assembler_family = _taxonomy_to_assembler_family(taxonomy_family)

        logger.info(
            "Processing carousel %s (family=%s, image_prompts=%d)",
            carousel_id, assembler_family,
            len(spec.get("image_prompts") or []),
        )

        # Step 1: Generate per-slide AI images
        image_paths_by_index: dict[int, Path] = {}
        if not dry_run and spec.get("image_prompts"):
            image_gen = image_gen or ImageGenAPI(provider="openai")
            carousel_output = output_dir / carousel_id
            image_paths_by_index = _generate_slide_images(
                spec, image_gen, carousel_output,
            )

        # Step 2: Build slide list
        slides = build_slides_for_render(spec, image_paths_by_index)

        # Step 3: Render via CarouselAssembler
        if dry_run:
            logger.info("[DRY RUN] Would render %d slides for %s", len(slides), carousel_id)
            enriched = dict(spec)
            enriched["rendered_slides"] = []
            enriched["slide_count"] = len(slides)
            results.append(enriched)
            continue

        try:
            rendered_paths = assembler.render_carousel(
                family=assembler_family,
                slides=slides,
                output_dir=output_dir / carousel_id,
                carousel_id=carousel_id,
            )

            # Step 4: Clean rendered PNGs (preserve PNG format)
            cleaned_paths = []
            for rp in rendered_paths:
                cleaned = clean_image(rp, add_noise=True, noise_sigma=1.5)
                cleaned_paths.append(cleaned)

            enriched = dict(spec)
            enriched["rendered_slides"] = [str(p) for p in cleaned_paths]
            enriched["slide_count"] = len(cleaned_paths)

            # Track which slides had image generation failures
            expected_images = {ip.get("slide_index") for ip in (spec.get("image_prompts") or [])}
            missing_images = expected_images - set(image_paths_by_index.keys())
            if missing_images:
                enriched["image_gen_failures"] = sorted(missing_images)
                logger.warning(
                    "Carousel %s: image generation failed for slides %s (rendered as text-only)",
                    carousel_id, sorted(missing_images),
                )

            results.append(enriched)

            logger.info(
                "Rendered carousel %s: %d slides", carousel_id, len(cleaned_paths),
            )

        except Exception as e:
            logger.error("Failed to render carousel %s: %s", carousel_id, e)
            enriched = dict(spec)
            enriched["rendered_slides"] = []
            enriched["slide_count"] = 0
            enriched["render_error"] = str(e)
            results.append(enriched)

    logger.info(
        "Carousel generation complete: %d/%d rendered successfully",
        sum(1 for r in results if r.get("rendered_slides")),
        len(results),
    )
    return results
