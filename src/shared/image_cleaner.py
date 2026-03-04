"""
Image Metadata Cleaner

Strips all metadata (EXIF, IPTC, XMP, PNG text chunks) from images and applies
subtle post-processing to defeat AI-content fingerprinting. Pinterest's primary
detection layer scans DigitalSourceType, Software tags, and XMP data — re-saving
pixel data through Pillow discards all of these.

Usage:
    from src.shared.image_cleaner import clean_image
    clean_image(Path("pin.png"))          # overwrite in place
    clean_image(src, dst, add_noise=False) # copy without noise
"""

import logging
import random
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def _add_gaussian_noise(image: Image.Image, sigma: float = 1.5) -> Image.Image:
    """Add subtle Gaussian noise to RGB channels only.

    Alters the pixel-level frequency fingerprint without visible quality loss.
    Sigma of 1.5 is imperceptible at display sizes. For RGBA images, noise is
    applied only to the RGB channels — the alpha channel is preserved intact.
    """
    arr = np.array(image, dtype=np.float32)
    if image.mode == "RGBA":
        # Only add noise to RGB channels, preserve alpha
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3:4]
        noise = np.random.normal(0.0, sigma, rgb.shape).astype(np.float32)
        rgb = np.clip(rgb + noise, 0.0, 255.0)
        arr = np.concatenate([rgb, alpha], axis=2).astype(np.uint8)
    else:
        noise = np.random.normal(0.0, sigma, arr.shape).astype(np.float32)
        arr = np.clip(arr + noise, 0.0, 255.0).astype(np.uint8)
    return Image.fromarray(arr, mode=image.mode)


def clean_image(
    input_path: Path,
    output_path: Optional[Path] = None,
    add_noise: bool = True,
    noise_sigma: float = 1.5,
    jpeg_quality: Optional[int] = None,
) -> Path:
    """Strip metadata from an image and optionally apply anti-detection noise.

    Opens the image (loading pixel data only), converts to RGB, optionally adds
    Gaussian noise, and saves as JPEG with no metadata. When output_path is None
    the input file is overwritten in place.

    Args:
        input_path: Source image file.
        output_path: Destination path. Defaults to input_path (overwrite).
        add_noise: Whether to add Gaussian noise.
        noise_sigma: Standard deviation of the noise.
        jpeg_quality: JPEG quality 0-100. None picks a random value in 89-94.

    Returns:
        The path the cleaned image was written to.
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path
    else:
        output_path = Path(output_path)

    try:
        if jpeg_quality is None:
            jpeg_quality = random.randint(89, 94)

        # Detect input format to preserve it (PNG carousel slides must stay PNG)
        input_ext = input_path.suffix.lower()
        is_png = input_ext == ".png"

        # Open and load pixel data — metadata is NOT carried over
        with Image.open(input_path) as img:
            if is_png:
                # Preserve RGBA for PNG (carousel slides need transparency support)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                else:
                    img = img.copy()
            else:
                # Convert to RGB for JPEG output
                if img.mode in ("RGBA", "LA", "PA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                else:
                    img = img.copy()

        if add_noise:
            img = _add_gaussian_noise(img, sigma=noise_sigma)

        # Save in the same format as input — PNG stays PNG, JPEG stays JPEG
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if is_png:
            img.save(output_path, format="PNG")
        else:
            img.save(output_path, format="JPEG", quality=jpeg_quality)

        logger.info(
            "Cleaned image: %s -> %s (quality=%d, noise=%s)",
            input_path,
            output_path,
            jpeg_quality,
            add_noise,
        )
        return output_path

    except (OSError, ValueError) as e:
        logger.warning("Image cleaning failed for %s: %s", input_path, e)
        return input_path
