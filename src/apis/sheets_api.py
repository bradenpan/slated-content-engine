"""
Google Sheets API Wrapper

Manages the Google Sheet that serves as both the human review interface
and the automation trigger. The Sheet has four tabs:

1. Weekly Review - Data report + content plan for approval
   - Analysis summary, plan details, plan_status column
   - Statuses: pending_review, approved, rejected

2. Content Queue - Generated pins + blog posts for approval
   - Thumbnail, title, description, blog URL, board, schedule
   - content_status column: pending_review, approved, rejected

3. Post Log - Record of posted pins
   - Pin ID, date posted, URL, status (posted / failed)

4. Dashboard - At-a-glance weekly/monthly metrics
   - Auto-populated from analytics pulls

Authentication: Google service account with Sheets API access.
The service account credentials are passed as a base64-encoded JSON string.

Environment variables required:
- GOOGLE_SHEETS_CREDENTIALS_JSON (service account JSON, base64 encoded)
- GOOGLE_SHEET_ID (the spreadsheet ID from the Sheet URL)
- GOOGLE_SHEET_URL (optional, full URL for Slack notification links)
"""

import os
import json
import base64
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Tab names in the Google Sheet
TAB_WEEKLY_REVIEW = "Weekly Review"
TAB_CONTENT_QUEUE = "Content Queue"
TAB_POST_LOG = "Post Log"
TAB_DASHBOARD = "Dashboard"

# === Column Schema: Content Queue Tab ===
# 0-based column indices. Must match the column structure the Apps Script expects.
# Header row: ID | Type | Title | Description | Board | Blog URL | Schedule | Pillar | Thumbnail | Status | Notes | Feedback
CQ_COL_ID = 0           # A: Internal ID (e.g., "W12-01" or "B12-01")
CQ_COL_TYPE = 1         # B: Type (pin / blog)
CQ_COL_TITLE = 2        # C: Title
CQ_COL_DESCRIPTION = 3  # D: Description or summary
CQ_COL_BOARD = 4        # E: Board name (pins only)
CQ_COL_BLOG_URL = 5     # F: Blog post URL
CQ_COL_SCHEDULE = 6     # G: Scheduled date/slot
CQ_COL_PILLAR = 7       # H: Content pillar (1-5)
CQ_COL_THUMBNAIL = 8    # I: Thumbnail URL or image reference
CQ_COL_STATUS = 9       # J: content_status
CQ_COL_NOTES = 10       # K: Reviewer notes
CQ_COL_FEEDBACK = 11    # L: Reviewer feedback for regen

# Expected Content Queue header row — used for validation
EXPECTED_CQ_HEADERS = [
    "ID", "Type", "Title", "Description", "Board", "Blog URL",
    "Schedule", "Pillar", "Thumbnail", "Status", "Notes", "Feedback",
]

# === Sheet Cell References ===
# Weekly Review control cells
WR_CELL_PLAN_STATUS = "B3"
WR_CELL_DEPLOY_STATUS = "B4"
WR_CELL_REGEN_TRIGGER = "B5"

# Content Queue control cells
CQ_CELL_REGEN_TRIGGER = "N1"


class SheetsAPIError(Exception):
    """Raised when Google Sheets operations fail."""
    pass


