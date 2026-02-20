# Content Generation Pipeline -- Implementation Report

**Date:** 2026-02-20
**Implemented by:** Content Generation Agent
**Files implemented:** 5 Python modules

---

## 1. What Was Implemented

Five Python modules that form the content generation pipeline for Slated's Pinterest automation system. These scripts transform a weekly strategy into blog posts, pin copy, pin images, and deployed content on goslated.com.

### Files

| File | Purpose | Lines of Code |
|------|---------|--------------|
| `src/generate_weekly_plan.py` | Weekly content plan generation + content memory summary | ~500 |
| `src/generate_blog_posts.py` | Blog post generation orchestrator | ~260 |
| `src/blog_generator.py` | Individual blog post generator (4 types) | ~450 |
| `src/generate_pin_content.py` | Pin copy + image sourcing for all 28 weekly pins | ~470 |
| `src/blog_deployer.py` | Blog deployment to goslated.com + pin schedule creation | ~440 |

### No files in `src/apis/` were modified.

All API wrappers are imported and called through their defined interfaces. Another agent is implementing those.

---

## 2. The Flow: How These Scripts Chain Together

```
MONDAY 6:00 AM (automated, cron)
    |
    v
generate_weekly_plan.py
    |-- Loads strategy context (7 strategy files)
    |-- Loads most recent weekly analysis from analysis/weekly/
    |-- Generates content memory summary (Python aggregation, no LLM call)
    |     |-- Reads data/content-log.jsonl
    |     |-- Produces 7 sections of aggregated data
    |     |-- Writes to data/content-memory-summary.md
    |-- Determines current seasonal window from seasonal-calendar.json
    |-- Builds keyword performance data from content log
    |-- Calls claude_api.generate_weekly_plan() with all context
    |-- Validates plan against 8 constraint categories
    |-- Re-prompts Claude (up to 2x) if constraints are violated
    |-- Writes plan to Google Sheets "Weekly Review" tab
    |-- Saves plan as data/weekly-plan-{date}.json
    |-- Sends Slack: "Weekly review ready"
    |
    v
[HUMAN APPROVAL in Google Sheet]
    |
    v
generate_blog_posts.py (triggered by plan approval)
    |-- Loads approved plan (from JSON file or Sheets)
    |-- Filters to new content only (not fresh treatments)
    |-- For each blog post spec:
    |     |-- blog_generator.generate() dispatches by type:
    |     |     |-- generate_recipe_post() -> blog_post_recipe.md prompt
    |     |     |-- generate_weekly_plan_post() -> blog_post_weekly_plan.md prompt
    |     |     |-- generate_guide_post() -> blog_post_guide.md prompt
    |     |     |-- generate_listicle_post() -> blog_post_listicle.md prompt
    |     |-- Validates: frontmatter completeness, word count, CTA presence
    |     |-- For recipes: validates Schema.org fields (ISO 8601 durations, etc.)
    |-- Saves MDX files to data/generated/blog/
    |-- Saves metadata to data/blog-generation-results.json
    |-- Returns post_id -> {slug, title, file_path, mdx_content, status}
    |
    v
generate_pin_content.py (runs after blog generation)
    |-- Loads plan + blog generation results
    |-- Generates pin copy in batches of 6 via claude_api.generate_pin_copy()
    |     |-- Falls back to individual calls if batch fails
    |-- For each of 28 pins:
    |     |-- Sources image by tier:
    |     |     Tier 1 (stock): claude generates search query -> stock_api.search()
    |     |           -> filter_previously_used() -> download_image()
    |     |     Tier 2 (AI): claude generates image prompt -> image_gen.generate()
    |     |     Tier 3 (template): no image sourcing, pin_assembler handles it
    |     |-- Calls pin_assembler.assemble_pin() to render final PNG
    |     |-- Builds UTM link: goslated.com/blog/{slug}?utm_source=pinterest&...
    |-- Writes all pins to Google Sheets "Content Queue" tab
    |-- Sends Slack: "28 pins + N blog posts ready for review"
    |-- Saves results to data/pin-generation-results.json
    |
    v
[HUMAN APPROVAL in Google Sheet]
    |
    v
blog_deployer.py (triggered by content approval)
    |-- Reads content approvals from Google Sheets
    |     (falls back to local files if Sheets unavailable)
    |-- Commits approved blog posts to goslated.com repo:
    |     |-- Tries batch commit via github_api.commit_multiple_posts()
    |     |-- Falls back to individual commits on failure
    |-- Verifies each URL is live via github_api.verify_deployment()
    |     |-- Retries once on failure, sends Slack alert if still failing
    |-- Updates Google Sheet with confirmed live URLs
    |-- Creates pin schedule (data/pin-schedule.json) for post_pins.py
    |     |-- Each pin entry: pin_id, title, description, alt_text,
    |     |   board_id, link, image_path, scheduled_date, scheduled_slot
    |-- Appends entries to data/content-log.jsonl (metrics initialized to 0)
    |-- Sends Slack: "Week is live. N pins scheduled Tue-Mon, M blog posts deployed."
    |
    v
[DAILY POSTING by post_pins.py -- separate agent]
```

