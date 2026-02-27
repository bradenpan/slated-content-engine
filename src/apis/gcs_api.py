"""
Google Cloud Storage API Wrapper

Uploads pin images and blog hero images to Google Cloud Storage for inline
preview in Google Sheets via =IMAGE() formulas.

Uses the same service account credentials as the Sheets API (just needs
the storage scope). Objects are stored in a single bucket with public
read access (allUsers objectViewer), so =IMAGE() formulas can render them.

Storage: A single bucket (default "slated-pipeline-pins"). Previous week's
pin images are deleted before uploading new ones.

Environment variables required:
- GOOGLE_SHEETS_CREDENTIALS_JSON (base64-encoded service account JSON)
- GCS_BUCKET_NAME (optional, defaults to "slated-pipeline-pins")
"""

import os
import json
import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_BUCKET_NAME = "slated-pipeline-pins"


class GcsAPIError(Exception):
    """Raised when Google Cloud Storage operations fail."""
    pass


class GcsAPI:
    """Client for uploading pin images to Google Cloud Storage."""

    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize the Google Cloud Storage client.

        Uses the same base64-encoded service account JSON as SheetsAPI.
        If credentials are missing, logs a warning and sets self.client = None
        so callers can check availability without crashing.

        Args:
            bucket_name: GCS bucket name. Falls back to GCS_BUCKET_NAME env var,
                         then to DEFAULT_BUCKET_NAME.
        """
        self.bucket_name = (
            bucket_name
            or os.environ.get("GCS_BUCKET_NAME", "")
            or DEFAULT_BUCKET_NAME
        )
        self.client = None
        self.bucket = None

        creds_b64 = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", "")

        if not creds_b64:
            logger.warning(
                "Google credentials not provided (GOOGLE_SHEETS_CREDENTIALS_JSON). "
                "GCS uploads will be skipped."
            )
            return

        try:
            creds_json = base64.b64decode(creds_b64).decode("utf-8")
            creds_dict = json.loads(creds_json)
        except Exception as e:
            logger.warning("Failed to decode service account credentials: %s", e)
            return

        try:
            from google.oauth2 import service_account
            from google.cloud import storage

            try:
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict,
                )
            except ValueError:
                # pyca/cryptography may reject keys with non-standard parameters
                # (e.g., incorrect CRT coefficients). Fall back to python-rsa signer.
                from google.auth import _default as _auth_default
                from google.auth.crypt import _python_rsa

                signer = _python_rsa.RSASigner.from_service_account_info(creds_dict)
                credentials = service_account.Credentials(
                    signer=signer,
                    service_account_email=creds_dict.get("client_email"),
                    token_uri=creds_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
                    project_id=creds_dict.get("project_id"),
                )
            self.client = storage.Client(
                credentials=credentials,
                project=creds_dict.get("project_id"),
            )
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(
                "GCS API initialized (bucket=%s, project=%s)",
                self.bucket_name, creds_dict.get("project_id"),
            )

        except ImportError:
            logger.warning(
                "google-cloud-storage not installed. "
                "Install: pip install google-cloud-storage"
            )
        except Exception as e:
            logger.warning("Failed to initialize GCS client: %s", e)

    def upload_image(self, local_path: Path, remote_name: Optional[str] = None) -> Optional[str]:
        """
        Upload a single image to GCS and return its public URL.

        Args:
            local_path: Local path to the image file.
            remote_name: Object name in the bucket. Defaults to the filename.

        Returns:
            Public URL string, or None if upload fails.
        """
        if not self.client:
            logger.warning("GCS client not available, skipping upload of %s", local_path)
            return None

        name = remote_name or Path(local_path).name

        try:
            # Detect MIME type from magic bytes
            from src.utils.image_utils import detect_mime_type
            with open(local_path, "rb") as img_f:
                header = img_f.read(12)
            detected = detect_mime_type(header)
            content_type = detected if detected != "application/octet-stream" else "image/png"

            blob = self.bucket.blob(name)
            blob.upload_from_filename(str(local_path), content_type=content_type)

            url = self.get_public_url(name)
            logger.debug("Uploaded %s -> %s", name, url)
            return url

        except Exception as e:
            logger.error("Failed to upload %s to GCS: %s", name, e)
            return None

    def download_image(self, object_name: str, output_path: Path) -> Optional[Path]:
        """
        Download an image from GCS by object name.

        Args:
            object_name: The object name in the bucket.
            output_path: Local path to save the downloaded file.

        Returns:
            The output path on success, None on failure.
        """
        if not self.client:
            logger.warning("GCS client not available, cannot download %s", object_name)
            return None

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            blob = self.bucket.blob(object_name)
            blob.download_to_filename(str(output_path))
            logger.debug("Downloaded GCS object %s -> %s", object_name, output_path)
            return output_path

        except Exception as e:
            logger.error("Failed to download %s from GCS: %s", object_name, e)
            return None

    def upload_pin_images(
        self,
        pin_results: list[dict],
        generated_dir: Path,
    ) -> dict[str, str]:
        """
        Upload all pin images to GCS, clearing previous pin images first.

        Args:
            pin_results: List of pin dicts with pin_id fields.
            generated_dir: Directory containing rendered pin PNGs.

        Returns:
            dict: pin_id -> public URL mapping.
        """
        if not self.client:
            return {}

        if not pin_results:
            return {}

        # Clear previous pin images (files matching W*-*.png pattern)
        self.delete_old_images(prefix="W")

        url_map: dict[str, str] = {}
        uploaded = 0
        failed = 0

        for pin in pin_results:
            pin_id = pin.get("pin_id", "")
            if not pin_id:
                continue

            image_path = generated_dir / f"{pin_id}.png"
            if not image_path.exists():
                logger.warning("Pin image not found: %s", image_path)
                failed += 1
                continue

            url = self.upload_image(image_path)
            if url:
                url_map[pin_id] = url
                uploaded += 1
            else:
                failed += 1

        logger.info(
            "GCS pin upload complete: %d uploaded, %d failed out of %d pins",
            uploaded, failed, len(pin_results),
        )
        return url_map

    def upload_blog_hero_images(
        self,
        blog_results: dict,
        generated_dir: Path,
    ) -> dict[str, str]:
        """
        Upload blog hero images to GCS.

        Searches for hero images by slug in the generated directory.

        Args:
            blog_results: Blog generation results dict (post_id -> data).
            generated_dir: Directory containing pin and hero images.

        Returns:
            dict: post_id -> public URL mapping.
        """
        if not self.client:
            return {}

        urls: dict[str, str] = {}
        extensions = [".jpg", ".jpeg", ".png", ".webp"]

        for post_id, post_data in blog_results.items():
            if post_data.get("status") != "success":
                continue

            slug = post_data.get("slug", "")
            if not slug:
                continue

            # Find the hero image file
            hero_path = None
            for ext in extensions:
                candidate = generated_dir / f"{slug}-hero{ext}"
                if candidate.exists():
                    hero_path = candidate
                    break

            if not hero_path:
                # Also check blog output dir
                blog_dir = generated_dir.parent / "blog"
                for ext in extensions:
                    candidate = blog_dir / f"{slug}{ext}"
                    if candidate.exists():
                        hero_path = candidate
                        break

            if not hero_path:
                logger.debug("No hero image found for blog %s (slug=%s)", post_id, slug)
                continue

            remote_name = f"blog-hero-{slug}{hero_path.suffix}"
            url = self.upload_image(hero_path, remote_name)
            if url:
                urls[post_id] = url
                logger.debug("Uploaded blog hero for %s: %s", post_id, url[:60])

        return urls

    def delete_old_images(self, prefix: Optional[str] = None) -> int:
        """
        Delete objects in the bucket, optionally filtered by prefix.

        Args:
            prefix: If provided, only delete objects whose names start with
                    this prefix.

        Returns:
            int: Number of objects deleted.
        """
        if not self.client:
            return 0

        deleted = 0
        try:
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            for blob in blobs:
                try:
                    blob.delete()
                    deleted += 1
                except Exception as e:
                    logger.warning("Failed to delete GCS object %s: %s", blob.name, e)

            if deleted:
                logger.info("Deleted %d objects from GCS (prefix=%s)", deleted, prefix)

        except Exception as e:
            logger.warning("Error listing/deleting GCS objects: %s", e)

        return deleted

    def get_public_url(self, object_name: str) -> str:
        """
        Return the public URL for an object.

        Args:
            object_name: The object name in the bucket.

        Returns:
            str: Public URL in the format
                 https://storage.googleapis.com/{bucket}/{name}
        """
        return f"https://storage.googleapis.com/{self.bucket_name}/{object_name}"

    def extract_object_name(self, gcs_url: str) -> str:
        """
        Extract the object name from a GCS public URL.

        Args:
            gcs_url: URL like https://storage.googleapis.com/bucket/object-name

        Returns:
            str: The object name, or empty string if not a valid GCS URL.
        """
        prefix = f"https://storage.googleapis.com/{self.bucket_name}/"
        if gcs_url.startswith(prefix):
            return gcs_url[len(prefix):]
        return ""


