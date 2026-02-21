"""
Slack Webhook Notification Wrapper

Sends notifications to a Slack channel at key pipeline events:

| Event                    | Message                                          | Action Needed? |
|--------------------------|--------------------------------------------------|----------------|
| Monday 6am ET            | "Weekly review ready. [Sheet link]"              | Yes            |
| After plan approval      | "Content generation started..."                  | No             |
| After content generated  | "28 pins + 9 blog posts ready for review."       | Yes            |
| After content approval   | "Week is live. 28 pins scheduled."               | No             |
| Daily (3x)               | "Posted 2/2 pins for [slot]"                     | No             |
| On failure               | "FAILED: [details]"                              | Yes            |
| 1st Monday               | "Monthly review ready. [Sheet link]"             | Yes            |
| Monday 6pm reminder      | "Reminder: content still pending review."         | Yes            |

Uses Slack Block Kit for structured messages with color-coded severity.

Environment variables required:
- SLACK_WEBHOOK_URL
- GOOGLE_SHEET_URL (for linking to the Sheet in messages)
"""

import os
import json
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Color constants for Slack attachment sidebar
COLOR_INFO = "#36a64f"      # green
COLOR_WARNING = "#ff9900"   # orange/yellow
COLOR_ERROR = "#ff0000"     # red
COLOR_NEUTRAL = "#439FE0"   # blue


class SlackNotifyError(Exception):
    """Raised when Slack notification fails."""
    pass