---

## 3. How Content Memory Summary Is Generated

The content memory summary (`data/content-memory-summary.md`) is generated by pure Python aggregation in `generate_weekly_plan.generate_content_memory_summary()`. No LLM call is involved. The function reads `data/content-log.jsonl` line by line, parses each JSON entry, and computes the following seven sections:

### Section 1: RECENT TOPICS (Last 4 Weeks)
- Deduplicates by `blog_slug`
- Sorts by date descending
- Shows: date, pillar, title, content type

### Section 2: ALL BLOG POSTS
- Groups unique blog slugs by `content_type`, then by `pillar`
- Shows nested hierarchy: type > pillar > list of posts

### Section 3: PILLAR MIX
- Four sub-sections:
  - **Last 4 weeks:** Pin count and percentage per pillar (P1-P5)
  - **All time:** Same breakdown for entire log history
  - **Content type (last 4 weeks):** Counter by content_type
  - **Board distribution (last 4 weeks):** Counter by board name
  - **Funnel layer (last 4 weeks):** Counter by funnel_layer (discovery/consideration/conversion)

### Section 4: KEYWORD FREQUENCY
- Counts `primary_keyword` and `secondary_keywords` across all entries
- Shows **Top 15** by usage count with last-used date and save_rate if available
- Loads `strategy/keyword-lists.json` and computes **untargeted keywords** (target keywords from strategy that have never been used)

### Section 5: IMAGES USED RECENTLY (Last 90 Days)
- Collects all `image_source:image_id` pairs from entries in the last 90 days
- Outputs as a single-line comma-separated list for stock photo dedup

### Section 6: FRESH PIN CANDIDATES
- Finds all unique blog slugs where the most recent pin is 4+ weeks old AND treatment count < 5
- Sorts by `total_saves` descending (best performers first)
- Shows: title, slug, pillar, saves, impressions, treatment count, last pin date
- Limited to top 20 candidates

### Section 7: TREATMENT TRACKER
- Counts pins per URL in the last 60 days
- Flags URLs approaching the 5-treatment limit with `[APPROACHING LIMIT]`
- Flags URLs at the limit with `[AT LIMIT - NO MORE TREATMENTS]`

The summary is written to `data/content-memory-summary.md` and stays under ~3K tokens even after a full year of content.

---

## 4. Validation Logic and What Happens When Constraints Are Violated

`generate_weekly_plan.validate_plan()` runs 8 constraint checks against the generated plan:

| # | Constraint | Implementation |
|---|-----------|---------------|
| 1 | **Total pins = 28** | Counts `plan["pins"]` length |
| 2 | **Pillar mix within ranges** | Counts pins per pillar vs. targets: P1(9-10), P2(7-8), P3(5-6), P4(2-3), P5(4-5). Allows +/-1 pin tolerance. |
| 3 | **No topic repetition within 4 weeks** | Loads recent topics from content log, computes word-level overlap (>60% shared words flags a violation) |
| 4 | **Max 5 pins per board** | Counter by `target_board` vs. `max_pins_per_board_per_week` from board-structure.json |
| 5 | **Max 2 fresh treatments per URL per week** | Counts pins with `pin_type == "fresh-treatment"` grouped by slug |
| 6 | **No more than 3 consecutive same-template** | Sorts pins by scheduled day+slot, checks sliding window of 4 pins for identical templates |
| 7 | **4 pins per day, Tue-Mon** | Counter by `scheduled_date` -- each of 7 posting days must have exactly 4 |
| 8 | **No negative keywords** | Checks all pin and blog post keywords and topics against negative-keywords.json. Both exact and substring matching. |

**When violations are found:**
1. Violations are logged as warnings
2. A violation summary is appended to the analysis context
3. Claude is re-prompted (up to 2 retries) with the specific violations to fix
4. If still failing after retries, the plan proceeds with warning-level violations logged

**Blog post validation** (in `blog_generator.py`) checks:
- Frontmatter field completeness (10 required fields)
- Pillar value (must be 1-5)
- Post type validity
- Keywords field is a list
- Description length (max 300 chars)
- For recipe posts: Schema.org fields (prepTime, cookTime, totalTime validated as ISO 8601 durations; recipeIngredient and recipeInstructions validated as non-empty lists)
- Word count vs. targets (with 20% tolerance): weekly-plan 1200-1800, recipe 600-800, guide 800-1200, listicle 800-1200
- CTA presence (checks for "slated", "try it free", "dinner draft", "download")

