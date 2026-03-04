# Multi-Channel Architecture: Revised Phase 8+ Proposal

**Date:** 2026-03-03
**Author:** Claude (Engineering)
**Audience:** Product leadership
**Status:** Draft — awaiting approval

---

## Executive Summary

The original Phase 8 ("Two-step planning split") was designed around an assumption that Pinterest and TikTok would share unified topic selection, with each channel deriving its own content from shared topics. After deeper analysis, this assumption doesn't hold — and forcing it adds complexity without value.

This document proposes a revised architecture: **independent planning per channel, with a shared context layer that actively collects fresh cross-channel data before any planner runs.** Each channel owns its own topic selection and content strategy. The shared layer ensures every planner sees current performance data from ALL channels, enabling informed decisions — including opportunistically adapting successful content from other channels.

Phase 8 is rescoped from a complex planning refactor to: generalize the shared context layer + restructure the weekly automation so cross-channel data is fresh when planners run.

---

## 1. Why Unified Topic Planning Doesn't Work

The original plan assumed both channels would:
1. Share a common set of weekly blog topics
2. Derive channel-specific content (pins, carousels) from those topics

Three structural problems invalidate this:

### 1.1 Blog posts are a Pinterest asset, not a shared asset

Pinterest pins exist to drive traffic to blog posts on goslated.com. Every pin has a destination URL. The content funnel is: **pin → blog post → app CTA → install.**

TikTok has no per-post linking. Content is consumed on-platform. The funnel is: **carousel/video → brand awareness → bio link → install.** TikTok content must be self-contained — it doesn't reference or promote blog posts.

Blog posts are therefore Pinterest infrastructure, not a multi-channel shared asset.

### 1.2 Topic selection is driven by different forces

| Driver | Pinterest | TikTok |
|--------|-----------|--------|
| Discovery mechanism | Search (user queries keywords) | Algorithm (platform surfaces content) |
| Content lifespan | Months to years (evergreen) | 48–72 hours peak, 90 days search tail |
| Topic selection driver | Search volume, keyword gaps, SEO opportunity | Hooks, trends, format novelty, controversy |
| Optimal content | "Easy weeknight chicken tacos" (searchable, specific) | "5 reasons meal kits are a scam" (provocative, shareable) |
| Reactive content | None — fully planned | 30% of content should be trend-reactive |

A unified planner would need to compromise between SEO-optimized topics (Pinterest) and algorithm-optimized topics (TikTok). Neither channel benefits from that compromise.

### 1.3 The split adds cost without enabling anything

Two Claude calls instead of one adds ~$0.10–0.20/week in API cost, plus engineering complexity (new intermediate data format, new prompt, two-step retry logic). The only benefit is enabling TikTok to share topics — which, per above, it shouldn't.

---

## 2. What IS Actually Shared

The channels don't need shared topic selection, but they do benefit from shared visibility. Each channel's planner should be able to see:

- **What the other channel has published** — topics, formats, timing
- **What has performed well on the other channel** — and understand that cross-channel success is informative but not predictive (what works on Pinterest may not work on TikTok, and vice versa)
- **Shared brand context** — voice, pillars, seasonal calendar, negative keywords

This enables **opportunistic content reuse** without forcing it. If a Pinterest blog post about "weeknight chicken tacos" gets strong saves, the TikTok planner can see that and choose to adapt it into a carousel — or not. The decision stays with the channel planner, informed by data.

Critically, this cross-channel data must be **fresh** when planners run. A planner seeing week-old data from another channel is making decisions on stale information.

| Shared Asset | Purpose | Current State |
|-------------|---------|---------------|
| **Content log** | Cross-channel visibility into what's been published and how it performed | Exists (`content-log.jsonl`), but no channel tagging |
| **Content memory** | Summarized view of content history, surfaced to planners as context | Exists (`content_memory.py`), but Pinterest-specific output format |
| **Strategy context** | Brand voice, pillars, seasonal calendar, negative keywords | Exists (`content_planner.py`), mostly channel-agnostic |
| **Analytics collection** | Fresh performance data from all channels | Currently bundled inside Pinterest's weekly review — not shared |
| **Analytics utilities** | Metric computation, dimension aggregation | Exists (`analytics_utils.py`), already channel-agnostic |
| **API wrappers** | Claude, Sheets, GCS, GitHub, Slack | Exist in `src/shared/apis/`, fully reusable |

---

## 3. Proposed Architecture

### 3.1 Automation flow

The key architectural change: **analytics collection is a shared step that runs before any channel-specific planning.**

