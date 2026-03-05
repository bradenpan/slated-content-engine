"""TikTok Carousel Rendering + Image Generation Orchestrator.

Takes a weekly plan (list of carousel specs) and produces rendered slide PNGs:
1. For photo-forward carousels: generates background images via OpenAI gpt-image-1.5
2. Renders all slides via CarouselAssembler (Puppeteer manifest mode)
3. Cleans rendered images (metadata strip + anti-detection noise)
4. Uploads slides to GCS under tiktok/{carousel_id}/

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


def generate_carousels(
    plan: dict,
    image_gen: Optional[ImageGenAPI] = None,
    assembler: Optional[CarouselAssembler] = None,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> list[dict]:
    """Render all carousels in a weekly plan.

    For each carousel spec in the plan:
    1. Translate family name (underscore → hyphen)
    2. If photo-forward: generate background image via OpenAI
    3. Build slide list for CarouselAssembler
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
        is_photo_forward = assembler_family == "photo-forward"

        logger.info(
            "Processing carousel %s (family=%s, photo_forward=%s)",
            carousel_id, assembler_family, is_photo_forward,
        )

        # Step 1: Generate background image for photo-forward carousels
        background_image_path = None
        if is_photo_forward and not dry_run:
            image_gen = image_gen or ImageGenAPI(provider="openai")
            image_prompt = spec.get("_image_prompt", "")
            if not image_prompt:
                logger.warning(
                    "Carousel %s is photo-forward but has no _image_prompt. "
                    "Skipping image generation.", carousel_id,
                )
            else:
                try:
                    carousel_output = output_dir / carousel_id
                    carousel_output.mkdir(parents=True, exist_ok=True)
                    bg_path = carousel_output / "background.png"
                    background_image_path = image_gen.generate(
                        prompt=image_prompt,
                        width=IMAGE_GEN_WIDTH,
                        height=IMAGE_GEN_HEIGHT,
                        output_path=bg_path,
                        style="natural",
                    )
                    # Strip metadata only (no noise) — the rendered slides
                    # get noise applied later, avoiding double-noising
                    background_image_path = clean_image(
                        background_image_path,
                        add_noise=False,
                    )
                    logger.info("Generated background image: %s", background_image_path)
                except Exception as e:
                    logger.error(
                        "Failed to generate background for %s: %s", carousel_id, e,
                    )

        # Step 2: Build slide list for CarouselAssembler
        slides = []

        # Hook slide — guard against null hook_text from Claude
        hook_text = spec.get("hook_text") or ""
        hook_context = {
            "slide_type": "hook",
            "headline": hook_text,
        }
        if background_image_path:
            hook_context["background_image_url"] = str(background_image_path)
        slides.append(hook_context)

        # Content slides — guard against null content_slides from Claude
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
            if background_image_path:
                slide_context["background_image_url"] = str(background_image_path)
            slides.append(slide_context)

        # CTA slide — guard against null cta_slide from Claude
        cta = spec.get("cta_slide") or {}
        if not isinstance(cta, dict):
            logger.warning("Carousel %s cta_slide is not a dict, using defaults", carousel_id)
            cta = {}
        cta_context = {
            "slide_type": "cta",
            "cta_primary": cta.get("cta_primary") or "Follow @slatedapp",
            "cta_secondary": cta.get("cta_secondary") or "",
            "handle": "@slatedapp",
        }
        if background_image_path:
            cta_context["background_image_url"] = str(background_image_path)
        slides.append(cta_context)

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