---

## 5. Assumptions About API Wrapper Interfaces

The following assumptions were made about the API wrappers in `src/apis/`. These are based on the skeleton method signatures and docstrings.

### claude_api.ClaudeAPI
- `generate_weekly_plan()` returns a dict with keys `blog_posts` (list of dicts) and `pins` (list of dicts). Each blog post dict has fields matching the weekly plan output format (post_id, pillar, content_type, topic, primary_keyword, secondary_keywords, etc.). Each pin dict has fields matching the pin output format (pin_id, source_post_id, pin_type, pin_template, etc.).
- `generate_pin_copy()` accepts a list of pin specs and returns a list of dicts, one per pin, with keys: title, description, alt_text, text_overlay, subtitle.
- `generate_blog_post()` returns a complete MDX string (frontmatter + body).
- `generate_image_prompt()` returns a string (either a stock search query or an AI image prompt, depending on `image_source` parameter).

### image_stock.ImageStockAPI
- `search()` returns a list of dicts with keys: source, id, preview_url, download_url, width, height, photographer, description.
- `filter_previously_used()` accepts candidate list and used IDs in "source:id" format, returns filtered list.
- `download_image()` saves to the provided path and returns the Path.

### image_gen.ImageGenAPI
- `generate()` saves the generated image to `output_path` and returns the Path.
- Handles retries internally (up to `max_retries`).

### sheets_api.SheetsAPI
- `write_weekly_review()` writes analysis + plan to the Weekly Review tab.
- `write_content_queue()` writes blog posts + pins to the Content Queue tab.
- `read_content_approvals()` returns a list of dicts with keys: id, type ("blog" or "pin"), status, notes.

### github_api.GitHubAPI
- `commit_multiple_posts()` accepts a list of dicts with keys: slug, mdx_content, hero_image_path. Returns commit SHA.
- `commit_blog_post()` accepts slug, mdx_content, optional hero_image_path. Returns commit SHA.
- `verify_deployment()` accepts slug and max_wait_seconds. Returns bool.

### pin_assembler.PinAssembler
- `assemble_pin()` accepts template_type, hero_image_path, headline, subtitle, variant, output_path. Returns Path to rendered PNG.

### slack_notify.SlackNotify
- All notification methods are fire-and-forget. Errors are caught and logged but do not halt the pipeline.

---

## 6. What Needs to Be Tested First

### Priority 1: Content Memory Summary Generation
- Test `generate_content_memory_summary()` with an empty content log (first run)
- Test with a populated content-log.jsonl (seed 4-8 weeks of sample data)
- Verify all 7 sections produce correct aggregations
- Verify untargeted keyword detection works against keyword-lists.json
- Verify fresh pin candidates sort correctly by saves

### Priority 2: Plan Validation
- Test each of the 8 constraint checks individually with known violations
- Test that re-prompting with violations produces different output
- Test edge cases: exactly 28 pins, pillar counts at boundary values, empty content log

### Priority 3: Blog Generator
- Test `_extract_frontmatter()` with real MDX output from Claude
- Test `_generate_slug()` with unicode characters, special characters, long titles
- Test `validate_frontmatter()` and `validate_schema_fields()` with valid and invalid inputs
- Test that each blog post type (recipe, weekly-plan, guide, listicle) routes to the correct prompt template

### Priority 4: Pin Content Generation
- Test `build_utm_link()` with various board names and special characters
- Test `load_used_image_ids()` with a populated content log
- Test the stock image fallback path (all candidates previously used -> fallback to first result)
- Test the AI image fallback when stock search returns empty
- Test batch copy generation with batch failures -> individual fallback

### Priority 5: Blog Deployer
- Test `_build_fallback_approvals()` when Sheets is unavailable
- Test `_create_pin_schedule()` produces correct JSON for post_pins.py
- Test `_append_to_content_log()` writes valid JSONL entries
- Test URL verification retry logic
- Test individual commit fallback when batch commit fails

### Integration Testing
- End-to-end: generate_weekly_plan -> generate_blog_posts -> generate_pin_content -> blog_deployer
- Test with mock API wrappers that return realistic structured data
- Verify data flows correctly between scripts via the JSON files in data/

### Files needed for testing that do not exist yet:
- Sample `data/content-log.jsonl` with 4-8 weeks of entries
- `strategy/current-strategy.md` with actual strategy content (likely a copy of the full strategy doc)
- `strategy/brand-voice.md` with voice guidelines
- Sample `analysis/weekly/` review files
- The API wrapper implementations (currently all raise NotImplementedError)
