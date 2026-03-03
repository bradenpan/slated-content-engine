"""Tests for BlogDeployer filtering pins with failed URL verification.

Validates fix #18: blog_deployer.py excludes pins linked to blogs whose
URLs failed verification from the pin schedule. This prevents posting
pins that link to non-existent blog posts.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.shared.blog_deployer import BlogDeployer


@pytest.fixture
def deployer():
    """Create a BlogDeployer with all dependencies mocked."""
    github = MagicMock()
    sheets = MagicMock()
    slack = MagicMock()
    return BlogDeployer(github=github, sheets=sheets, slack=slack)


def _make_approval(item_id, item_type, slug="", status="approved"):
    """Build a content approval dict as returned by read_content_approvals."""
    return {
        "id": item_id,
        "type": item_type,
        "title": f"Title for {item_id}",
        "slug": slug,
        "board": "Board A",
        "schedule": "2026-03-03/morning",
        "pillar": "1",
        "status": status,
        "notes": "",
        "feedback": "",
    }


class TestPinFilterOnFailedVerification:
    """Pins for blogs with failed URL verification are excluded from schedule."""

    def test_failed_urls_excluded_from_schedule(self, deployer):
        # Set up approvals: 2 blogs, 3 pins (2 for blog-a, 1 for blog-b)
        deployer.sheets.read_content_approvals.return_value = [
            _make_approval("B1", "blog", slug="blog-a"),
            _make_approval("B2", "blog", slug="blog-b"),
            _make_approval("P1", "pin", slug="blog-a"),
            _make_approval("P2", "pin", slug="blog-a"),
            _make_approval("P3", "pin", slug="blog-b"),
        ]

        # Merge succeeds
        deployer.github.merge_develop_to_main.return_value = "abc123def456"

        # blog-a fails verification, blog-b succeeds
        deployer.github.verify_deployment.side_effect = lambda slug, **kw: slug == "blog-b"

        # Mock _create_pin_schedule to capture what pins get passed
        scheduled_pins = []

        def capture_schedule(approved_pins, plan_path=None):
            scheduled_pins.extend(approved_pins)
            return len(approved_pins)

        with patch.object(deployer, "_create_pin_schedule", side_effect=capture_schedule):
            with patch.object(deployer, "_append_to_content_log", return_value=0):
                deployer.promote_to_production()

        # Only P3 (linked to blog-b) should be scheduled
        scheduled_ids = [p["id"] for p in scheduled_pins]
        assert "P3" in scheduled_ids
        assert "P1" not in scheduled_ids
        assert "P2" not in scheduled_ids

    def test_all_urls_pass_all_pins_included(self, deployer):
        deployer.sheets.read_content_approvals.return_value = [
            _make_approval("B1", "blog", slug="blog-a"),
            _make_approval("B2", "blog", slug="blog-b"),
            _make_approval("P1", "pin", slug="blog-a"),
            _make_approval("P2", "pin", slug="blog-b"),
        ]

        deployer.github.merge_develop_to_main.return_value = "abc123"
        deployer.github.verify_deployment.return_value = True

        scheduled_pins = []

        def capture_schedule(approved_pins, plan_path=None):
            scheduled_pins.extend(approved_pins)
            return len(approved_pins)

        with patch.object(deployer, "_create_pin_schedule", side_effect=capture_schedule):
            with patch.object(deployer, "_append_to_content_log", return_value=0):
                deployer.promote_to_production()

        scheduled_ids = [p["id"] for p in scheduled_pins]
        assert "P1" in scheduled_ids
        assert "P2" in scheduled_ids

    def test_warning_logged_for_filtered_pins(self, deployer, caplog):
        deployer.sheets.read_content_approvals.return_value = [
            _make_approval("B1", "blog", slug="blog-a"),
            _make_approval("P1", "pin", slug="blog-a"),
            _make_approval("P2", "pin", slug="blog-a"),
        ]

        deployer.github.merge_develop_to_main.return_value = "abc123"
        # blog-a fails verification
        deployer.github.verify_deployment.return_value = False

        with patch.object(deployer, "_create_pin_schedule", return_value=0):
            with patch.object(deployer, "_append_to_content_log", return_value=0):
                with caplog.at_level(logging.WARNING):
                    deployer.promote_to_production()

        # Check that a warning about excluded/filtered pins was logged
        assert any(
            "excluded" in r.message.lower() or "filtered" in r.message.lower()
            for r in caplog.records
        ), "Expected a warning about excluded pins due to failed URL verification"


class TestPinFilterUsesSlugField:
    """Pin filtering checks both 'blog_slug' and 'slug' fields."""

    def test_pin_with_blog_slug_field_filtered(self, deployer):
        # Pin uses "blog_slug" key instead of "slug"
        pin = _make_approval("P1", "pin")
        pin["blog_slug"] = "blog-a"
        pin.pop("slug", None)

        deployer.sheets.read_content_approvals.return_value = [
            _make_approval("B1", "blog", slug="blog-a"),
            pin,
        ]

        deployer.github.merge_develop_to_main.return_value = "abc123"
        deployer.github.verify_deployment.return_value = False

        scheduled_pins = []

        def capture_schedule(approved_pins, plan_path=None):
            scheduled_pins.extend(approved_pins)
            return len(approved_pins)

        with patch.object(deployer, "_create_pin_schedule", side_effect=capture_schedule):
            with patch.object(deployer, "_append_to_content_log", return_value=0):
                deployer.promote_to_production()

        # Pin should be filtered out because blog-a failed verification
        assert len(scheduled_pins) == 0