```
┌─────────────────────────────────────────────────────────┐
│  SHARED: Collect & Refresh (Monday ~5:30am ET)          │
│                                                         │
│  1. Pull Pinterest analytics  (src/pinterest/)          │
│  2. Pull TikTok analytics     (src/tiktok/)             │
│  3. [Future channels...]                                │
│  4. Refresh content memory    (src/shared/)             │
│     → Reads ALL channel data from content log           │
│     → Generates summary with channel attribution        │
│     → Writes data/content-memory-summary.md             │
└────────────────────────┬────────────────────────────────┘
                         │ fresh cross-channel data ready
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐   ┌──────────────────────────────┐
│ PINTEREST            │   │ TIKTOK                        │
│ Weekly Review        │   │ Weekly Review                  │
│ (Monday ~6:00am)     │   │ (Monday ~6:00am)               │
│                      │   │                                │
│ 1. Weekly analysis   │   │ 1. Weekly analysis             │
│ 2. Generate plan     │   │ 2. Generate plan               │
│    (reads fresh      │   │    (reads fresh                │
│     content memory   │   │     content memory             │
│     with ALL channel │   │     with ALL channel           │
│     performance)     │   │     performance)               │
│ 3. Write to Sheet    │   │ 3. Write to Sheet              │
│ 4. Slack notify      │   │ 4. Slack notify                │
└─────────────────────┘   └──────────────────────────────┘
```

**Current flow** (Pinterest only):
```
weekly-review.yml (Monday 6am):
  1. Refresh Pinterest token
  2. Pull Pinterest analytics        ← analytics + planning bundled
  3. Generate content memory summary
  4. Run weekly performance analysis
  5. Generate weekly content plan
```

**Proposed flow** (multi-channel):
```
collect-analytics.yml (Monday ~5:30am):
  1. Refresh Pinterest token
  2. Pull Pinterest analytics
  3. Pull TikTok analytics (via Publer)
  4. Generate content memory summary (all channels, fresh data)
  5. Commit updated data files

pinterest-weekly-review.yml (Monday ~6:00am, after collect-analytics):
  1. Run weekly performance analysis (Pinterest-specific)
  2. Generate weekly content plan (reads fresh cross-channel content memory)
  3. Write to Sheet, notify Slack

tiktok-weekly-review.yml (Monday ~6:00am, after collect-analytics):
  1. Run weekly performance analysis (TikTok-specific)
  2. Generate weekly content plan (reads fresh cross-channel content memory)
  3. Write to Sheet, notify Slack
```

The same pattern applies to monthly reviews: a shared analytics refresh runs before any channel-specific monthly review.

### 3.2 Data architecture

```
┌───────────────────────────────────────────────────────┐
│                 Shared Context Layer                   │
│                                                       │
│  Strategy files     Content log        Content memory │
│  (brand voice,      (channel-tagged,   (generated     │
│   pillars,           full history       from log,     │
│   seasonal           of ALL channels,   includes      │
│   calendar,          refreshed before   channel        │
│   keywords)          planning runs)     attribution)  │
│                                                       │
├──────────────────────┬────────────────────────────────┤
│  Pinterest Planner   │    TikTok Planner              │
│                      │                                │
│  Topics driven by:   │    Topics driven by:           │
│  • SEO keywords      │    • Hook effectiveness        │
│  • Search volume     │    • Trend relevance           │
│  • Pillar strategy   │    • Attribute weights         │
│  • Blog-first model  │    • Explore/exploit ratio     │
│                      │                                │
│  Reads:              │    Reads:                      │
│  • Shared strategy   │    • Shared strategy           │
│  • Content memory    │    • Content memory            │
│    (sees all channel │      (sees all channel         │
│     performance,     │       performance,             │
│     FRESH as of      │       FRESH as of              │
│     this morning)    │       this morning)            │
│  • Pinterest board   │    • TikTok attribute          │
│    structure         │      taxonomy                  │
│                      │                                │
│  Output:             │    Output:                     │
│  8-10 blog posts     │    7-21 carousel specs         │
│  + 28 pin specs      │    (self-contained)            │
│                      │                                │
│  Writes to log:      │    Writes to log:              │
│  channel: "pinterest"│    channel: "tiktok"           │
└──────────────────────┴────────────────────────────────┘
```

### 3.3 Key design decisions

**Independent planning, shared fresh data.** Each channel runs its own planning call with its own prompt, constraints, and output format. All planners read the same content memory, which was generated from freshly-pulled analytics across ALL channels earlier that morning.

**Shared analytics collection runs first.** A dedicated workflow pulls performance data from every active channel and refreshes the content memory summary before any channel-specific planning begins. This ensures no planner is working with stale cross-channel data.

