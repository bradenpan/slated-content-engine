"""
AI Image Generation Wrapper (DALL-E / Flux Pro)

Tier 2 image source for the pipeline. Used for custom compositions,
lifestyle scenes, or when stock photography doesn't have what's needed.

Supports:
- OpenAI gpt-image-1.5 via OpenAI API
- Flux Pro via Replicate API

Cost: ~$0.03-0.08 per image
Quality mitigation strategies:
- Prefer overhead/flat-lay compositions (avoids hand/utensil artifacts)
- Use consistent style anchors in prompts (lighting, angle, surface, color temp)
- Post-process color grading for brand consistency
- 10-25% failure rate expected; retry logic with slight prompt modification included

Environment variables required:
- OPENAI_API_KEY (for DALL-E)
- REPLICATE_API_TOKEN (for Flux Pro)
- IMAGE_GEN_PROVIDER (optional, "openai" or "replicate", defaults to "openai")
"""

import os
import io
import time
import uuid
import base64
import logging
from pathlib import Path
from typing import Optional

import requests

from src.shared.paths import PIN_OUTPUT_DIR
from src.shared.config import (
    IMAGE_COST_PER_IMAGE as COST_PER_IMAGE,
    MIN_IMAGE_SIZE,
)

logger = logging.getLogger(__name__)


class ImageGenError(Exception):
    """Raised when AI image generation fails."""
    pass


