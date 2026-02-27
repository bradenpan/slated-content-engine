"""
Google Drive API Wrapper

Uploads pin images to Google Drive for inline preview in Google Sheets.
Uses the same service account credentials as the Sheets API (just adds
the Drive scope). Images are set to "anyone with link can view" so
Google Sheets =IMAGE() formulas can render them.

Storage: A single folder called "pinterest-pipeline-pins" in the service
account's Drive space. Previous week's images are deleted before uploading
new ones — the user never sees or manages this folder.

Environment variables required:
- GOOGLE_SHEETS_CREDENTIALS_JSON (base64-encoded service account JSON)
"""

import os
import json
import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DRIVE_FOLDER_NAME = "pinterest-pipeline-pins"


class DriveAPIError(Exception):
    """Raised when Google Drive operations fail."""
    pass


class DriveAPI:
    """Client for uploading pin images to Google Drive."""

    def __init__(self, credentials_json: Optional[str] = None):
        """
        Initialize the Google Drive client.

        Uses the same base64-encoded service account JSON as SheetsAPI.

        Args:
            credentials_json: Base64-encoded service account JSON.
                              Falls back to GOOGLE_SHEETS_CREDENTIALS_JSON env var.
        """
        creds_b64 = credentials_json or os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", "")

        if not creds_b64:
            raise DriveAPIError(
                "Google credentials not provided. "
                "Set GOOGLE_SHEETS_CREDENTIALS_JSON env var."
            )

        try:
            creds_json = base64.b64decode(creds_b64).decode("utf-8")
            creds_dict = json.loads(creds_json)
        except Exception as e:
            raise DriveAPIError(f"Failed to decode service account credentials: {e}") from e

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://www.googleapis.com/auth/drive.file"],
            )
            self.drive = build("drive", "v3", credentials=credentials)
            logger.info("Google Drive API initialized")

        except ImportError as e:
            raise DriveAPIError(
                "Google API libraries not installed. "
                "Install: google-api-python-client google-auth"
            ) from e
        except Exception as e:
            raise DriveAPIError(f"Failed to initialize Google Drive API: {e}") from e

        self._folder_id: Optional[str] = None

    def _get_or_create_folder(self) -> str:
        """
        Find or create the pin images folder in Drive.

        Returns:
            str: The folder ID.
        """
        if self._folder_id:
            return self._folder_id

        # Search for existing folder
        try:
            results = self.drive.files().list(
                q=(
                    f"name='{DRIVE_FOLDER_NAME}' "
                    f"and mimeType='application/vnd.google-apps.folder' "
                    f"and trashed=false"
                ),
                fields="files(id)",
                spaces="drive",
            ).execute()

            files = results.get("files", [])
            if files:
                self._folder_id = files[0]["id"]
                logger.info("Found existing Drive folder: %s", self._folder_id)
                return self._folder_id

        except Exception as e:
            logger.warning("Error searching for Drive folder: %s", e)

        # Create new folder
        try:
            file_metadata = {
                "name": DRIVE_FOLDER_NAME,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = self.drive.files().create(
                body=file_metadata,
                fields="id",
            ).execute()

            self._folder_id = folder["id"]
            logger.info("Created Drive folder: %s", self._folder_id)
            return self._folder_id

        except Exception as e:
            raise DriveAPIError(f"Failed to create Drive folder: {e}") from e

    def _clear_folder(self, folder_id: str) -> int:
        """
        Delete all files in a folder (previous week's images).

        Args:
            folder_id: The folder to clear.

        Returns:
            int: Number of files deleted.
        """
        deleted = 0
        try:
            results = self.drive.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id, name)",
                spaces="drive",
                pageSize=100,
            ).execute()

            for file in results.get("files", []):
                try:
                    self.drive.files().delete(fileId=file["id"]).execute()
                    deleted += 1
                except Exception as e:
                    logger.warning("Failed to delete %s: %s", file["name"], e)

            if deleted:
                logger.info("Cleared %d files from Drive folder", deleted)

        except Exception as e:
            logger.warning("Error clearing Drive folder: %s", e)

        return deleted

    def upload_image(self, file_path: Path, filename: Optional[str] = None) -> str:
        """
        Upload a single image to Drive and make it publicly viewable.

        Args:
            file_path: Local path to the image file.
            filename: Optional filename override.

        Returns:
            str: Public view URL for use in Sheets =IMAGE() formula.
        """
        folder_id = self._get_or_create_folder()
        name = filename or file_path.name

        try:
            from googleapiclient.http import MediaFileUpload

            file_metadata = {
                "name": name,
                "parents": [folder_id],
            }
            # Detect actual image format from magic bytes (file may be JPEG
            # with .png extension after pin_assembler size optimization)
            with open(file_path, "rb") as img_f:
                header = img_f.read(12)
            if header[:2] == b"\xff\xd8":
                mime_type = "image/jpeg"
            elif header[:4] == b"\x89PNG":
                mime_type = "image/png"
            elif header[:4] == b"RIFF" and header[8:12] == b"WEBP":
                mime_type = "image/webp"
            else:
                mime_type = "image/png"  # Default fallback

            media = MediaFileUpload(
                str(file_path),
                mimetype=mime_type,
                resumable=False,
            )

            uploaded = self.drive.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
            ).execute()

            file_id = uploaded["id"]

            # Set "anyone with link can view"
            self.drive.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()

            url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"
            logger.debug("Uploaded %s -> %s", name, url)
            return url

        except Exception as e:
            raise DriveAPIError(f"Failed to upload {name}: {e}") from e

    def download_image(self, file_id: str, output_path: Path) -> Path:
        """
        Download an image from Drive by file ID.

        Args:
            file_id: The Drive file ID.
            output_path: Local path to save the downloaded file.

        Returns:
            Path: The output path.
        """
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io

            request = self.drive.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(fh.getvalue())
            logger.debug("Downloaded Drive file %s -> %s", file_id, output_path)
            return output_path

        except Exception as e:
            raise DriveAPIError(f"Failed to download file {file_id}: {e}") from e

    def upload_pin_images(self, generated_pins: list[dict], pins_dir: Path) -> dict[str, str]:
        """
        Upload all pin images to Drive, clearing previous week's images first.

        Args:
            generated_pins: List of pin dicts with pin_id fields.
            pins_dir: Directory containing rendered pin PNGs.

        Returns:
            dict: pin_id -> public view URL mapping.
        """
        if not generated_pins:
            return {}

        # Clear previous images
        folder_id = self._get_or_create_folder()
        self._clear_folder(folder_id)

        # Upload each pin image
        url_map: dict[str, str] = {}
        uploaded = 0
        failed = 0

        for pin in generated_pins:
            pin_id = pin.get("pin_id", "")
            if not pin_id:
                continue

            image_path = pins_dir / f"{pin_id}.png"
            if not image_path.exists():
                logger.warning("Pin image not found: %s", image_path)
                failed += 1
                continue

            try:
                url = self.upload_image(image_path)
                url_map[pin_id] = url
                uploaded += 1
            except DriveAPIError as e:
                logger.error("Failed to upload pin %s: %s", pin_id, e)
                failed += 1

        logger.info(
            "Drive upload complete: %d uploaded, %d failed out of %d pins",
            uploaded, failed, len(generated_pins),
        )
        return url_map