**Cross-channel awareness is informative, not prescriptive.** The content memory tells each planner what other channels have published and how it performed. The planner decides whether to adapt, riff on, or ignore cross-channel content. This is handled in the planning prompt's framing, not in validation logic.

**Channel-tagged content log.** The existing `content-log.jsonl` gains a `channel` field. Content memory surfaces this attribution: *"Topic X was covered on Pinterest (W10, 450 impressions, 38 saves)"* — so a TikTok planner can see the topic worked on Pinterest and decide whether it's worth adapting for a different format and audience.

**No intermediate data formats.** There is no shared topic plan, content catalog, or reuse registry. The content log IS the shared data layer. Each planner reads it (via content memory), gets context, and makes its own decisions.

**Pinterest planning logic unchanged.** The existing single-shot planning call (`generate_weekly_plan.py` → `claude.generate_weekly_plan()`) stays as-is. The only change is that it's split into a separate workflow from the analytics pull.

---

## 4. Rescoped Phase Plan

### Phase 8 (Rescoped): Shared context layer + workflow restructure

**Original scope:** Two-step planning split (unified topic plan → channel-specific derivation)
**New scope:** Make the shared context layer channel-aware and restructure the weekly automation so cross-channel data is fresh when planners run

**What gets built:**

#### 4.1 Content log: add channel tagging

- Add `channel` field to content log entries. Backfill existing entries as `"pinterest"`.
- Update `content_log.py` write functions to accept and include channel.
- Update `blog_deployer.py` and `post_pins.py` to tag entries with `"pinterest"`.
- Backward-compatible: missing `channel` field defaults to `"pinterest"` on read.

#### 4.2 Content memory: channel-aware output

- The summary generated by `content_memory.py` includes channel attribution on entries — so a planner reading the summary can distinguish "this topic was covered on Pinterest and got 400 saves" from "this topic was covered on TikTok and got 50K views."
- Function signature gains an optional `channel` parameter for filtering, but defaults to showing all channels.

#### 4.3 Content planner: remove Pinterest hardcoding

- `load_strategy_context()` currently hardcodes loading `pinterest/board-structure.json`. Refactor to load only shared strategy files by default (brand voice, keywords, seasonal calendar, negative keywords).
- Channel-specific planners load their own structure files directly (Pinterest loads `board-structure.json`, TikTok loads `attribute-taxonomy.json`).

#### 4.4 Content log utility: generalize idempotency check

- Add `is_content_posted(content_id, channel)` that checks for the appropriate platform ID field (`pinterest_pin_id`, `publer_post_id`, etc.).
- Keep `is_pin_posted()` as a backward-compatible wrapper.

#### 4.5 Workflow restructure: split analytics from planning

- Extract analytics pull + content memory refresh from `weekly-review.yml` into a new `collect-analytics.yml` workflow.
- `collect-analytics.yml` runs Monday ~5:30am ET. Pulls analytics from all active channels, refreshes content memory, commits updated data files.
- Rename `weekly-review.yml` → `pinterest-weekly-review.yml`. Runs Monday ~6:00am ET. Depends on `collect-analytics` completing (via `workflow_run` trigger or time offset). Contains only: weekly analysis → plan generation → Sheet write → Slack notify.
- This pattern is ready for `tiktok-weekly-review.yml` to plug in later (Phase 10).

#### 4.6 Strategy file cleanup

- Move `strategy/tiktok/archetypes.md` and `strategy/tiktok/brand-guidelines.md` to `strategy/` root — they're brand-level docs, not TikTok-specific.

**What does NOT change:**
- Pinterest planning logic (`generate_weekly_plan.py`) — untouched
- `ClaudeAPI.generate_weekly_plan()` — untouched
- `prompts/pinterest/weekly_plan.md` — untouched
- Plan validator — stays Pinterest-specific in `src/pinterest/`
- No new prompts or Claude calls
- Pinterest weekly output is identical — same plan structure, same Sheet output

**Effort:** 5–7 hours
**Risk:** LOW-MEDIUM (workflow restructure changes automation timing, but planning logic is untouched)

**Verify:**
- `collect-analytics.yml` runs cleanly, pulls Pinterest data, refreshes content memory
- `pinterest-weekly-review.yml` runs after collection, produces identical plan output
- `python -m pytest tests/` passes
- Existing content log entries without `channel` field are treated as `"pinterest"` by default
- Content memory summary includes channel attribution on entries
- End-to-end: Monday automation produces the same Weekly Review Sheet output as before

---

### Phases 9–12: Unchanged in scope, cleaner integration

The downstream TikTok phases are unaffected by this rescope. They were already designed as independent channel modules. The workflow restructure makes integration cleaner:

