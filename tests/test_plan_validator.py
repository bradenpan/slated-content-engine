"""Tests for src/plan_validator.py -- weekly plan validation logic."""

from datetime import date, timedelta

import pytest

from src.pinterest.plan_validator import (
    MAX_CONSECUTIVE_SAME_TEMPLATE,
    MAX_PINS_PER_BOARD,
    PILLAR_MIX_TARGETS,
    PINS_PER_DAY,
    POSTING_DAYS,
    TOTAL_WEEKLY_PINS,
    validate_plan,
    violation_messages,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pin(pin_id, pillar=1, board="Board A", template="template-1",
              scheduled_date="2026-03-03", scheduled_slot="morning",
              source_post_id="P1", primary_keyword="test keyword",
              pin_type="new", **extra):
    pin = {
        "pin_id": pin_id,
        "pillar": pillar,
        "target_board": board,
        "pin_template": template,
        "scheduled_date": scheduled_date,
        "scheduled_slot": scheduled_slot,
        "source_post_id": source_post_id,
        "primary_keyword": primary_keyword,
        "secondary_keywords": [],
        "pin_topic": "",
        "pin_type": pin_type,
    }
    pin.update(extra)
    return pin


def _make_post(post_id, topic="unique topic", primary_keyword="test keyword", **extra):
    post = {
        "post_id": post_id,
        "topic": topic,
        "primary_keyword": primary_keyword,
        "secondary_keywords": [],
    }
    post.update(extra)
    return post


def _build_valid_plan():
    """Build a minimal valid plan with 28 pins across 7 days, correct pillar mix."""
    # Pillar mix targets: P1: 9-10, P2: 7-8, P3: 5-6, P4: 2-3, P5: 4-5
    # Use: P1=10, P2=7, P3=5, P4=2, P5=4 = 28
    pillar_counts = {1: 10, 2: 7, 3: 5, 4: 2, 5: 4}

    # 7 posting days, 4 pins per day
    base_date = date(2026, 3, 3)  # Tuesday
    days = [(base_date + timedelta(days=i)).isoformat() for i in range(7)]
    slots = ["morning", "afternoon", "evening-1", "evening-2"]
    boards = ["Board A", "Board B", "Board C", "Board D", "Board E", "Board F"]
    templates = ["template-1", "template-2", "template-3", "template-4"]

    pins = []
    posts = []
    pin_idx = 0
    post_idx = 0

    for pillar, count in pillar_counts.items():
        for i in range(count):
            day_index = pin_idx // PINS_PER_DAY
            slot_index = pin_idx % PINS_PER_DAY
            post_id = f"P{post_idx + 1}"

            pins.append(_make_pin(
                pin_id=f"W1-{pin_idx:02d}",
                pillar=pillar,
                board=boards[pin_idx % len(boards)],
                template=templates[pin_idx % len(templates)],
                scheduled_date=days[day_index],
                scheduled_slot=slots[slot_index],
                source_post_id=post_id,
            ))
            posts.append(_make_post(
                post_id=post_id,
                topic=f"unique topic about subject {post_idx}",
            ))
            pin_idx += 1
            post_idx += 1

    return {"pins": pins, "blog_posts": posts}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPinCount:
    def test_exact_28_pins_no_violation(self):
        plan = _build_valid_plan()
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        pin_count_violations = [v for v in violations if v["category"] == "pin_count"]
        assert len(pin_count_violations) == 0

    def test_too_few_pins(self):
        plan = _build_valid_plan()
        plan["pins"] = plan["pins"][:20]
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        pin_count_violations = [v for v in violations if v["category"] == "pin_count"]
        assert len(pin_count_violations) == 1
        assert "20" in pin_count_violations[0]["message"]

    def test_too_many_pins(self):
        plan = _build_valid_plan()
        plan["pins"].append(_make_pin("extra"))
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        pin_count_violations = [v for v in violations if v["category"] == "pin_count"]
        assert len(pin_count_violations) == 1
        assert "29" in pin_count_violations[0]["message"]


class TestPillarMix:
    def test_valid_mix_no_violation(self):
        plan = _build_valid_plan()
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        pillar_violations = [v for v in violations if v["category"] == "pillar_mix"]
        assert len(pillar_violations) == 0

    def test_pillar_outside_tolerance(self):
        plan = _build_valid_plan()
        # Set all pins to pillar 1 -- way outside range for other pillars
        for pin in plan["pins"]:
            pin["pillar"] = 1
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        pillar_violations = [v for v in violations if v["category"] == "pillar_mix"]
        assert len(pillar_violations) > 0


class TestTopicRepetition:
    def test_no_repetition(self):
        plan = _build_valid_plan()
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        topic_violations = [v for v in violations if v["category"] == "topic_repetition"]
        assert len(topic_violations) == 0

    def test_high_word_overlap_flagged(self):
        recent_date = (date.today() - timedelta(days=7)).isoformat()
        content_log = [
            {"topic_summary": "best healthy meal prep ideas", "blog_slug": "old-post",
             "date": recent_date}
        ]
        plan = _build_valid_plan()
        # Add a post that overlaps > 60% with the recent topic
        plan["blog_posts"][0]["topic"] = "best healthy meal prep ideas for beginners"
        violations = validate_plan(plan, "", content_log=content_log, board_structure={}, negative_keywords=[])
        topic_violations = [v for v in violations if v["category"] == "topic_repetition"]
        assert len(topic_violations) >= 1


class TestBoardLimit:
    def test_within_limit_no_violation(self):
        plan = _build_valid_plan()
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        board_violations = [v for v in violations if v["category"] == "board_limit"]
        assert len(board_violations) == 0

    def test_exceeds_board_limit(self):
        plan = _build_valid_plan()
        # Put all pins on the same board
        for pin in plan["pins"]:
            pin["target_board"] = "Single Board"
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        board_violations = [v for v in violations if v["category"] == "board_limit"]
        assert len(board_violations) >= 1
        assert "Single Board" in board_violations[0]["message"]


class TestTreatmentLimit:
    def test_within_treatment_limit(self):
        plan = _build_valid_plan()
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        treatment_violations = [v for v in violations if v["category"] == "treatment_limit"]
        assert len(treatment_violations) == 0

    def test_exceeds_treatment_limit(self):
        plan = _build_valid_plan()
        # Set 3 pins as fresh-treatment for the same slug
        for i in range(3):
            plan["pins"][i]["pin_type"] = "fresh-treatment"
            plan["pins"][i]["blog_slug"] = "same-post-slug"
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        treatment_violations = [v for v in violations if v["category"] == "treatment_limit"]
        assert len(treatment_violations) >= 1


class TestConsecutiveTemplate:
    def test_no_consecutive_violation(self):
        plan = _build_valid_plan()
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        consec_violations = [v for v in violations if v["category"] == "consecutive_template"]
        assert len(consec_violations) == 0

    def test_four_consecutive_same_template_flagged(self):
        plan = _build_valid_plan()
        # Force first 4 pins (same day, consecutive slots) to use same template
        base_date = plan["pins"][0]["scheduled_date"]
        for i in range(4):
            plan["pins"][i]["pin_template"] = "template-X"
            plan["pins"][i]["scheduled_date"] = base_date
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        consec_violations = [v for v in violations if v["category"] == "consecutive_template"]
        assert len(consec_violations) >= 1


class TestDayDistribution:
    def test_valid_distribution(self):
        plan = _build_valid_plan()
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        day_violations = [v for v in violations if v["category"] == "day_distribution"]
        assert len(day_violations) == 0

    def test_uneven_distribution(self):
        plan = _build_valid_plan()
        # Move all pins to the same date
        for pin in plan["pins"]:
            pin["scheduled_date"] = "2026-03-03"
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        day_violations = [v for v in violations if v["category"] == "day_distribution"]
        assert len(day_violations) >= 1


class TestNegativeKeywords:
    def test_no_negative_keywords(self):
        plan = _build_valid_plan()
        violations = validate_plan(plan, "", content_log=[], board_structure={}, negative_keywords=[])
        neg_violations = [v for v in violations if "negative_keyword" in v["category"]]
        assert len(neg_violations) == 0

    def test_pin_targets_negative_keyword(self):
        plan = _build_valid_plan()
        plan["pins"][0]["primary_keyword"] = "cheap plastic containers"
        violations = validate_plan(
            plan, "", content_log=[], board_structure={},
            negative_keywords=["cheap"],
        )
        neg_violations = [v for v in violations if v["category"] == "negative_keyword_pin"]
        assert len(neg_violations) >= 1
        assert neg_violations[0]["post_id"] is None
        assert neg_violations[0]["pin_id"] == plan["pins"][0]["pin_id"]

    def test_post_targets_negative_keyword(self):
        plan = _build_valid_plan()
        plan["blog_posts"][0]["primary_keyword"] = "fast food recipes"
        violations = validate_plan(
            plan, "", content_log=[], board_structure={},
            negative_keywords=["fast food"],
        )
        neg_violations = [v for v in violations if v["category"] == "negative_keyword_post"]
        assert len(neg_violations) >= 1

    def test_pin_topic_contains_negative_keyword(self):
        plan = _build_valid_plan()
        plan["pins"][0]["pin_topic"] = "buy cheap meal prep containers"
        violations = validate_plan(
            plan, "", content_log=[], board_structure={},
            negative_keywords=["cheap"],
        )
        neg_violations = [v for v in violations if v["category"] == "negative_keyword_pin"]
        assert len(neg_violations) >= 1


class TestViolationMessages:
    def test_extracts_messages(self):
        violations = [
            {"category": "pin_count", "message": "Too few pins"},
            {"category": "pillar_mix", "message": "Pillar 1 out of range"},
        ]
        msgs = violation_messages(violations)
        assert msgs == ["Too few pins", "Pillar 1 out of range"]

    def test_empty_list(self):
        assert violation_messages([]) == []