class SlackNotify:
    """Simple Slack webhook notification sender."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        sheet_url: Optional[str] = None,
    ):
        """
        Initialize the Slack notifier.

        Args:
            webhook_url: Slack incoming webhook URL. Falls back to SLACK_WEBHOOK_URL.
            sheet_url: Google Sheet URL for linking. Falls back to GOOGLE_SHEET_URL.
        """
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        self.sheet_url = sheet_url or os.environ.get("GOOGLE_SHEET_URL", "")

        if not self.webhook_url:
            logger.warning(
                "SLACK_WEBHOOK_URL not set. Slack notifications will be logged but not sent."
            )

    def notify_review_ready(self, analysis_summary: str) -> None:
        """
        Send "Weekly review ready" notification with Sheet link.

        Args:
            analysis_summary: Brief summary of the weekly analysis.
        """
        sheet_link = f"<{self.sheet_url}|Open Google Sheet>" if self.sheet_url else "(Sheet URL not configured)"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Weekly Review Ready"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Your weekly analytics report and content plan are ready for review.\n\n"
                        f"*Summary:*\n{analysis_summary}\n\n"
                        f":point_right: {sheet_link}"
                    ),
                },
            },
        ]

        self._send_message(
            text="Weekly review ready -- open the Google Sheet to review and approve.",
            blocks=blocks,
            color=COLOR_NEUTRAL,
        )

    def notify_content_generation_started(self) -> None:
        """Send "Content generation started" notification."""
        self._send_message(
            text="Content generation started. Generating pins and blog posts... This takes ~10-15 minutes.",
            color=COLOR_INFO,
        )

    def notify_content_ready(
        self,
        num_pins: int,
        num_blog_posts: int,
    ) -> None:
        """
        Send "Content ready for review" notification.

        Args:
            num_pins: Number of pins generated.
            num_blog_posts: Number of blog posts generated.
        """
        sheet_link = f"<{self.sheet_url}|Open Google Sheet>" if self.sheet_url else "(Sheet URL not configured)"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Content Ready for Review"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{num_pins} pins* and *{num_blog_posts} blog posts* are ready for your review.\n\n"
                        f":point_right: {sheet_link}"
                    ),
                },
            },
        ]

        self._send_message(
            text=f"{num_pins} pins + {num_blog_posts} blog posts ready for review.",
            blocks=blocks,
            color=COLOR_NEUTRAL,
        )

    def notify_week_live(
        self,
        num_pins_scheduled: int,
        num_blog_posts_deployed: int,
    ) -> None:
        """
        Send "Week is live" notification.

        Args:
            num_pins_scheduled: Number of pins in the posting schedule.
            num_blog_posts_deployed: Number of blog posts deployed to Vercel.
        """
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Week Is Live"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{num_pins_scheduled} pins* scheduled for Tue-Mon posting windows.\n"
                        f"*{num_blog_posts_deployed} blog posts* deployed to goslated.com.\n\n"
                        f"Daily posting starts tomorrow."
                    ),
                },
            },
        ]

        self._send_message(
            text=f"Week is live. {num_pins_scheduled} pins scheduled, {num_blog_posts_deployed} blog posts deployed.",
            blocks=blocks,
            color=COLOR_INFO,
        )

    def notify_posting_complete(
        self,
        slot: str,
        posted: int,
        total: int,
    ) -> None:
        """
        Send daily posting completion notification.

        Args:
            slot: Time slot name ("morning", "afternoon", or "evening").
            posted: Number of pins successfully posted.
            total: Total pins attempted.
        """
        if posted == total:
            color = COLOR_INFO
            status_text = f"Posted {posted}/{total} pins for {slot} slot."
        elif posted > 0:
            color = COLOR_WARNING
            status_text = f"Posted {posted}/{total} pins for {slot} slot. {total - posted} failed."
        else:
            color = COLOR_ERROR
            status_text = f"All {total} pins failed for {slot} slot."

        self._send_message(text=status_text, color=color)

    def notify_failure(self, workflow: str, error: str) -> None:
        """
        Send failure alert with error details.

        Args:
            workflow: Name of the failed workflow/step.
            error: Error message or traceback.
        """
        # Truncate very long error messages for Slack readability
        error_truncated = error[:1500] + "..." if len(error) > 1500 else error

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Pipeline Failure"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Workflow:* `{workflow}`\n\n"
                        f"*Error:*\n```{error_truncated}```"
                    ),
                },
            },
        ]

        self._send_message(
            text=f"FAILED: {workflow} -- {error_truncated}",
            blocks=blocks,
            color=COLOR_ERROR,
        )

    def notify_monthly_review_ready(self, summary: str) -> None:
        """
        Send "Monthly review ready" notification.

        Args:
            summary: Brief summary of the monthly review.
        """
        sheet_link = f"<{self.sheet_url}|Open Google Sheet>" if self.sheet_url else "(Sheet URL not configured)"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Monthly Strategy Review Ready"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Your 30-day deep analysis and strategy recommendations are ready.\n\n"
                        f"*Summary:*\n{summary}\n\n"
                        f":point_right: {sheet_link}"
                    ),
                },
            },
        ]

        self._send_message(
            text=f"Monthly strategy review ready -- {summary}",
            blocks=blocks,
            color=COLOR_NEUTRAL,
        )

    def notify_approval_reminder(self) -> None:
        """Send Monday 6pm reminder if content still pending review."""
        sheet_link = f"<{self.sheet_url}|Open Google Sheet>" if self.sheet_url else "(Sheet URL not configured)"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Reminder: Content Pending Review"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Weekly content is still pending review. "
                        f"Tuesday's posting slots will be missed if not approved tonight.\n\n"
                        f":point_right: {sheet_link}"
                    ),
                },
            },
        ]

        self._send_message(
            text="Reminder: weekly content still pending review. Tuesday posts will be missed if not approved tonight.",
            blocks=blocks,
            color=COLOR_WARNING,
        )

    def notify_regen_complete(self, regen_results: list[dict]) -> None:
        """
        Send notification after content regeneration completes.

        Args:
            regen_results: List of dicts with keys: pin_id, type, regen_type,
                           old_score, new_score, and optional error.
        """
        sheet_link = (
            f"<{self.sheet_url}|Open Google Sheet>"
            if self.sheet_url
            else "(Sheet URL not configured)"
        )

        succeeded = [r for r in regen_results if not r.get("error")]
        failed = [r for r in regen_results if r.get("error")]

        item_lines = []
        for r in succeeded:
            pin_id = r.get("pin_id", "?")
            item_type = r.get("type", "pin")
            regen_type = r.get("regen_type", "regen")

            label_map = {
                "regen_image": "new image",
                "regen_copy": "new copy",
                "regen": "full regen",
            }
            label = label_map.get(regen_type, regen_type)

            old_score = r.get("old_score")
            new_score = r.get("new_score")
            if old_score is not None and new_score is not None:
                score_text = f" (score: {new_score}, was {old_score})"
            elif new_score is not None:
                score_text = f" (score: {new_score})"
            else:
                score_text = ""

            item_lines.append(f"\u2022 {pin_id} ({item_type}) \u2014 {label}{score_text}")
            warning = r.get("warning")
            if warning:
                item_lines.append(f"  :warning: {warning}")

        for r in failed:
            pin_id = r.get("pin_id", "?")
            item_type = r.get("type", "pin")
            error = r.get("error", "unknown error")
            item_lines.append(f"\u2022 {pin_id} ({item_type}) \u2014 FAILED: {error}")

        items_text = "\n".join(item_lines) if item_lines else "No items processed."

        # Build summary line
        parts = []
        if succeeded:
            parts.append(f"*{len(succeeded)}* regenerated")
        if failed:
            parts.append(f"*{len(failed)}* failed")
        summary = ", ".join(parts) + " \u2014 ready for re-review"

        color = COLOR_NEUTRAL if not failed else COLOR_WARNING

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Regen Complete"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{summary}:\n\n"
                        f"{items_text}\n\n"
                        f":point_right: {sheet_link}"
                    ),
                },
            },
        ]

        self._send_message(
            text=f"{len(succeeded)} regenerated, {len(failed)} failed -- ready for re-review.",
            blocks=blocks,
            color=color,
        )

    def notify(self, message: str, level: str = "info") -> None:
        """
        Send a generic notification message.

        Args:
            message: The message text.
            level: Severity level -- "info", "warning", or "error".
        """
        color_map = {
            "info": COLOR_INFO,
            "warning": COLOR_WARNING,
            "error": COLOR_ERROR,
        }
        self._send_message(text=message, color=color_map.get(level, COLOR_INFO))

    def notify_reminder(self, pending_items: str) -> None:
        """
        Send a reminder about pending items.

        Args:
            pending_items: Description of what is still pending.
        """
        sheet_link = f"<{self.sheet_url}|Open Google Sheet>" if self.sheet_url else "(Sheet URL not configured)"

        self._send_message(
            text=f"Reminder: {pending_items}\n{sheet_link}",
            color=COLOR_WARNING,
        )

    def _send_message(
        self,
        text: str,
        blocks: Optional[list] = None,
        color: str = COLOR_INFO,
    ) -> None:
        """
        Send a message via the Slack webhook.

        Args:
            text: Fallback text for notifications and non-block-supporting clients.
            blocks: Optional Slack Block Kit blocks for rich formatting.
            color: Sidebar color for the message attachment.

        Raises:
            SlackNotifyError: If the webhook call fails.
        """
        if not self.webhook_url:
            logger.info("[Slack (not sent -- no webhook URL)] %s", text)
            return

        payload: dict = {"text": text}

        if blocks:
            # Use attachments with blocks for color sidebar support
            payload["attachments"] = [
                {
                    "color": color,
                    "blocks": blocks,
                }
            ]

        logger.info("Sending Slack notification: %s", text[:100])

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code != 200:
                error_msg = (
                    f"Slack webhook returned HTTP {response.status_code}: {response.text}"
                )
                logger.error(error_msg)
                raise SlackNotifyError(error_msg)

            logger.debug("Slack notification sent successfully.")

        except requests.RequestException as e:
            error_msg = f"Failed to send Slack notification: {e}"
            logger.error(error_msg)
            raise SlackNotifyError(error_msg) from e


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    notifier = SlackNotify()
    print("Sending test notification...")
    notifier.notify_review_ready("Test notification from pinterest-pipeline smoke test.")
    print("Done.")
