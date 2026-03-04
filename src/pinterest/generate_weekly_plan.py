"""
Weekly Content Plan Generator (Pinterest)

Generates the weekly content plan (8-10 blog posts + 28 derived pins)
using Claude Sonnet. This is the "brain" step that runs every Monday
at 6am ET as part of the weekly-review.yml workflow.

The plan is blog-first: blog posts are defined first, then pins are
derived from them.

Input context loaded for the planning prompt:
1. strategy/current-strategy.md -- Strategic direction
2. analysis/weekly/latest -- Most recent weekly analysis
3. data/content-memory-summary.md -- Content memory (prevents repetition)
4. strategy/seasonal-calendar.json -- Current seasonal window
5. strategy/keyword-lists.json + performance data -- Keyword targets
6. strategy/negative-keywords.json -- Topics to avoid
7. strategy/cta-variants.json -- CTA copy for blog post assignments
8. strategy/pinterest/board-structure.json -- Board distribution constraints

Output: Structured plan written to Google Sheet "Weekly Review" tab.

Planning constraints enforced (from strategy Section 12.2):
- Pillar mix percentages
- No topic repetition within 10 weeks
- Max 5 treatments per URL in 60 days
- Max 5 pins per board per week
- No more than 3 consecutive same-template pins
- 4 pins per day across 3 time slots
- Seasonal content injection during windows
- Performance-informed adjustments
"""

import json
import logging
from collections import Counter
from datetime import datetime, timedelta, date
from typing import Optional

from src.shared.apis.claude_api import ClaudeAPI
from src.shared.apis.sheets_api import SheetsAPI
from src.shared.apis.slack_notify import SlackNotify
from src.shared.paths import DATA_DIR, STRATEGY_DIR
from src.shared.content_planner import (
    load_strategy_context,
    load_latest_analysis,
    get_current_seasonal_window,
)
from src.shared.content_memory import generate_content_memory_summary
from src.pinterest.plan_validator import validate_plan, violation_messages, TOPIC_REPETITION_WINDOW_WEEKS
from src.shared.utils.content_log import load_content_log as _load_content_log
from src.shared.utils.plan_utils import (
    identify_replaceable_posts,
    splice_replacements,
    build_keyword_performance_data,
    extract_recent_topics,
)

logger = logging.getLogger(__name__)