class SheetsAPI:
    """Client for Google Sheets read/write operations."""

    def __init__(
        self,
        credentials_json: Optional[str] = None,
        sheet_id: Optional[str] = None,
    ):
        """
        Initialize the Google Sheets client.

        Args:
            credentials_json: Base64-encoded service account JSON.
                              Falls back to GOOGLE_SHEETS_CREDENTIALS_JSON env var.
            sheet_id: The Google Sheet ID. Falls back to GOOGLE_SHEET_ID env var.
        """
        creds_b64 = credentials_json or os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
        self.sheet_id = sheet_id or os.environ.get("GOOGLE_SHEET_ID", "")

        if not creds_b64:
            raise SheetsAPIError(
                "Google Sheets credentials not provided. "
                "Set GOOGLE_SHEETS_CREDENTIALS_JSON env var (base64-encoded service account JSON)."
            )
        if not self.sheet_id:
            raise SheetsAPIError(
                "Google Sheet ID not provided. Set GOOGLE_SHEET_ID env var."
            )

        # Decode credentials and build the Sheets API service
        try:
            creds_json = base64.b64decode(creds_b64).decode("utf-8")
            creds_dict = json.loads(creds_json)
        except Exception as e:
            raise SheetsAPIError(f"Failed to decode service account credentials: {e}") from e

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            self.service = build("sheets", "v4", credentials=credentials)
            self.sheets = self.service.spreadsheets()
            logger.info("Google Sheets API initialized for sheet: %s", self.sheet_id)

        except ImportError as e:
            raise SheetsAPIError(
                "Google API libraries not installed. "
                "Install: google-api-python-client google-auth"
            ) from e
        except Exception as e:
            raise SheetsAPIError(f"Failed to initialize Google Sheets API: {e}") from e

        self._validated_tabs: set[str] = set()

    # === Header Validation ===

    def _validate_headers(self, tab_name: str, expected_headers: list[str]) -> None:
        """Validate that row 1 of a tab matches expected column headers.

        Logs a warning if headers don't match. Does NOT raise an exception.
        Results are cached so validation runs at most once per tab per session.

        # TODO: Once confirmed working in production, this can be upgraded to
        # raise ValueError on mismatch to prevent silent data corruption.

        Args:
            tab_name: Sheet tab name.
            expected_headers: List of expected column header strings.
        """
        if tab_name in self._validated_tabs:
            return
        self._validated_tabs.add(tab_name)

        try:
            result = self.sheets.values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{tab_name}'!1:1",
            ).execute()
            actual = result.get("values", [[]])[0] if result.get("values") else []
        except Exception as e:
            logger.warning("Header validation failed for '%s' (could not read row 1): %s", tab_name, e)
            return

        if list(actual) != list(expected_headers):
            logger.warning(
                "Header mismatch in '%s'! Expected %s, got %s. "
                "Column indices may be wrong — check for data corruption.",
                tab_name, expected_headers, actual,
            )
        else:
            logger.debug("Header validation passed for '%s'.", tab_name)

    # === Cell Read/Write ===

    def write_cell(self, tab_name: str, cell: str, value: str) -> None:
        """Write a single value to a specific cell.

        Args:
            tab_name: Sheet tab name.
            cell: Cell reference (e.g., "B3", "N1").
            value: Value to write.
        """
        try:
            self.sheets.values().update(
                spreadsheetId=self.sheet_id,
                range=f"'{tab_name}'!{cell}",
                valueInputOption="RAW",
                body={"values": [[value]]},
            ).execute()
            logger.debug("Wrote '%s' to '%s'!%s.", value, tab_name, cell)
        except Exception as e:
            raise SheetsAPIError(f"Failed to write to '{tab_name}'!{cell}: {e}") from e

    # === Weekly Review Operations ===

    def write_weekly_review(
        self,
        analysis_summary: str,
        content_plan: dict,
        performance_data: dict,
    ) -> None:
        """
        Write weekly analysis and content plan to the "Weekly Review" tab.

        Clears the existing content and writes fresh data.
        Sets plan_status to "pending_review".

        Args:
            analysis_summary: Formatted weekly analysis text.
            content_plan: Structured weekly plan (blog posts + pins).
            performance_data: Key metrics for the dashboard.
        """
        logger.info("Writing weekly review to Google Sheet...")

        # Build the review data rows
        # Fixed rows: 1=Title, 2=blank, 3=STATUS, 4=PRODUCTION (written separately),
        #             5=PLAN REGEN trigger
        rows = [
            ["Pinterest Weekly Review", "", "", datetime.now(timezone.utc).strftime("%Y-%m-%d")],
            [""],
            ["STATUS", "pending_review"],
            [""],  # Row 4: placeholder — PRODUCTION/deploy status written by write_deploy_status()
            ["PLAN REGEN", "idle"],  # Row 5: B5 is the plan regen trigger cell
            [""],
            ["=== PERFORMANCE SUMMARY ==="],
        ]

        # Add performance metrics
        for key, value in performance_data.items():
            rows.append([str(key), str(value)])

        rows.append([""])
        rows.append(["=== ANALYSIS ==="])
        # Split analysis into lines for readability in the Sheet
        for line in analysis_summary.split("\n"):
            rows.append([line])

        rows.append([""])
        rows.append(["=== CONTENT PLAN ==="])

        # Blog posts section
        blog_posts = content_plan.get("blog_posts", [])
        if blog_posts:
            rows.append(["Blog Posts Planned:", str(len(blog_posts))])
            rows.append(["ID", "Type", "Topic", "Pillar", "Keywords", "Status", "Feedback"])
            for post in blog_posts:
                rows.append([
                    str(post.get("post_id", "")),
                    str(post.get("content_type", "")),
                    str(post.get("topic", "")),
                    str(post.get("pillar", "")),
                    ", ".join([post.get("primary_keyword", "")] + post.get("secondary_keywords", [])),
                    "",  # Status — blank = approved by default; user sets "regen" to request replacement
                    "",  # Feedback — free text for reviewer notes on what to change
                ])

        # Pins section
        pins = content_plan.get("pins", [])
        if pins:
            rows.append([""])
            rows.append(["Pins Planned:", str(len(pins))])
            rows.append(["ID", "Topic", "Board", "Schedule", "Type"])
            for pin in pins:
                rows.append([
                    str(pin.get("pin_id", "")),
                    str(pin.get("pin_topic", "")),
                    str(pin.get("target_board", "")),
                    f"{pin.get('scheduled_date', '')} / {pin.get('scheduled_slot', '')}",
                    str(pin.get("pin_type", "")),
                ])

        self._clear_and_write(TAB_WEEKLY_REVIEW, rows)
        logger.info("Weekly review written. %d blog posts, %d pins planned.", len(blog_posts), len(pins))

    def read_plan_approval_status(self) -> str:
        """
        Read the plan_status from the "Weekly Review" tab.

        Looks for the STATUS row (row 3, column B based on write_weekly_review layout).

        Returns:
            str: "pending_review", "approved", or "rejected".
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{TAB_WEEKLY_REVIEW}'!{WR_CELL_PLAN_STATUS}",
            ).execute()

            values = result.get("values", [[]])
            status = values[0][0] if values and values[0] else "pending_review"
            logger.info("Plan approval status: %s", status)
            return status

        except Exception as e:
            logger.error("Failed to read plan approval status: %s", e)
            raise SheetsAPIError(f"Failed to read plan status: {e}") from e

    def write_deploy_status(self, status: str = "pending_review", preview_url: str = "") -> None:
        """
        Write production deploy status to Weekly Review tab row 4.

        Layout: A4="PRODUCTION", B4=status, C4=preview_url.
        The Apps Script watches B4 for "approved" to trigger promotion.

        Args:
            status: "pending_review" or "approved".
            preview_url: Vercel preview URL for reviewing blogs.
        """
        try:
            self.sheets.values().update(
                spreadsheetId=self.sheet_id,
                range=f"'{TAB_WEEKLY_REVIEW}'!A4:C4",
                valueInputOption="RAW",
                body={"values": [["PRODUCTION", status, preview_url]]},
            ).execute()
            logger.info("Deploy status written: %s", status)
        except Exception as e:
            raise SheetsAPIError(f"Failed to write deploy status: {e}") from e

    def read_deploy_status(self) -> str:
        """
        Read production deploy status from Weekly Review tab cell B4.

        Returns:
            str: "pending_review" or "approved".
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{TAB_WEEKLY_REVIEW}'!{WR_CELL_DEPLOY_STATUS}",
            ).execute()

            values = result.get("values", [[]])
            status = values[0][0] if values and values[0] else "pending_review"
            logger.info("Deploy status: %s", status)
            return status
        except Exception as e:
            logger.error("Failed to read deploy status: %s", e)
            raise SheetsAPIError(f"Failed to read deploy status: {e}") from e

    # === Content Queue Operations ===

    def write_content_queue(
        self,
        blog_posts: list[dict],
        pins: list[dict],
        pin_image_urls: dict = None,
        blog_image_urls: dict = None,
        blog_previews: dict = None,
        quality_gate_stats: dict = None,
    ) -> None:
        """
        Write generated blog posts and pins to the "Content Queue" tab.

        Each row includes metadata and content_status = "pending_review".
        When pin_image_urls is provided, writes =IMAGE() formulas for inline
        pin image previews. Uses USER_ENTERED so formulas render.

        Args:
            blog_posts: List of generated blog post metadata dicts.
                Keys: post_id, title, content_type, pillar, slug
            pins: List of generated pin metadata dicts.
                Keys: pin_id, title, description, board_name, link, scheduled_date,
                      scheduled_slot, pillar, image_path, alt_text
                Optional quality keys: _quality_note, image_retries
            pin_image_urls: Optional dict of pin_id -> public image URL.
                When provided, writes =IMAGE(url) in thumbnail column.
            blog_image_urls: Optional dict of post_id -> public hero image URL.
                When provided, writes =IMAGE(url) for blog post thumbnails.
            blog_previews: Optional dict of post_id -> blog description text.
                When provided, writes preview in description column for blogs.
            quality_gate_stats: Optional dict with summary strings.
                When provided, writes a summary row at the bottom.
        """
        pin_image_urls = pin_image_urls or {}
        blog_image_urls = blog_image_urls or {}
        blog_previews = blog_previews or {}

        logger.info("Writing content queue: %d blog posts, %d pins...", len(blog_posts), len(pins))

        # Header row (A-L, 12 columns)
        rows = [
            ["ID", "Type", "Title", "Description", "Board", "Blog URL",
             "Schedule", "Pillar", "Thumbnail", "Status", "Notes", "Feedback"],
        ]

        # Blog posts
        for post in blog_posts:
            post_id = str(post.get("post_id", ""))
            description = blog_previews.get(post_id, str(post.get("content_type", "")))

            # Use IMAGE() formula if we have a hero image URL from Drive
            blog_img_url = blog_image_urls.get(post_id)
            blog_thumbnail = f'=IMAGE("{blog_img_url}")' if blog_img_url else ""

            rows.append([
                post_id,
                "blog",
                str(post.get("title", "")),
                description,
                "",  # No board for blog posts
                str(post.get("slug", "")),  # Slug stored in Blog URL column; deployer needs it
                "",  # No schedule for blog posts
                str(post.get("pillar", "")),
                blog_thumbnail,
                "pending_review",
                "",  # Notes
                "",  # Feedback
            ])

        # Pins
        for pin in pins:
            pin_id = str(pin.get("pin_id", ""))

            # Build description with alt text
            desc = str(pin.get("description", ""))
            alt_text = pin.get("alt_text", "")
            if alt_text:
                desc = f"{desc}\n\nAlt: {alt_text}"

            # Use IMAGE() formula if we have a public URL from Drive
            image_url = pin_image_urls.get(pin_id)
            if image_url:
                thumbnail = f'=IMAGE("{image_url}")'
            else:
                # Don't write local runner paths — they're meaningless after
                # the GitHub Actions runner is destroyed
                thumbnail = ""

            # Per-pin quality note (populated by publish_content_queue.py)
            quality_note = str(pin.get("_quality_note", ""))

            rows.append([
                pin_id,
                "pin",
                str(pin.get("title", "")),
                desc,
                str(pin.get("board_name", pin.get("target_board", ""))),
                str(pin.get("link", "")),
                f"{pin.get('scheduled_date', '')}/{pin.get('scheduled_slot', '')}",
                str(pin.get("pillar", "")),
                thumbnail,
                "pending_review",
                quality_note,
                "",  # Feedback
            ])

        # Quality gate summary row at the bottom
        if quality_gate_stats:
            rows.append([])  # blank separator row
            rows.append([
                "QUALITY GATE STATS",
                "",
                quality_gate_stats.get("ai_summary", ""),
                "", "", "", "", "", "", "", "", "",
            ])

        # Use USER_ENTERED so =IMAGE() formulas are interpreted
        self._clear_and_write(TAB_CONTENT_QUEUE, rows, value_input_option="USER_ENTERED")
        logger.info("Content queue written: %d total items.", len(rows) - 1)

    def read_content_approvals(self) -> list[dict]:
        """
        Read approval statuses from the "Content Queue" tab.

        Returns:
            list[dict]: Each item with id, type (blog/pin), status, and notes.
        """
        self._validate_headers(TAB_CONTENT_QUEUE, EXPECTED_CQ_HEADERS)
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{TAB_CONTENT_QUEUE}'!A:L",
            ).execute()

            values = result.get("values", [])
            if len(values) < 2:
                return []

            items = []
            for row in values[1:]:  # Skip header
                if not row:
                    continue
                items.append({
                    "id": row[CQ_COL_ID] if len(row) > CQ_COL_ID else "",
                    "type": row[CQ_COL_TYPE] if len(row) > CQ_COL_TYPE else "",
                    "title": row[CQ_COL_TITLE] if len(row) > CQ_COL_TITLE else "",
                    "slug": row[CQ_COL_BLOG_URL] if len(row) > CQ_COL_BLOG_URL else "",
                    "board": row[CQ_COL_BOARD] if len(row) > CQ_COL_BOARD else "",
                    "schedule": row[CQ_COL_SCHEDULE] if len(row) > CQ_COL_SCHEDULE else "",
                    "pillar": row[CQ_COL_PILLAR] if len(row) > CQ_COL_PILLAR else "",
                    "status": row[CQ_COL_STATUS] if len(row) > CQ_COL_STATUS else "pending_review",
                    "notes": row[CQ_COL_NOTES] if len(row) > CQ_COL_NOTES else "",
                    "feedback": row[CQ_COL_FEEDBACK] if len(row) > CQ_COL_FEEDBACK else "",
                })

            approved = sum(1 for i in items if i["status"] in ("approved", "use_ai_image"))
            rejected = sum(1 for i in items if i["status"] == "rejected")
            pending = sum(1 for i in items if i["status"] == "pending_review")
            logger.info(
                "Content approvals: %d approved, %d rejected, %d pending.",
                approved, rejected, pending,
            )
            return items

        except Exception as e:
            logger.error("Failed to read content approvals: %s", e)
            raise SheetsAPIError(f"Failed to read content approvals: {e}") from e

    def read_regen_requests(self) -> list[dict]:
        """
        Read Content Queue rows flagged for regeneration.

        Returns items where column J (status) starts with 'regen'.
        Each item includes the 1-based row index for in-place updates.

        Returns:
            list[dict]: Regen request items with row_index, id, type, title,
                        description, board, slug, schedule, pillar, status,
                        feedback, and notes.
        """
        self._validate_headers(TAB_CONTENT_QUEUE, EXPECTED_CQ_HEADERS)
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{TAB_CONTENT_QUEUE}'!A:L",
            ).execute()

            values = result.get("values", [])
            if len(values) < 2:
                return []

            items = []
            for i, row in enumerate(values[1:], start=2):  # row 2 = first data row
                if not row or len(row) <= CQ_COL_STATUS:
                    continue
                status = row[CQ_COL_STATUS].strip()
                if not status.startswith("regen"):
                    continue
                items.append({
                    "row_index": i,
                    "id": row[CQ_COL_ID] if len(row) > CQ_COL_ID else "",
                    "type": row[CQ_COL_TYPE] if len(row) > CQ_COL_TYPE else "",
                    "title": row[CQ_COL_TITLE] if len(row) > CQ_COL_TITLE else "",
                    "description": row[CQ_COL_DESCRIPTION] if len(row) > CQ_COL_DESCRIPTION else "",
                    "board": row[CQ_COL_BOARD] if len(row) > CQ_COL_BOARD else "",
                    "slug": row[CQ_COL_BLOG_URL] if len(row) > CQ_COL_BLOG_URL else "",
                    "schedule": row[CQ_COL_SCHEDULE] if len(row) > CQ_COL_SCHEDULE else "",
                    "pillar": row[CQ_COL_PILLAR] if len(row) > CQ_COL_PILLAR else "",
                    "status": status,
                    "notes": row[CQ_COL_NOTES] if len(row) > CQ_COL_NOTES else "",
                    "feedback": row[CQ_COL_FEEDBACK] if len(row) > CQ_COL_FEEDBACK else "",
                })

            logger.info("Found %d regen requests in Content Queue.", len(items))
            return items

        except Exception as e:
            logger.error("Failed to read regen requests: %s", e)
            raise SheetsAPIError(f"Failed to read regen requests: {e}") from e

    def update_content_row(
        self,
        row_index: int,
        thumbnail: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> None:
        """
        Update specific cells in a Content Queue row by row index.

        Only writes cells for which a value is provided. Uses USER_ENTERED
        so =IMAGE() formulas render.

        Args:
            row_index: 1-based row index in the Content Queue tab.
            thumbnail: New value for column I (e.g., '=IMAGE("url")').
            title: New value for column C.
            description: New value for column D.
            status: New value for column J.
            notes: New value for column K.
            feedback: New value for column L (typically cleared after regen).
        """
        updates: list[dict] = []
        col_map = {
            CQ_COL_TITLE: title,
            CQ_COL_DESCRIPTION: description,
            CQ_COL_THUMBNAIL: thumbnail,
            CQ_COL_STATUS: status,
            CQ_COL_NOTES: notes,
            CQ_COL_FEEDBACK: feedback,
        }

        for col_index, value in col_map.items():
            if value is None:
                continue
            col_letter = chr(65 + col_index)
            cell_range = f"'{TAB_CONTENT_QUEUE}'!{col_letter}{row_index}"
            updates.append({
                "range": cell_range,
                "values": [[value]],
            })

        if not updates:
            return

        try:
            self.sheets.values().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={
                    "valueInputOption": "USER_ENTERED",
                    "data": updates,
                },
            ).execute()
            logger.info("Updated Content Queue row %d (%d cells).", row_index, len(updates))
        except Exception as e:
            raise SheetsAPIError(f"Failed to update content row {row_index}: {e}") from e

    def reset_regen_trigger(self) -> None:
        """Write 'idle' to Content Queue regen trigger cell to reset it."""
        try:
            self.write_cell(TAB_CONTENT_QUEUE, CQ_CELL_REGEN_TRIGGER, "idle")
            logger.info("Reset regen trigger to 'idle'.")
        except Exception as e:
            raise SheetsAPIError(f"Failed to reset regen trigger: {e}") from e

    def read_plan_regen_requests(self) -> list[dict]:
        """
        Read blog post rows from the Weekly Review tab where Status="regen".

        The Weekly Review tab layout (after write_weekly_review) has blog post
        rows with columns: A=ID, B=Type, C=Topic, D=Pillar, E=Keywords,
        F=Status, G=Feedback. Blog rows start after the "Blog Posts Planned:"
        label row and its header row.

        Returns:
            list[dict]: Blog posts flagged for regen, each with keys:
                        post_id, content_type, topic, pillar, keywords,
                        status, feedback, row_index (1-based sheet row).
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{TAB_WEEKLY_REVIEW}'!A:G",
            ).execute()

            values = result.get("values", [])
            if not values:
                return []

            items = []
            in_blog_section = False
            for i, row in enumerate(values, start=1):
                if not row:
                    continue

                # Detect the blog header row to know we're in the blog section
                cell_a = str(row[0]).strip() if row else ""
                if cell_a == "ID" and len(row) >= 6 and str(row[5]).strip() == "Status":
                    in_blog_section = True
                    continue

                # End of blog section: blank row, pins section header, or section marker
                if in_blog_section and (
                    not cell_a
                    or cell_a.startswith("Pins Planned:")
                    or cell_a.startswith("===")
                ):
                    in_blog_section = False
                    continue

                if not in_blog_section:
                    continue

                # Read the status column (F = index 5)
                status = str(row[5]).strip().lower() if len(row) > 5 else ""
                if status != "regen":
                    continue

                items.append({
                    "row_index": i,
                    "post_id": cell_a,
                    "content_type": str(row[1]).strip() if len(row) > 1 else "",
                    "topic": str(row[2]).strip() if len(row) > 2 else "",
                    "pillar": str(row[3]).strip() if len(row) > 3 else "",
                    "keywords": str(row[4]).strip() if len(row) > 4 else "",
                    "status": status,
                    "feedback": str(row[6]).strip() if len(row) > 6 else "",
                })

            logger.info("Found %d plan regen requests in Weekly Review.", len(items))
            return items

        except Exception as e:
            logger.error("Failed to read plan regen requests: %s", e)
            raise SheetsAPIError(f"Failed to read plan regen requests: {e}") from e

    def reset_plan_regen_trigger(self) -> None:
        """Write 'idle' to Weekly Review plan regen trigger cell to reset it."""
        try:
            self.write_cell(TAB_WEEKLY_REVIEW, WR_CELL_REGEN_TRIGGER, "idle")
            logger.info("Reset plan regen trigger to 'idle'.")
        except Exception as e:
            raise SheetsAPIError(f"Failed to reset plan regen trigger: {e}") from e

    # === Post Log Operations ===

    def append_post_log(self, pin_data: dict) -> None:
        """
        Append a posted pin record to the "Post Log" tab.

        Args:
            pin_data: Dict with keys: pin_id, date, slot, board, title,
                      url, pinterest_pin_id, status, error.
        """
        row = [
            str(pin_data.get("pin_id", "")),
            str(pin_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))),
            str(pin_data.get("slot", "")),
            str(pin_data.get("board", "")),
            str(pin_data.get("title", "")),
            str(pin_data.get("url", "")),
            str(pin_data.get("pinterest_pin_id", "")),
            str(pin_data.get("status", "")),
            str(pin_data.get("error", "")),
        ]

        try:
            self.sheets.values().append(
                spreadsheetId=self.sheet_id,
                range=f"'{TAB_POST_LOG}'!A:I",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()
            logger.info("Post log entry appended: pin_id=%s status=%s",
                        pin_data.get("pin_id"), pin_data.get("status"))
        except Exception as e:
            raise SheetsAPIError(f"Failed to append post log: {e}") from e

    def update_pin_status(
        self,
        pin_id: str,
        status: str,
        pinterest_pin_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update a pin's status in the "Post Log" tab.

        Finds the row by pin_id and updates the status column.

        Args:
            pin_id: Internal pin ID (e.g., "W12-01").
            status: "posted", "failed", or "retry".
            pinterest_pin_id: The Pinterest-assigned pin ID (on success).
            error_message: Error details (on failure).
        """
        # Append as a new log entry rather than updating in-place
        # This provides a complete audit trail
        self.append_post_log({
            "pin_id": pin_id,
            "status": status,
            "pinterest_pin_id": pinterest_pin_id or "",
            "error": error_message or "",
        })

    # === Dashboard Operations ===

    def update_dashboard(self, metrics: dict) -> None:
        """
        Update the "Dashboard" tab with latest metrics.

        Writes metrics as key-value pairs starting at A1.

        Args:
            metrics: Key-value pairs for dashboard cells.
                Example: {"Total Pins Posted": 112, "Weekly Impressions": 5432, ...}
        """
        logger.info("Updating dashboard with %d metrics...", len(metrics))

        rows = [
            ["Pinterest Pipeline Dashboard", "", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
            [""],
        ]

        for key, value in metrics.items():
            rows.append([str(key), str(value)])

        self._clear_and_write(TAB_DASHBOARD, rows)
        logger.info("Dashboard updated.")

    # === Internal Helpers ===

    def _clear_and_write(
        self,
        tab_name: str,
        rows: list[list],
        value_input_option: str = "RAW",
    ) -> None:
        """
        Clear a tab and write new data.

        Args:
            tab_name: Sheet tab name.
            rows: List of row data (each row is a list of cell values).
            value_input_option: "RAW" for literal values, "USER_ENTERED"
                to interpret formulas like =IMAGE().
        """
        range_str = f"'{tab_name}'"

        try:
            # Clear existing content
            self.sheets.values().clear(
                spreadsheetId=self.sheet_id,
                range=range_str,
                body={},
            ).execute()

            # Write new content
            if rows:
                self.sheets.values().update(
                    spreadsheetId=self.sheet_id,
                    range=f"'{tab_name}'!A1",
                    valueInputOption=value_input_option,
                    body={"values": rows},
                ).execute()

            logger.debug("Wrote %d rows to '%s'.", len(rows), tab_name)

        except Exception as e:
            raise SheetsAPIError(f"Failed to write to '{tab_name}': {e}") from e

    def _get_sheet_id(self, tab_name: str) -> int:
        """
        Get the numeric sheet ID for a tab by name.

        Args:
            tab_name: Sheet tab name (e.g., "Content Queue").

        Returns:
            int: The sheet ID used in batchUpdate requests.

        Raises:
            SheetsAPIError: If tab not found.
        """
        try:
            spreadsheet = self.sheets.get(
                spreadsheetId=self.sheet_id,
            ).execute()

            for sheet in spreadsheet.get("sheets", []):
                props = sheet.get("properties", {})
                if props.get("title") == tab_name:
                    return props["sheetId"]

            raise SheetsAPIError(f"Tab '{tab_name}' not found in spreadsheet")
        except SheetsAPIError:
            raise
        except Exception as e:
            raise SheetsAPIError(f"Failed to get sheet ID for '{tab_name}': {e}") from e

    def set_row_heights(
        self,
        tab_name: str,
        start_row: int,
        num_rows: int,
        height_px: int,
    ) -> None:
        """
        Set row heights for a range of rows.

        Args:
            tab_name: Sheet tab name.
            start_row: First row (1-based, data rows start at 2).
            num_rows: Number of rows to resize.
            height_px: Height in pixels.
        """
        sheet_id = self._get_sheet_id(tab_name)

        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={
                    "requests": [
                        {
                            "updateDimensionProperties": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": start_row - 1,  # 0-based
                                    "endIndex": start_row - 1 + num_rows,
                                },
                                "properties": {
                                    "pixelSize": height_px,
                                },
                                "fields": "pixelSize",
                            }
                        }
                    ]
                },
            ).execute()
            logger.info(
                "Set row heights %d-%d to %dpx in '%s'.",
                start_row, start_row + num_rows - 1, height_px, tab_name,
            )
        except Exception as e:
            logger.error("Failed to set row heights: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Google Sheets API smoke test")
    print("============================")

    try:
        sheets = SheetsAPI()
        status = sheets.read_plan_approval_status()
        print(f"Plan approval status: {status}")

        approvals = sheets.read_content_approvals()
        print(f"Content queue items: {len(approvals)}")
        for item in approvals[:3]:
            print(f"  [{item['type']}] {item['id']}: {item['status']}")

    except SheetsAPIError as e:
        print(f"Sheets API error: {e}")
    except Exception as e:
        print(f"Error: {e}")