class ImageGenAPI:
    """Wrapper for AI image generation APIs (OpenAI DALL-E and Replicate Flux Pro)."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the image generation client.

        Args:
            provider: "openai" for DALL-E or "replicate" for Flux Pro.
                      Falls back to IMAGE_GEN_PROVIDER env var, then defaults to "openai".
            api_key: API key. Falls back to OPENAI_API_KEY or REPLICATE_API_TOKEN
                     depending on provider.
        """
        self.provider = (
            provider
            or os.environ.get("IMAGE_GEN_PROVIDER", "openai")
        ).lower()

        if self.provider == "openai":
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
            if not self.api_key:
                raise ImageGenError("OPENAI_API_KEY required for OpenAI image generation.")
        elif self.provider == "replicate":
            self.api_key = api_key or os.environ.get("REPLICATE_API_TOKEN", "")
            if not self.api_key:
                raise ImageGenError("REPLICATE_API_TOKEN required for Replicate image generation.")
        else:
            raise ImageGenError(f"Unknown provider: {self.provider}. Use 'openai' or 'replicate'.")

        # Cumulative cost tracking
        self.total_cost_usd = 0.0
        self.total_images_generated = 0

        logger.info("Image generation initialized: provider=%s", self.provider)

    def generate(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1536,
        output_path: Optional[Path] = None,
        style: str = "natural",
        max_retries: int = 2,
    ) -> Path:
        """
        Generate an image from a text prompt.

        Implements retry logic: on failure, retries up to max_retries times
        with a slight prompt modification to increase variance.

        Args:
            prompt: Detailed image generation prompt (from Claude via image_prompt.md).
            width: Image width in pixels.
            height: Image height in pixels (default 1536 for ~2:3 pin ratio).
            output_path: Path to save the generated image. Auto-generated if None.
            style: Style hint - "natural" for food photography, "vivid" for stylized.
            max_retries: Number of retry attempts on failure (10-25% failure rate expected).

        Returns:
            Path: Path to the saved image file.

        Raises:
            ImageGenError: If generation fails after all retries.
        """
        if output_path is None:
            PIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = PIN_OUTPUT_DIR / f"{uuid.uuid4().hex[:12]}.png"

        last_error = None
        current_prompt = prompt

        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    "Generating image (attempt %d/%d): provider=%s size=%dx%d",
                    attempt + 1, max_retries + 1, self.provider, width, height,
                )

                if self.provider == "openai":
                    image_bytes = self._generate_openai(current_prompt, width, height, style)
                elif self.provider == "replicate":
                    image_bytes = self._generate_replicate(current_prompt, width, height)
                else:
                    raise ImageGenError(f"Unknown provider: {self.provider}")

                # Validate the generated image
                if not self._validate_image(image_bytes, width, height):
                    raise ImageGenError("Generated image failed validation (corrupt, blank, or wrong dimensions).")

                # Save to disk
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(image_bytes)

                # Track cost
                cost = COST_PER_IMAGE.get(self.provider, 0.05)
                self.total_cost_usd += cost
                self.total_images_generated += 1

                logger.info(
                    "Image generated: %s (%d bytes, $%.2f). Session total: %d images, $%.2f.",
                    output_path, len(image_bytes), cost,
                    self.total_images_generated, self.total_cost_usd,
                )

                return output_path

            except ImageGenError as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        "Image generation failed (attempt %d/%d): %s. Retrying with modified prompt...",
                        attempt + 1, max_retries + 1, e,
                    )
                    # Modify prompt slightly for retry to increase generation variance
                    current_prompt = self._modify_prompt_for_retry(prompt, attempt + 1)
                    time.sleep(2)  # Brief pause before retry
                else:
                    logger.error("Image generation failed after %d attempts.", max_retries + 1)

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        "Unexpected error in image generation (attempt %d/%d): %s",
                        attempt + 1, max_retries + 1, e,
                    )
                    current_prompt = self._modify_prompt_for_retry(prompt, attempt + 1)
                    time.sleep(2)
                else:
                    logger.error("Image generation failed after %d attempts: %s", max_retries + 1, e)

        raise ImageGenError(
            f"Image generation failed after {max_retries + 1} attempts. Last error: {last_error}"
        )

    def _generate_openai(self, prompt: str, width: int, height: int, style: str = "natural") -> bytes:
        """
        Generate image via OpenAI gpt-image-1 API.

        Args:
            prompt: Image generation prompt.
            width: Desired width.
            height: Desired height.
            style: "natural" or "vivid".

        Returns:
            bytes: Raw image data (PNG).
        """
        # OpenAI gpt-image-1 supports specific sizes. Map to closest supported.
        size_str = self._get_openai_size(width, height)

        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                # gpt-image-1.5 is correct — OpenAI's latest image gen model (not gpt-image-1)
                "model": "gpt-image-1.5",
                "prompt": prompt,
                "n": 1,
                "size": size_str,
                "quality": "medium",
            },
            timeout=120,
        )

        if response.status_code != 200:
            error_text = response.text
            try:
                error_data = response.json()
                error_text = error_data.get("error", {}).get("message", response.text)
            except (ValueError, KeyError):
                pass
            raise ImageGenError(f"OpenAI image generation failed (HTTP {response.status_code}): {error_text}")

        data = response.json()
        data_list = data.get("data") or []
        if not data_list:
            raise ImageGenError("OpenAI returned empty data array")
        image_data = data_list[0]

        # gpt-image-1 returns base64-encoded image
        b64_image = image_data.get("b64_json")
        if b64_image:
            return base64.b64decode(b64_image)

        # Or it might return a URL
        image_url = image_data.get("url")
        if image_url:
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()
            return img_response.content

        raise ImageGenError("OpenAI response contained no image data.")

    def _generate_replicate(self, prompt: str, width: int, height: int) -> bytes:
        """
        Generate image via Replicate Flux Pro API.

        Uses the synchronous prediction endpoint for simplicity.
        Flux Pro model: black-forest-labs/flux-pro

        Args:
            prompt: Image generation prompt.
            width: Desired width.
            height: Desired height.

        Returns:
            bytes: Raw image data.
        """
        # Create prediction using the model-based endpoint (accepts model names
        # directly, unlike /v1/predictions which requires a version SHA hash)
        response = requests.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-pro/predictions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": {
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_outputs": 1,
                    "guidance_scale": 3.5,
                },
            },
            timeout=30,
        )

        if response.status_code not in (200, 201):
            raise ImageGenError(f"Replicate prediction creation failed (HTTP {response.status_code}): {response.text}")

        prediction = response.json()
        prediction_id = prediction.get("id")

        if not prediction_id:
            raise ImageGenError("Replicate returned no prediction ID.")

        # Poll for completion
        max_poll_time = 120  # seconds
        poll_interval = 3  # seconds
        start_time = time.time()

        while time.time() - start_time < max_poll_time:
            status_response = requests.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )

            if status_response.status_code != 200:
                raise ImageGenError(f"Failed to poll prediction status: HTTP {status_response.status_code}")

            status_data = status_response.json()
            status = status_data.get("status")

            if status == "succeeded":
                output = status_data.get("output")
                if isinstance(output, list) and len(output) > 0:
                    image_url = output[0]
                elif isinstance(output, str):
                    image_url = output
                else:
                    raise ImageGenError(f"Unexpected Replicate output format: {output}")

                img_response = requests.get(image_url, timeout=30)
                img_response.raise_for_status()
                return img_response.content

            elif status == "failed":
                error = status_data.get("error", "Unknown error")
                raise ImageGenError(f"Replicate generation failed: {error}")

            elif status in ("starting", "processing"):
                logger.debug("Replicate prediction %s: %s...", prediction_id, status)
                time.sleep(poll_interval)
            else:
                raise ImageGenError(f"Unknown Replicate status: {status}")

        raise ImageGenError(f"Replicate generation timed out after {max_poll_time}s.")

    def _validate_image(self, image_bytes: bytes, expected_width: int = 0, expected_height: int = 0) -> bool:
        """
        Basic quality check on generated image.

        Checks for:
        - Minimum file size (reject blank/corrupt images)
        - Valid image format (PNG/JPEG decodable via Pillow)
        - Approximate dimension check (within 10% tolerance)

        Args:
            image_bytes: Raw image data.
            expected_width: Expected width (0 = skip check).
            expected_height: Expected height (0 = skip check).

        Returns:
            bool: True if image passes validation.
        """
        # Check minimum file size
        if len(image_bytes) < MIN_IMAGE_SIZE:
            logger.warning("Image too small: %d bytes (minimum: %d).", len(image_bytes), MIN_IMAGE_SIZE)
            return False

        # Try to decode with Pillow for format and dimension validation
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()  # Verify it's a valid image

            # Re-open after verify (verify can consume the stream)
            img = Image.open(io.BytesIO(image_bytes))
            actual_width, actual_height = img.size

            logger.debug("Image validated: %dx%d, format=%s", actual_width, actual_height, img.format)

            # Check dimensions if expected values provided (10% tolerance)
            if expected_width > 0 and expected_height > 0:
                width_ok = abs(actual_width - expected_width) / expected_width < 0.1
                height_ok = abs(actual_height - expected_height) / expected_height < 0.1
                if not (width_ok and height_ok):
                    logger.warning(
                        "Image dimensions mismatch: got %dx%d, expected ~%dx%d.",
                        actual_width, actual_height, expected_width, expected_height,
                    )
                    # Still return True -- dimension mismatch is a warning, not a hard failure
                    # The pin assembler will resize anyway

            return True

        except ImportError:
            # Pillow not available -- skip dimension check, just verify non-empty
            logger.debug("Pillow not available; skipping image decode validation.")
            return True
        except Exception as e:
            logger.warning("Image validation failed: %s", e)
            return False

    def _modify_prompt_for_retry(self, original_prompt: str, attempt: int) -> str:
        """
        Slightly modify the prompt for retry to increase generation variance.

        Args:
            original_prompt: The original prompt.
            attempt: Retry attempt number (1-based).

        Returns:
            str: Modified prompt.
        """
        modifiers = [
            "Professional food photography style. ",
            "Magazine-quality composition. ",
            "Clean, well-lit scene. ",
        ]

        modifier = modifiers[attempt % len(modifiers)]
        modified = f"{modifier}{original_prompt}"
        logger.debug("Modified prompt for retry %d: added '%s'", attempt, modifier.strip())
        return modified

    def _get_openai_size(self, width: int, height: int) -> str:
        """
        Map requested dimensions to the closest OpenAI supported size.

        gpt-image-1 supports: 1024x1024, 1024x1536, 1536x1024, auto.

        Args:
            width: Requested width.
            height: Requested height.

        Returns:
            str: OpenAI size string.
        """
        aspect = width / height if height > 0 else 1.0

        if aspect > 1.2:
            return "1536x1024"  # Landscape
        elif aspect < 0.8:
            return "1024x1536"  # Portrait (pin-friendly)
        else:
            return "1024x1024"  # Square


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Image Generation API smoke test")
    print("================================")

    provider = os.environ.get("IMAGE_GEN_PROVIDER", "openai")
    print(f"Provider: {provider}")

    try:
        gen = ImageGenAPI(provider=provider)

        test_prompt = (
            "Overhead shot of a colorful chicken stir fry in a dark wok, "
            "fresh vegetables, warm kitchen lighting, rustic wood surface, "
            "professional food photography"
        )

        print(f"Generating test image...")
        path = gen.generate(
            prompt=test_prompt,
            output_path=Path("test_generated_image.png"),
        )
        print(f"Generated image saved to: {path}")
        print(f"Session cost: ${gen.total_cost_usd:.2f}")
        print(f"Images generated: {gen.total_images_generated}")

    except ImageGenError as e:
        print(f"Image generation error: {e}")
    except Exception as e:
        print(f"Error: {e}")
