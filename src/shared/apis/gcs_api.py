"""
Google Cloud Storage API Wrapper

Uploads pin images and blog hero images to Google Cloud Storage for inline
preview in Google Sheets via =IMAGE() formulas.

Uses the same service account credentials as the Sheets API (just needs
the storage scope). Objects are stored in a single bucket with public
read access (allUsers objectViewer), so =IMAGE() formulas can render them.

Storage: A single bucket (default "slated-pipeline-pins"). Pin images from
2+ weeks ago are deleted before uploading new ones (keeps current and
previous week alive to avoid breaking scheduled pins still pending).

Environment variables required:
- GOOGLE_SHEETS_CREDENTIALS_JSON (base64-encoded service account JSON)
- GCS_BUCKET_NAME (optional, defaults to "slated-pipeline-pins")
"""

import os
import json
import base64
import logging
import re
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
        self._init_error: str | None = None

        creds_b64 = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", "")

        if not creds_b64:
            self._init_error = "Google credentials not provided (GOOGLE_SHEETS_CREDENTIALS_JSON)"
            logger.warning(
                "%s. GCS uploads will be skipped.", self._init_error,
            )
            return

        try:
            creds_json = base64.b64decode(creds_b64).decode("utf-8")
            creds_dict = json.loads(creds_json)
        except Exception as e:
            self._init_error = f"Failed to decode service account credentials: {e}"
            logger.warning("%s", self._init_error)
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
            self._init_error = "google-cloud-storage not installed"
            logger.warning(
                "%s. Install: pip install google-cloud-storage",
                self._init_error,
            )
        except Exception as e:
            self._init_error = f"Failed to initialize GCS client: {e}"
            logger.warning("%s", self._init_error)

    @property
    def is_available(self) -> bool:
        """Check whether the GCS client was initialized successfully."""
        return self.client is not None

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
            # Reject empty files
            file_size = Path(local_path).stat().st_size
            if file_size == 0:
                logger.warning("Skipping upload of empty file: %s", local_path)
                return None

            # Detect MIME type from magic bytes
            from src.shared.utils.image_utils import detect_mime_type
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
            logger.warning("GCS client not configured — skipping pin image upload")
            return {}

        if not pin_results:
            return {}

        # Parse current week number from pin_ids (e.g., "W10-01" → 10).
        # Only delete images from 2+ weeks ago (keeps current and previous week).
        # Validate that all pins share the same week to avoid misscoped cleanup.
        week_re = re.compile(r'^W(\d+)-')
        weeks_seen: set[int] = set()
        for pin in pin_results:
            pid = pin.get("pin_id") or ""
            m = week_re.match(pid)
            if m:
                weeks_seen.add(int(m.group(1)))

        if len(weeks_seen) == 1:
            current_week = weeks_seen.pop()
            self.delete_old_week_images(current_week)
        elif len(weeks_seen) > 1:
            # Mixed-week batch — use the highest week to avoid deleting too aggressively
            current_week = max(weeks_seen)
            logger.warning(
                "Mixed week batch detected (weeks: %s), using W%d for cleanup",
                sorted(weeks_seen), current_week,
            )
            self.delete_old_week_images(current_week)
        else:
            logger.warning(
                "Could not parse week number from any pin_id, skipping GCS cleanup",
            )

        url_map: dict[str, str] = {}
        uploaded = 0
        failed = 0

        for pin in pin_results:
            pin_id = pin.get("pin_id") or ""
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
            logger.warning("GCS client not configured — skipping blog hero image upload")
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

    def delete_old_week_images(self, current_week: int) -> int:
        """Delete pin images from 2+ weeks before current_week.

        Keeps W(current) and W(current-1) alive. Deletes W(current-2) and earlier.
        Example: uploading W10 pins deletes W8, W7, ... but keeps W9, W10.

        Also cleans up ai-heroes/ objects following the same week logic.

        Args:
            current_week: The week number currently being uploaded (e.g., 10).

        Returns:
            int: Number of objects deleted.
        """
        if not self.client:
            logger.warning("GCS client not configured — skipping delete_old_week_images")
            return 0

        # Regex to extract week number from blob names like "W9-01.png" or "ai-heroes/W9-24-ai-hero.png"
        week_pattern = re.compile(r'W(\d+)-')

        # Note: week numbers are compared without year context. This is safe
        # given weekly pipeline cadence (old-year blobs are deleted long before
        # the same week number recurs). If the pipeline ever skips 50+ weeks,
        # same-numbered blobs from a prior year could be incorrectly matched.
        def should_keep(blob_week: int) -> bool:
            """Return True if blob_week should be kept (current or previous week)."""
            if blob_week == current_week or blob_week == current_week - 1:
                return True
            # Year boundary: when current is W1, current_week - 1 = 0 (no real week).
            # The actual previous week is W52 or W53 (ISO years vary).
            if current_week == 1 and blob_week in (52, 53):
                return True
            return False

        deleted = 0
        try:
            for blob_prefix in ("W", "ai-heroes/W"):
                blobs = self.client.list_blobs(self.bucket_name, prefix=blob_prefix)
                for blob in blobs:
                    match = week_pattern.search(blob.name)
                    if not match:
                        continue
                    blob_week = int(match.group(1))
                    if should_keep(blob_week):
                        continue
                    try:
                        blob.delete()
                        deleted += 1
                    except Exception as e:
                        logger.warning("Failed to delete GCS object %s: %s", blob.name, e)

            if deleted:
                prev_week = current_week - 1 if current_week > 1 else "52/53"
                logger.info(
                    "Deleted %d old week images from GCS (current_week=W%d, keeping W%d and W%s)",
                    deleted, current_week, current_week, prev_week,
                )

        except Exception as e:
            logger.warning("Error listing/deleting old week images: %s", e)

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


