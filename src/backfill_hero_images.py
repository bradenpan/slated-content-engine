"""
One-off script: download correct hero images from Google Sheet URLs
and save them to data/generated/pins/{slug}-hero.{ext} so they can
be committed to git and picked up by blog_deployer.

For each blog row in the Content Queue:
  - status "approved"     -> use column I (Thumbnail) URL
  - status "use_ai_image" -> use column M (AI Image) URL

Usage:
    python -m src.backfill_hero_images                              # dry-run (Sheets API)
    python -m src.backfill_hero_images --run                        # download via Sheets API
    python -m src.backfill_hero_images --xlsx path/to/file.xlsx     # dry-run from xlsx export
    python -m src.backfill_hero_images --xlsx path/to/file.xlsx --run  # download from xlsx
"""

import re
import sys
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PIN_OUTPUT_DIR = Path("data/generated/pins")

# Column indices matching sheets_api.py
CQ_COL_ID = 0        # A
CQ_COL_TYPE = 1       # B
CQ_COL_BLOG_URL = 5   # F (slug for blogs)
CQ_COL_THUMBNAIL = 8  # I
CQ_COL_STATUS = 9     # J
CQ_COL_AI_IMAGE = 12  # M


def _extract_url_from_formula(cell_value) -> str:
    """Extract the URL from an =IMAGE("url") formula, or return as-is if plain URL."""
    if not cell_value:
        return ""
    cell_value = str(cell_value)
    match = re.search(r'=IMAGE\("([^"]+)"\)', cell_value)
    if match:
        return match.group(1)
    # Maybe it's already a plain URL
    if cell_value.startswith("http"):
        return cell_value
    return ""


def _extension_from_url(url: str) -> str:
    """Guess file extension from URL path."""
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        return ext
    return ".jpg"  # safe default for stock images


def _load_rows_from_xlsx(xlsx_path: str) -> list[list]:
    """Load Content Queue rows from an xlsx export."""
    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Content Queue"]
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append(list(row))
    return rows


def _load_rows_from_sheets() -> list[list]:
    """Load Content Queue rows from Google Sheets API."""
    from dotenv import load_dotenv
    load_dotenv()
    from src.apis.sheets_api import SheetsAPI
    sheets = SheetsAPI()
    result = sheets.sheets.values().get(
        spreadsheetId=sheets.sheet_id,
        range="'Content Queue'!A:M",
        valueRenderOption="FORMULA",
    ).execute()
    return result.get("values", [])


def main():
    run_mode = "--run" in sys.argv
    if not run_mode:
        print("DRY RUN \u2014 pass --run to actually download images\n")

    # Determine data source
    xlsx_path = None
    if "--xlsx" in sys.argv:
        idx = sys.argv.index("--xlsx")
        if idx + 1 < len(sys.argv):
            xlsx_path = sys.argv[idx + 1]

    if xlsx_path:
        print(f"Reading from xlsx: {xlsx_path}\n")
        rows = _load_rows_from_xlsx(xlsx_path)
    else:
        print("Reading from Google Sheets API\n")
        rows = _load_rows_from_sheets()

    if len(rows) < 2:
        print("No data rows found in Content Queue.")
        return

    downloaded = 0
    skipped = 0
    errors = 0

    for row in rows[1:]:  # skip header
        if not row or len(row) <= CQ_COL_STATUS:
            continue

        row_type = row[CQ_COL_TYPE] if len(row) > CQ_COL_TYPE else ""
        if row_type != "blog":
            continue

        item_id = row[CQ_COL_ID] if len(row) > CQ_COL_ID else ""
        slug = row[CQ_COL_BLOG_URL] if len(row) > CQ_COL_BLOG_URL else ""
        status = str(row[CQ_COL_STATUS]).strip() if len(row) > CQ_COL_STATUS else ""

        if not slug:
            print(f"  SKIP {item_id}: no slug")
            skipped += 1
            continue

        # Pick the right column based on status
        if status == "approved":
            raw = row[CQ_COL_THUMBNAIL] if len(row) > CQ_COL_THUMBNAIL else ""
            source_label = "thumbnail (col I)"
        elif status == "use_ai_image":
            raw = row[CQ_COL_AI_IMAGE] if len(row) > CQ_COL_AI_IMAGE else ""
            source_label = "AI image (col M)"
        else:
            print(f"  SKIP {item_id} ({slug}): status is '{status}', not approved/use_ai_image")
            skipped += 1
            continue

        url = _extract_url_from_formula(raw)
        if not url:
            print(f"  SKIP {item_id} ({slug}): no URL in {source_label}")
            skipped += 1
            continue

        ext = _extension_from_url(url)
        hero_filename = f"{slug}-hero{ext}"
        hero_path = PIN_OUTPUT_DIR / hero_filename

        print(f"  {'DOWNLOAD' if run_mode else 'WOULD DOWNLOAD'} {item_id} ({slug})")
        print(f"    from: {url[:100]}")
        print(f"    to:   {hero_path}")

        if run_mode:
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()

                # Detect actual content type
                ct = resp.headers.get("content-type", "")
                if "png" in ct:
                    ext = ".png"
                elif "webp" in ct:
                    ext = ".webp"
                elif "jpeg" in ct or "jpg" in ct:
                    ext = ".jpg"

                # Re-derive path with correct extension
                hero_filename = f"{slug}-hero{ext}"
                hero_path = PIN_OUTPUT_DIR / hero_filename

                PIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                hero_path.write_bytes(resp.content)

                # Clean stale heroes with different extensions
                for old in PIN_OUTPUT_DIR.glob(f"{slug}-hero.*"):
                    if old.suffix != ext:
                        old.unlink()
                        print(f"    cleaned stale: {old.name}")

                downloaded += 1
                print(f"    SAVED ({len(resp.content)} bytes)")

            except Exception as e:
                errors += 1
                print(f"    ERROR: {e}")

    print(f"\nDone. Downloaded: {downloaded}, Skipped: {skipped}, Errors: {errors}")
    if downloaded > 0 and run_mode:
        print("\nNext steps:")
        print("  git add data/generated/pins/*-hero.*")
        print('  git commit -m "fix: backfill blog hero images from Sheet"')
        print("  git push")
        print("  Then trigger deploy-to-preview.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