| Phase | Integration point |
|-------|------------------|
| **9: Carousel rendering** | No planning dependency. Pure rendering infrastructure. |
| **10: Content generation** | TikTok planner reads shared context + cross-channel content memory (already fresh from `collect-analytics`). Creates `tiktok-weekly-review.yml` that runs after `collect-analytics`, parallel to Pinterest's review. |
| **11: Posting via Publer** | TikTok posting writes to content log with `channel: "tiktok"`. |
| **12: Analytics + feedback** | TikTok analytics pull is added as a step in `collect-analytics.yml`. Cross-channel data automatically flows to all planners the following week. |

**Phase 10 detail (TikTok planner design):**

The TikTok planner (`src/tiktok/generate_weekly_plan.py`) will:
1. Load shared context via `content_planner.load_strategy_context()`
2. Load content memory via `content_memory.generate_content_memory_summary()` — already fresh, already includes Pinterest performance data with channel attribution
3. Load TikTok-specific context (attribute taxonomy, format structure, trend signals)
4. Call `ClaudeAPI.generate_tiktok_plan()` — a new method with its own prompt (`prompts/tiktok/weekly_plan.md`)
5. Validate against TikTok-specific constraints
6. Write to Sheets, save JSON, notify Slack

The planning prompt will include framing like: *"Below is content published across all channels recently, with performance data. High performers on other channels may be worth adapting for TikTok, but cross-channel success is not guaranteed — Pinterest is search-driven and evergreen, TikTok is algorithm-driven and hook-dependent. Use your judgment."*

**Phase 12 detail (closing the loop):**

When Phase 12 adds TikTok analytics, it plugs into the existing `collect-analytics.yml`:
```
collect-analytics.yml (updated):
  1. Refresh Pinterest token
  2. Pull Pinterest analytics
  3. Pull TikTok analytics (via Publer)    ← added in Phase 12
  4. Generate content memory summary        ← already cross-channel aware
  5. Commit updated data files
```

No workflow restructuring needed at that point — the shared collection pattern is already in place.

---

## 5. What This Means for the Implementation Timeline

| Phase | Original hours | Revised hours | Change |
|-------|---------------|---------------|--------|
| 8: Shared context layer + workflow restructure | 8–12 | 5–7 | Simpler planning scope; adds workflow restructure |
| 9: Carousel rendering | 35–50 | 35–50 | Unchanged |
| 10: Content generation + cross-channel prompts | 55–75 | 60–83 | Adds Pinterest prompt updates for cross-channel awareness |
| 11: Posting via Publer | 25–35 | 25–35 | Unchanged |
| 12: Analytics + feedback | 25–38 | 25–38 | Unchanged; plugs into existing collect-analytics workflow |
| **MVP total (8–12)** | **148–210** | **150–213** | ~2h added (cross-channel prompts) |

The timeline savings are modest because the bulk of the work was always in Phases 9–12 (building the TikTok pipeline itself). The real wins are:
- **Risk reduction:** No refactoring of the live Pinterest planning logic
- **Cleaner integration:** Phase 12 just adds a step to an existing workflow instead of restructuring automation from scratch
- **Fresh data guarantee:** Every planner always sees current cross-channel performance

---

## 6. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Workflow restructure causes timing issues (planning runs before analytics completes) | Medium | High | Use `workflow_run` trigger or sufficient time offset. Test end-to-end before merging. |
| Content memory refactoring breaks Pinterest | Low | High | Comprehensive test coverage; missing `channel` field defaults to `"pinterest"` |
| Cross-channel data misleads a planner (e.g., TikTok copies a Pinterest strategy that doesn't translate) | Low | Low | Prompt framing explicitly notes cross-channel performance is informative, not predictive |
| Content log migration (adding channel field) breaks existing readers | Low | Medium | Backward-compatible: all existing code treats missing channel field as Pinterest |
| We later discover channels DO need shared topic selection | Very low | Medium | Can add a shared planning step later without architectural changes — the context layer supports it |

---

## 7. Recommendation

Approve the rescoped Phase 8 as described: **generalize the shared context layer, restructure weekly automation for fresh cross-channel data, keep channel planning fully independent.**

This approach:
- Preserves the live Pinterest planning logic with zero changes
- Ensures every planner sees fresh cross-channel performance data (not stale week-old numbers)
- Gives each channel full autonomy over its content strategy
- Provides cross-channel visibility so planners can opportunistically adapt successful content
- Makes Phase 12 (TikTok analytics) a simple plug-in to an existing workflow pattern
- Requires no new intermediate data formats, prompts, or Claude calls
- Sets up clean infrastructure for Phase 10 (TikTok planner) to integrate naturally