def generate_plan(
    week_start_date: Optional[str] = None,
    claude: Optional[ClaudeAPI] = None,
    sheets: Optional[SheetsAPI] = None,
    slack: Optional[SlackNotify] = None,
) -> dict:
    """
    Generate the weekly content plan.

    Main orchestration function. This is the entry point called by
    the weekly-review.yml workflow.

    Args:
        week_start_date: ISO date string for the week start (Monday).
                        Defaults to the current or next Monday.

    Returns:
        dict: The generated weekly plan with blog_posts and pins arrays.
    """
    if week_start_date:
        start_date = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    else:
        today = date.today()
        # Find the current or next Monday
        days_until_monday = (7 - today.weekday()) % 7
        start_date = today + timedelta(days=days_until_monday) if days_until_monday > 0 else today

    week_label = start_date.strftime("W%W-%Y")
    logger.info("Generating weekly plan for week starting %s (%s)", start_date, week_label)

    # Step 1: Load the current strategy document
    strategy_context = load_strategy_context()
    logger.info("Loaded strategy context: %d files", len(strategy_context))

    # Step 2: Load the most recent weekly analysis
    latest_analysis = load_latest_analysis()
    if latest_analysis:
        logger.info("Loaded latest weekly analysis")
    else:
        logger.info("No previous weekly analysis found (first run)")

    # Step 3: Generate the content memory summary
    content_memory = generate_content_memory_summary()
    logger.info("Generated content memory summary")

    # Step 4: Determine current seasonal window
    seasonal_calendar = strategy_context.get("seasonal_calendar", {})
    seasonal_context = get_current_seasonal_window(
        seasonal_calendar.get("seasons", [])
    )
    logger.info("Seasonal context: %s", seasonal_context[:100] if seasonal_context else "None")

    # Step 5: Load keyword performance data
    keyword_data = build_keyword_performance_data(
        strategy_context.get("keyword_lists", {}),
    )

    # Step 6: Load negative keywords
    neg_kw_data = strategy_context.get("negative_keywords", {})
    negative_keywords = [
        item["term"] if isinstance(item, dict) else item
        for item in neg_kw_data.get("negative_keywords", [])
    ]

    # Step 7: Call Claude to generate the plan
    claude = claude or ClaudeAPI()
    plan = claude.generate_weekly_plan(
        strategy_doc=strategy_context.get("strategy_doc", ""),
        weekly_analysis=latest_analysis,
        content_memory=content_memory,
        seasonal_context=seasonal_context,
        keyword_data=keyword_data,
        negative_keywords=negative_keywords,
        week_start_date=start_date,
    )

    _validate_plan_structure(plan)

    # Step 8: Validate against constraints
    content_log = _load_content_log()
    # Load Pinterest-specific board structure directly (not from shared context)
    try:
        board_structure = json.loads(
            (STRATEGY_DIR / "pinterest" / "board-structure.json").read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Could not load board-structure.json: %s", e)
        board_structure = {}
    violations = validate_plan(plan, content_memory, content_log, board_structure)

    # Step 9: Retry loop -- targeted replacement first, full regen as fallback
    max_retries = 2
    retry_count = 0
    while violations and retry_count < max_retries:
        targeted = [v for v in violations if v["severity"] == "targeted"]
        structural = [v for v in violations if v["severity"] == "structural"]

        logger.warning(
            "Plan validation found %d issues (retry %d/%d): "
            "%d targeted, %d structural. %s",
            len(violations), retry_count + 1, max_retries,
            len(targeted), len(structural),
            violation_messages(violations),
        )

        if structural:
            # Structural issues require full plan regeneration
            logger.info("Structural violations present -- full plan regeneration")
            plan = claude.generate_weekly_plan(
                strategy_doc=strategy_context.get("strategy_doc", ""),
                weekly_analysis=latest_analysis + "\n\n" + _build_reprompt_context(violations),
                content_memory=content_memory,
                seasonal_context=seasonal_context,
                keyword_data=keyword_data,
                negative_keywords=negative_keywords,
                week_start_date=start_date,
            )
        else:
            # Only targeted violations -- attempt surgical replacement
            replaceable = identify_replaceable_posts(plan, violations)

            if not replaceable:
                # Targeted violations but can't identify posts (e.g., pin neg-keyword
                # on an existing: source) -- fall back to full regen
                logger.warning(
                    "Targeted violations but no replaceable posts found. "
                    "Falling back to full regeneration."
                )
                plan = claude.generate_weekly_plan(
                    strategy_doc=strategy_context.get("strategy_doc", ""),
                    weekly_analysis=latest_analysis + "\n\n" + _build_reprompt_context(violations),
                    content_memory=content_memory,
                    seasonal_context=seasonal_context,
                    keyword_data=keyword_data,
                    negative_keywords=negative_keywords,
                    week_start_date=start_date,
                )
            elif len(replaceable) > len(plan.get("blog_posts", [])) * 0.5:
                # Too many posts need replacement -- surgical fix is pointless
                logger.info(
                    "Too many posts need replacement (%d of %d). Full regeneration.",
                    len(replaceable), len(plan.get("blog_posts", [])),
                )
                plan = claude.generate_weekly_plan(
                    strategy_doc=strategy_context.get("strategy_doc", ""),
                    weekly_analysis=latest_analysis + "\n\n" + _build_reprompt_context(violations),
                    content_memory=content_memory,
                    seasonal_context=seasonal_context,
                    keyword_data=keyword_data,
                    negative_keywords=negative_keywords,
                    week_start_date=start_date,
                )
            else:
                # Surgical replacement of specific posts
                logger.info(
                    "Attempting targeted replacement of %d post(s): %s",
                    len(replaceable), list(replaceable.keys()),
                )

                posts_to_replace = []
                all_slots = []
                all_offending_pin_ids: set[str] = set()
                for info in replaceable.values():
                    # Include violation reasons alongside the post for context
                    post_with_violations = dict(info["post"])
                    post_with_violations["_violations"] = [
                        v["message"] for v in info["violations"]
                    ]
                    posts_to_replace.append(post_with_violations)
                    all_slots.extend(info["slots"])
                    all_offending_pin_ids.update(info["pin_ids"])

                offending_post_ids = set(replaceable.keys())

                # Build context about the rest of the plan
                kept_posts = [
                    p for p in plan.get("blog_posts", [])
                    if p.get("post_id") not in offending_post_ids
                ]
                kept_pins = [
                    p for p in plan.get("pins", [])
                    if p.get("pin_id") not in all_offending_pin_ids
                ]

                plan_context = {
                    "kept_post_topics": [p.get("topic", "") for p in kept_posts],
                    "kept_pin_boards": dict(Counter(
                        p.get("target_board", "") for p in kept_pins
                    )),
                    "kept_pin_pillars": dict(Counter(
                        p.get("pillar") or 0 for p in kept_pins
                    )),
                    "week_number": plan.get("week_number", ""),
                    "date_range": plan.get("date_range", ""),
                }

                recent_topics_list = extract_recent_topics(
                    content_log, TOPIC_REPETITION_WINDOW_WEEKS
                )

                try:
                    replacements = claude.generate_replacement_posts(
                        posts_to_replace=posts_to_replace,
                        slots_to_fill=all_slots,
                        plan_context=plan_context,
                        content_memory=content_memory,
                        negative_keywords=negative_keywords,
                        recent_topics=recent_topics_list,
                    )

                    # Validate replacement pin count before splicing
                    expected_pins = len(all_slots)
                    actual_pins = len(replacements.get("pins", []))
                    if actual_pins != expected_pins:
                        logger.warning(
                            "Replacement returned %d pins, expected %d. "
                            "Falling back to full regen on next iteration.",
                            actual_pins, expected_pins,
                        )
                        # Force structural path on next iteration
                        violations = [
                            {**v, "severity": "structural"} for v in violations
                        ]
                        retry_count += 1
                        continue

                    plan = splice_replacements(
                        plan, replacements,
                        offending_post_ids, all_offending_pin_ids,
                    )
                except Exception as e:
                    logger.error(
                        "Targeted replacement failed: %s. "
                        "Falling back to full regen on next iteration.", e,
                    )
                    violations = [
                        {**v, "severity": "structural"} for v in violations
                    ]
                    retry_count += 1
                    continue

        violations = validate_plan(plan, content_memory, content_log, board_structure)
        retry_count += 1

    if violations:
        logger.warning(
            "Plan still has %d violations after %d retries. Proceeding with warnings: %s",
            len(violations), max_retries, violation_messages(violations),
        )

    # Step 10: Write the approved plan to Google Sheets
    try:
        sheets = sheets or SheetsAPI()
        sheets.write_weekly_review(
            analysis_summary=latest_analysis[:500] if latest_analysis else "First week - no prior analysis",
            content_plan=plan,
            performance_data={},
        )
        logger.info("Written plan to Google Sheets Weekly Review tab")
    except Exception as e:
        logger.error("Failed to write to Google Sheets: %s", e)

    # Step 11: Save plan locally as JSON (atomic write via temp+rename)
    plan_filename = f"weekly-plan-{start_date.isoformat()}.json"
    plan_path = DATA_DIR / plan_filename
    tmp_path = plan_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp_path.replace(plan_path)
    except OSError as e:
        logger.error("Failed to write plan file: %s", e)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    logger.info("Saved plan to %s", plan_path)

    # Step 12: Send Slack notification
    try:
        slack = slack or SlackNotify()
        num_posts = len(plan.get("blog_posts", []))
        num_pins = len(plan.get("pins", []))
        slack.notify_review_ready(
            f"Generated plan: {num_posts} blog posts, {num_pins} pins for week of {start_date}"
        )
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    return plan


def _validate_plan_structure(plan: object) -> None:
    """Validate that the Claude-generated plan has the expected structure.

    Checks that plan is a dict with non-empty "blog_posts" and "pins" lists.
    Raises ValueError immediately if the structure is wrong, rather than
    silently producing an empty week via .get() defaults.

    Args:
        plan: The parsed plan object from Claude's response.

    Raises:
        ValueError: If the plan structure is invalid.
    """
    if not isinstance(plan, dict):
        raise ValueError(
            f"Plan must be a dict, got {type(plan).__name__}. "
            "Claude may have returned an unexpected response format."
        )

    missing = []
    if "blog_posts" not in plan:
        missing.append("blog_posts")
    elif not isinstance(plan["blog_posts"], list) or not plan["blog_posts"]:
        missing.append("blog_posts (must be a non-empty list)")

    if "pins" not in plan:
        missing.append("pins")
    elif not isinstance(plan["pins"], list) or not plan["pins"]:
        missing.append("pins (must be a non-empty list)")

    if missing:
        raise ValueError(
            f"Plan is missing required fields: {', '.join(missing)}. "
            "Claude may have returned different key names or an empty plan."
        )


def _build_reprompt_context(violations: list[dict]) -> str:
    """
    Build the reprompt context string from plan violations.

    Consolidates the violation list into a formatted message for Claude
    to use when regenerating or fixing the plan.

    Args:
        violations: Structured violation list from validate_plan().

    Returns:
        str: Formatted reprompt context for the Claude API call.
    """
    violation_text = "\n".join(f"- {v['message']}" for v in violations)
    return (
        f"The generated plan has the following constraint violations that "
        f"must be fixed:\n\n{violation_text}\n\n"
        f"Please regenerate the plan, fixing these specific issues while "
        f"keeping the rest of the plan intact."
    )


def generate_weekly_plan(
    claude: Optional[ClaudeAPI] = None,
    sheets: Optional[SheetsAPI] = None,
    slack: Optional[SlackNotify] = None,
) -> dict:
    """
    Convenience alias for generate_plan() with default date.

    Returns:
        dict: The generated weekly plan.
    """
    return generate_plan(claude=claude, sheets=sheets, slack=slack)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    print("Generating weekly content plan...")
    plan = generate_weekly_plan()
    print(
        f"Generated plan with {len(plan.get('blog_posts', []))} blog posts "
        f"and {len(plan.get('pins', []))} pins"
    )
