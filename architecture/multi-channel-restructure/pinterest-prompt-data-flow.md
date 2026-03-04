# Pinterest Prompt Data Flow — Monday Morning Pipeline

**Date:** 2026-03-04 (updated after strategy context enrichment)
**Purpose:** Map exactly what data each step receives and produces

---

## Workflow: collect-analytics.yml (Monday 5:30am ET)

```
Step 0a: pull_analytics.py
  Input:  Pinterest API (last 30 days of pin metrics)
          + data/content-log.jsonl (to match pins to entries)
  Does:   Updates impressions, saves, clicks on existing content log entries
  Output: data/content-log.jsonl (entries now have fresh metrics)

              │
              ▼

Step 0b: content_memory.py
  Input:  data/content-log.jsonl
  Does:   Pure Python aggregation — 8 sections:
          1. Recent topics (last 10 weeks)
          2. All blog posts (grouped by type + pillar)
          3. Pillar mix (recent + all time, content type, board, funnel)
          4. Keyword frequency (top 15 + untargeted, with performance)
          5. Images used recently (last 90 days)
          6. Fresh pin candidates (posts with no pin in 4+ weeks)
          7. Treatment tracker (URLs with treatment counts in 60 days)
          8. Performance history (pillar lifetime, top keywords by saves,
             compounding signal, top all-time performers, pillar trends)
  Output: data/content-memory-summary.md
```

---

## Workflow: pinterest-weekly-review.yml (Monday 6:00am ET)

```
Step 1: weekly_analysis.py → Claude Sonnet
  Input:  data/content-log.jsonl (filtered to Pinterest entries only,
              channel filter applied before metric computation)
          + previous week's analysis (analysis/weekly/YYYY-wNN-review.md)
          + pin-schedule.json (planned vs actual)
          + strategy/current-strategy.md (via load_strategy_context())
          + data/content-memory-summary.md (via load_content_memory())
  Does:   Computes aggregates by every dimension (pillar, keyword,
          board, template, funnel, image source, pin type)
          → sends to Claude with weekly_analysis.md prompt
          → Claude evaluates performance against strategic intent,
            uses content memory to identify keyword saturation,
            compounding signals, and topic coverage gaps
  Output: analysis/weekly/YYYY-wNN-review.md
          (top/bottom pins, dimension rankings, strategic alignment
          check, cross-channel notes, recommendations)

              │
              ▼

Step 2: generate_weekly_plan.py → Claude Sonnet
  Input:  strategy/current-strategy.md (full strategy document)
          + analysis/weekly/latest review (Step 1's output)
          + data/content-memory-summary.md (Step 0b's output)
          + strategy/seasonal-calendar.json
          + strategy/keyword-lists.json
          + strategy/negative-keywords.json
          + strategy/pinterest/board-structure.json
          + strategy/cta-variants.json
  Does:   Sends everything to Claude with weekly_plan.md prompt.
          Topic dedup scoped to Pinterest-only — topics covered on
          other channels are NOT off-limits.
  Output: Weekly plan JSON (8-10 blog posts + 28 pins)
          → written to Google Sheet "Weekly Review" tab
          → Slack notification
```

---

## What each step knows

| | Strategy | Content Memory | Performance Data | Cross-Channel |
|---|---|---|---|---|
| **pull_analytics.py** | No | No | Writes it | No |
| **content_memory.py** | No | Produces it (8 sections) | Reads content log | Channel-aware tags |
| **weekly_analysis.py** | Full strategy doc | Full (incl. Section 8 perf history) | Full access | Placeholder ready |
| **generate_weekly_plan.py** | Full (1,056 lines) | Full (incl. Section 8 perf history) | Via analysis output | Cross-channel framing note |

---

## Key design decisions

**Why the analysis now gets strategy + content memory:**
Previously the analysis operated in a strategic vacuum — it saw numbers but didn't know the strategy behind them. It couldn't distinguish "Pillar 4 underperforms because the strategy predicts low volume" from "Pillar 4 underperforms because execution is bad." Now it can evaluate performance against strategic intent and flag genuine concerns vs expected patterns.

**Why we kept analysis and planning as separate calls:**
- Competing objectives (honest analysis vs. constructive planning) benefit from separation
- Easier to debug — analysis artifact shows what the planner was told
- Retry granularity — plan validation failures don't re-run the analysis
- Token pressure — combined call would be 30K+ input tokens in one shot

**Content memory Section 8 (Performance History) flows automatically:**
The planner already loads content memory — Section 8 is included without any changes to `generate_weekly_plan.py` or `collect-analytics.yml`.

---

## Monthly review pipeline (separate workflow, monthly-review.yml)

```
Step 1: pull_analytics.py (30-day window)
  Same as weekly but with broader date range.

Step 2: monthly_review.py → Claude Opus
  Input:  30-day aggregated performance data
          + all weekly analyses from this month
          + strategy/current-strategy.md (summary)
          + pillar/keyword/board/content-type/image-source aggregates
          + seasonal context
          + data/content-memory-summary.md (via load_content_memory())
          + cross-channel summary (placeholder, empty until TikTok launches)
  Output: analysis/monthly/YYYY-MM-review.md
          (strategic recommendations, pillar assessment, keyword strategy,
          cross-channel observations section)
```

---

## Prompt files

| Prompt | Used by | Model | Strategy | Content Memory | Cross-Channel |
|--------|---------|-------|----------|---------------|---------------|
| `prompts/pinterest/weekly_analysis.md` | weekly_analysis.py → claude_api.analyze_weekly_performance() | Sonnet | `{{strategy_context}}` | `{{content_memory_summary}}` | `{{cross_channel_summary}}` |
| `prompts/pinterest/weekly_plan.md` | generate_weekly_plan.py → claude_api.generate_weekly_plan() | Sonnet | `{{strategy_summary}}` | `{{content_memory_summary}}` | Cross-channel framing note |
| `prompts/pinterest/monthly_review.md` | monthly_review.py → claude_api.run_monthly_review() | Opus | `{{current_strategy_summary}}` | `{{content_memory_summary}}` | `{{cross_channel_summary}}` |
| `prompts/pinterest/pin_copy.md` | generate_pin_content.py → claude_api.generate_pin_copy() | Sonnet | — | — | — |
| `prompts/pinterest/weekly_plan_replace.md` | regen_weekly_plan.py → claude_api.generate_replacement_posts() | Sonnet | — | — | — |

---

## Token budget impact

| Call | Before | After | Delta |
|------|--------|-------|-------|
| Weekly analysis (Sonnet) | ~10K input | ~31K input | +$0.063/week |
| Monthly review (Opus) | ~25K input | ~40K input | +$0.075/month |
| Annual total | | | ~$4.20/year |
