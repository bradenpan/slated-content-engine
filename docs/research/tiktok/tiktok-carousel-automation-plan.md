# TikTok Carousel Automation — Implementation Plan

> **Purpose**: Technical implementation plan for coding agents. Content strategy, hooks, and editorial decisions are handled separately by a different agent/process.

---

## 1. System Overview

Build a perpetual content engine that generates, posts, measures, and improves TikTok carousel content continuously. The system runs a loop:

1. **Generate**: Produces 21 carousel specs per week (3/day × 7 days), varying across topics, angles, structures, hooks, slide counts, and visual templates — weighted by past performance data
2. **Render**: Renders multi-slide carousel images (1080×1920 PNGs) via Puppeteer
3. **Approve**: Surfaces all 21 carousels in Google Sheets for a single weekly review session
4. **Post**: Posts 3 approved carousels per day at randomized times across morning, afternoon, and evening slots
5. **Measure**: Pulls performance metrics (saves, shares, swipe-through, completion) from TikTok and maps them back to tagged attributes on each post
6. **Feed back**: Performance data feeds into the next week's generation step, shifting attribute weights toward what works while always exploring new combinations

This is not a batch workflow that converges on a single winning format. It is a continuous engine that always generates, always measures, always adjusts. What works will change over time — the system adapts.

**Reuse target: ~70% from the Pinterest pipeline at `C:\dev\pinterest-pipeline`.**

---

## 2. Reference: Pinterest Pipeline Components

These files in `C:\dev\pinterest-pipeline` are the starting point for reuse/adaptation:

| Component | Pinterest Source | Reuse Level |
|-----------|----------------|-------------|
| Claude API wrapper | `src/apis/claude_api.py` | **Direct reuse** — same module, new prompt files |
| Google Sheets API | `src/apis/sheets_api.py` | **Adapt** — new sheet ID, new column layout |
| Slack notifications | `src/apis/slack_notify.py` | **Adapt** — add TikTok event types |
| Puppeteer renderer | `render_pin.js` | **Adapt** — 1080x1920, multi-slide batch mode |
| Template assembler | `src/pin_assembler.py` | **Adapt** — multi-slide orchestration |
| Image generation | `src/apis/image_gen.py` | **Direct reuse** — same DALL-E/Replicate calls |
| Weekly planning | `src/generate_weekly_plan.py` | **Adapt** — TikTok carousel output schema |
| GCS upload | `src/apis/gcs_api.py` | **Direct reuse** |
| Content log pattern | `data/content-log.jsonl` | **Copy pattern** — new file for TikTok |
| GitHub Actions patterns | `.github/workflows/` | **Copy patterns** — new workflow files |
| Token manager | `src/token_manager.py` | **Reference** — TikTok uses different OAuth flow |
| Apps Script triggers | `src/apps-script/trigger.gs` | **Adapt** — new sheet, new dispatch events |

---

## 3. New Repository Structure

```
tiktok-automation/
├── src/
│   ├── apis/
│   │   ├── claude_api.py          # Copied from Pinterest, shared or symlinked
│   │   ├── tiktok_api.py          # NEW — TikTok Content Posting API wrapper
│   │   ├── sheets_api.py          # Adapted from Pinterest (new sheet config)
│   │   ├── slack_notify.py        # Adapted from Pinterest (TikTok events)
│   │   ├── image_gen.py           # Copied from Pinterest
│   │   └── gcs_api.py             # Copied from Pinterest
│   ├── generate_weekly_plan.py    # Adapted — outputs 21 carousel specs/week with attribute tags
│   ├── compute_attribute_weights.py # NEW — reads performance data, computes topic+structure allocations
│   ├── generate_carousels.py      # NEW — orchestrates full carousel generation
│   ├── carousel_assembler.py      # NEW — multi-slide template rendering
│   ├── post_carousels.py          # NEW — posts 3 carousels/day with randomized timing
│   ├── publish_content_queue.py   # Adapted — uploads to GCS, writes to Sheet
│   └── pull_analytics.py          # NEW — TikTok Display API metrics + attribute performance summary
├── prompts/
│   ├── weekly_plan.md             # Weekly generation prompt (see Section 4.5 for full spec)
│   ├── carousel_content.md        # Slide text + caption generation prompt
│   └── image_prompt.md            # Food/background image prompt (adapt from Pinterest)
├── templates/
│   └── carousels/
│       ├── clean-educational/     # Visual family 1: light bg, bold headlines, numbered
│       │   ├── hook-slide.html
│       │   ├── content-slide.html
│       │   ├── cta-slide.html
│       │   └── styles.css
│       ├── dark-bold/             # Visual family 2: high contrast, dramatic
│       │   ├── hook-slide.html
│       │   ├── content-slide.html
│       │   ├── cta-slide.html
│       │   └── styles.css
│       ├── photo-forward/         # Visual family 3: real photos with text overlay
│       │   ├── hook-slide.html
│       │   ├── content-slide.html
│       │   ├── cta-slide.html
│       │   └── styles.css
│       ├── comparison-grid/       # Visual family 4: split layouts, structured data
│       │   ├── hook-slide.html
│       │   ├── content-slide.html
│       │   ├── cta-slide.html
│       │   └── styles.css
│       └── shared/
│           ├── base-styles.css    # Brand colors, fonts, safe zones
│           └── assets/            # Logo, icons, swipe arrow indicator
├── strategy/                      # Populated by content strategy agent, NOT this pipeline
│   ├── current-strategy.md
│   ├── brand-voice.md
│   ├── keyword-lists.json
│   └── seasonal-calendar.json
├── data/
│   ├── generated/
│   │   └── carousels/             # Output PNGs organized by post ID
│   │       └── {post_id}/
│   │           ├── slide-01.png
│   │           ├── slide-02.png
│   │           └── ...
│   ├── attribute-taxonomy.json    # Full attribute space (topics, angles, structures, etc.)
│   ├── weekly-plan-W##-*.json     # Current week's 21 carousel specs
│   ├── attribute-weights-W##.json # Computed attribute allocations for current week
│   ├── performance-summary.json   # Latest per-attribute performance averages
│   ├── carousel-schedule.json     # Posting schedule (created after approval)
│   ├── content-log.jsonl          # Append-only posting log (includes attribute tags)
│   └── content-memory-summary.md  # Recent content history (avoid repeats)
├── .github/workflows/
│   ├── weekly-generate.yml        # Sunday 8pm: pull analytics → compute weights → generate 21 specs → render → Sheet
│   ├── promote-and-schedule.yml   # Triggered by content approval (batch of 21)
│   ├── daily-post.yml             # 3x/day every day: post from approved weekly batch
│   └── weekly-analysis.yml        # Sunday 7pm: pull analytics, compute performance summary
├── render_carousel.js             # Node.js Puppeteer renderer (multi-slide)
├── apps-script/
│   └── trigger.gs                 # Google Sheets → GitHub Actions triggers
├── package.json
├── requirements.txt
├── .env.example
└── CLAUDE.md
```

---

## 4. Component Specifications

### 4.1 `render_carousel.js` — Puppeteer Multi-Slide Renderer

**Adapts**: `pinterest-pipeline/render_pin.js`

**Key changes from Pinterest renderer**:
- Output dimensions: **1080 x 1920** (was 1000x1500)
- Accepts a **manifest of multiple slides** per carousel (not just one image)
- Returns array of PNG paths per carousel

**Interface**:
```bash
# Single slide
node render_carousel.js --html-file slide.html --output slide-01.png --width 1080 --height 1920

# Batch (primary mode) — renders all slides for one or more carousels
node render_carousel.js --manifest manifest.json
```

**Manifest format**:
```json
[
  {
    "carousel_id": "W12-01",
    "slides": [
      {"html_file": "/tmp/W12-01-slide-01.html", "output": "data/generated/carousels/W12-01/slide-01.png"},
      {"html_file": "/tmp/W12-01-slide-02.html", "output": "data/generated/carousels/W12-01/slide-02.png"}
    ]
  }
]
```

**Output**: JSON to stdout
```json
{"ok": true, "rendered": [{"carousel_id": "W12-01", "slides": ["slide-01.png", "slide-02.png", ...]}]}
```

**Puppeteer config**: Same as Pinterest — `--no-sandbox --disable-dev-shm-usage` for GitHub Actions headless.

---

### 4.2 `carousel_assembler.py` — Template Engine

**Adapts**: `pinterest-pipeline/src/pin_assembler.py`

**Key changes from Pinterest**:
- Handles **multiple slide types** per carousel (hook → content × N → CTA)
- Each slide type has its own HTML/CSS template
- Injects variables per slide, then calls `render_carousel.js` in batch mode

**Class interface**:
```python
class CarouselAssembler:
    def __init__(self, templates_dir: str = "templates/carousels"):
        ...

    def assemble_carousel(self, carousel_spec: dict) -> list[str]:
        """
        Takes a carousel spec, renders all slides, returns list of PNG paths.

        carousel_spec = {
            "carousel_id": "W12-01",
            "slides": [
                {
                    "type": "hook",          # template to use
                    "headline": "...",
                    "background_image": "base64 or file path",
                    "variables": {}          # additional template-specific vars
                },
                {
                    "type": "content",
                    "headline": "...",
                    "body_text": "...",
                    "background_image": "...",  # or null for solid bg
                    "slide_number": 2,
                    "total_slides": 8,
                    "variables": {}
                },
                {
                    "type": "cta",
                    "handle": "@slated",
                    "cta_text": "...",
                    "variables": {}
                }
            ]
        }
        """
        # 1. For each slide: load template HTML, inject variables, inline CSS
        # 2. Write temp HTML files
        # 3. Build manifest JSON
        # 4. Call render_carousel.js subprocess
        # 5. Validate PNGs exist and meet minimum size (10KB)
        # 6. Return list of PNG paths
```

**Template variable injection**: Same pattern as Pinterest `pin_assembler.py` — `{{variable_name}}` replacement + CSS inlining from `shared/base-styles.css` + slide-specific `styles.css`.

---

### 4.3 `templates/carousels/` — HTML/CSS Slide Templates

**Dimensions**: 1080 x 1920px (9:16 vertical)

**Safe zones** (avoid TikTok UI overlap):
- Top: 100px
- Left/Right: 60px
- Bottom: 280px (caption + buttons overlay)

**4 visual template families** (minimum to sustain 21 posts/week without template fatigue):

Each family has 3 slide types (hook, content, CTA) with its own color scheme, typography, and layout. The `carousel_assembler.py` receives the `visual_template` attribute from the carousel spec and selects the correct family.

#### Family 1: `clean-educational/`
- Light background, bold dark headlines, numbered slides
- Best for: listicles, tutorials, data-driven content
- Text-dominant (60-70% text)

#### Family 2: `dark-bold/`
- Dark background, high-contrast white/accent text, dramatic feel
- Best for: contrarian takes, bold claims, transformations
- Text-dominant with accent colors

#### Family 3: `photo-forward/`
- Real photos with semi-transparent overlay and text overlay
- Best for: lifestyle, story arcs, before/after
- Image-dominant (70% image)

#### Family 4: `comparison-grid/`
- Split layouts, side-by-side panels, structured data presentation
- Best for: comparisons, do's/don'ts, data dumps
- Balanced text/image

**Each family's slide types share the same variable interface**:

**hook-slide.html**: `{{headline}}`, `{{subtitle}}`, `{{background_image}}`, `{{overlay_opacity}}`
**content-slide.html**: `{{headline}}`, `{{body_text}}`, `{{background_image}}`, `{{background_color}}`, `{{background_type}}`, `{{slide_number}}`, `{{total_slides}}`
**cta-slide.html**: `{{primary_cta}}`, `{{secondary_cta}}`, `{{handle}}`, `{{logo_path}}`

This shared interface means the assembler can swap visual families without changing any generation logic.

**Refresh cycle**: Plan to add 1-2 new families or refresh existing ones every 4-6 weeks to prevent long-term visual staleness.

#### `shared/base-styles.css`
- Font imports (choose 1-2 fonts — suggest system fonts or Google Fonts that render in Puppeteer)
- Brand color variables (CSS custom properties)
- Safe zone padding rules
- Swipe arrow component styles
- Text shadow/outline for readability over images

---

### 4.4 `tiktok_api.py` — TikTok Content Posting API Wrapper

**New build**. Reference TikTok's Content Posting API docs.

**TikTok photo publish flow** (3-step):
1. `POST /v2/post/publish/creator_info/query/` — Check user's posting permissions
2. `POST /v2/post/publish/content/init/` — Initialize photo post, upload images
3. Poll `GET /v2/post/publish/status/fetch/` — Check publish status

**Class interface**:
```python
class TikTokAPI:
    def __init__(self, access_token: str):
        self.base_url = "https://open.tiktokapis.com"
        self.access_token = access_token

    def check_creator_info(self) -> dict:
        """Query creator's posting permissions and privacy options."""

    def publish_carousel(self, image_paths: list[str], caption: str,
                         privacy_level: str = "PUBLIC_TO_EVERYONE",
                         disable_comment: bool = False,
                         disable_duet: bool = False,
                         disable_stitch: bool = False) -> dict:
        """
        Publish a photo carousel post.

        1. Read image files, encode as needed
        2. Call content/init with photo_images and post_info
        3. Poll status/fetch until complete or failed
        4. Return publish_id and status

        TikTok requires:
        - Images as URLs (must upload to GCS first and provide public URLs)
        - OR direct upload via their upload endpoint
        - Min 2 images, max 35 images per carousel
        - Each image max 20MB
        """

    def get_publish_status(self, publish_id: str) -> dict:
        """Poll publish status. Returns PROCESSING, PUBLISH_COMPLETE, or FAILED."""

    def get_video_list(self, fields: list[str], max_count: int = 20) -> dict:
        """Fetch recent posts for analytics (TikTok Display API)."""
```

**OAuth**: TikTok uses OAuth 2.0 with authorization code flow. Token refresh is similar to Pinterest but different endpoint. Implement token refresh in this module or a separate `tiktok_token_manager.py`.

**Manual upload fallback**: When `TIKTOK_API_ENABLED=false` in env, `post_carousels.py` skips API calls, instead logs "MANUAL_UPLOAD_REQUIRED" to the content log and sends Slack notification with GCS download links.

---

### 4.5 `generate_weekly_plan.py` — Weekly Content Generation

**Adapts**: `pinterest-pipeline/src/generate_weekly_plan.py`

**Key changes from Pinterest**:
- Outputs **21 carousel specs per week** (3/day × 7 days) instead of 5
- Each spec is tagged with **attributes** (topic, angle, structure, hook_type, slide_count, visual_template) for the feedback loop
- Topic and structure are **pre-allocated by Python code** based on performance data before the Claude prompt runs
- Angle, hook type, slide count, and visual template are **chosen by Claude** within the prompt, informed by performance data
- Reads performance summary from `pull_analytics.py` output

#### Pre-prompt: Attribute Allocation (`compute_attribute_weights.py`)

This runs BEFORE the Claude call. Deterministic Python code — no LLM involved.

**Inputs**:
- `data/performance-summary.json` (output of `pull_analytics.py`)
- `data/attribute-taxonomy.json` (full attribute space)

**Logic**:
```python
# Pseudocode
def compute_allocations(performance_data, taxonomy, total_posts=21):
    """
    Allocates topic and structure for each of the 21 weekly slots.
    ~65% exploit (weighted toward high-performing attributes)
    ~35% explore (underrepresented, untested, or new attributes)
    Minimum 1 post per attribute value — nothing ever goes to zero.
    """
    exploit_count = int(total_posts * 0.65)  # ~14 posts
    explore_count = total_posts - exploit_count  # ~7 posts

    # EXPLOIT: distribute 14 slots proportional to save_rate performance
    # Higher-performing topics/structures get more slots
    exploit_slots = allocate_proportional(
        taxonomy["topics"], taxonomy["structures"],
        performance_data, count=exploit_count
    )

    # EXPLORE: distribute 7 slots to underrepresented combinations
    # Prioritize: untested combos > low-sample combos > new taxonomy entries
    explore_slots = allocate_exploration(
        taxonomy["topics"], taxonomy["structures"],
        performance_data, count=explore_count
    )

    return exploit_slots + explore_slots  # list of 21 {topic, structure, is_explore} dicts
```

**Output** (`data/attribute-weights-W##.json`):
```json
{
  "week_number": 12,
  "slots": [
    {"slot": 1, "topic": "grocery_savings", "structure": "listicle", "is_explore": false},
    {"slot": 2, "topic": "grocery_savings", "structure": "tutorial", "is_explore": false},
    {"slot": 19, "topic": "seasonal_grilling", "structure": "listicle", "is_explore": true},
    ...
  ]
}
```

Why topic and structure are pre-allocated in Python: these are the highest-impact variables (determine 60-70% of performance). You want tight, deterministic control and debuggability. If the system produces weird output, you can inspect the allocations separately from Claude's content generation.

Why angle, hook type, slide count, and visual template are left to Claude: these benefit from creative judgment about what combinations make sense for specific content. Claude sees the performance data and can make informed choices.

#### Claude Prompt Structure (`prompts/weekly_plan.md`)

The prompt has 6 sections:

**Section 1 — Role and output spec:**
Instructs Claude to generate 21 carousel specs, defines the output JSON schema including attribute tags.

**Section 2 — Attribute taxonomy:**
The full set of available values for each dimension, injected from `data/attribute-taxonomy.json`:
- Topics (from taxonomy)
- Angles: contrarian, transformation, social_proof, problem_solution, comparison, lifestyle, data_driven
- Structures: listicle, tutorial, comparison, story_arc, problem_solution, before_after, data_dump
- Hook types: curiosity_gap, bold_claim, relatable_problem, proof_first, question, shocking_stat, mistake
- Slide counts: 3, 5, 7, 8, 10
- Visual templates: clean_educational, dark_bold, photo_forward, comparison_grid

**Section 3 — Pre-computed allocations:**
The 21 topic+structure slots from `compute_attribute_weights.py`. Claude generates one carousel for each slot, choosing the remaining attributes (angle, hook type, slide count, visual template) itself.

Example:
```
Slot 1: topic=grocery_savings, structure=listicle
Slot 2: topic=grocery_savings, structure=tutorial
...
Slot 19: topic=seasonal_grilling, structure=listicle  (EXPLORE)
Slot 20: topic=kitchen_hacks, structure=story_arc  (EXPLORE)
Slot 21: topic=pantry_staples, structure=tutorial  (EXPLORE)
```

**Section 4 — Performance data:**
Raw performance summaries so Claude can make informed decisions on the attributes it controls. Includes:
- Save rate and share rate by attribute value (topic, structure, angle, hook type, slide count, visual template)
- Swipe-through rate by hook type
- Top 5 and bottom 5 posts from the last 4 weeks with full attribute breakdowns
- Injected from `data/performance-summary.json`

**Section 5 — Content constraints:**
- Follow brand voice guide exactly
- Do not repeat any topic+angle combination from the last 2 weeks (reads content memory)
- Every carousel must have genuinely different specific content — different tips, examples, data points
- Variety enforcement: no hook type more than 4× across all 21, no visual template more than 5×, at least 3 short carousels (3-5 slides) and 3 long (8-10 slides)
- For EXPLORE slots: try untested attribute combinations

**Section 6 — Cold start handling:**
When `total_posts < 30` (roughly first 2 weeks), skip performance weighting. Distribute evenly across all available attributes. The goal is generating data across the full attribute space, not optimizing yet.

#### Output Schema (`data/weekly-plan-W##-YYYY-MM-DD.json`)

```json
{
  "week_number": 12,
  "week_start": "2026-03-02",
  "total_posts_to_date": 147,
  "carousels": [
    {
      "carousel_id": "W12-01",
      "slot": 1,
      "scheduled_date": "2026-03-02",
      "scheduled_slot": "morning",
      "attributes": {
        "topic": "grocery_savings",
        "angle": "contrarian",
        "structure": "listicle",
        "hook_type": "curiosity_gap",
        "slide_count": 7,
        "visual_template": "clean_educational",
        "is_explore": false
      },
      "caption": "...",
      "hashtags": ["#mealprep", "#dinnerideas"],
      "slides": [
        {"type": "hook", "headline": "...", "subtitle": "..."},
        {"type": "content", "headline": "...", "body_text": "..."},
        {"type": "cta", "primary_cta": "...", "secondary_cta": "..."}
      ],
      "image_prompts": [
        {"slide_index": 0, "prompt": "..."},
        {"slide_index": 2, "prompt": "..."}
      ]
    }
  ]
}
```

**Claude call structure**: Load prompt template → inject attribute allocations, performance summary, taxonomy, brand voice, content memory → request structured JSON → parse and validate 21 specs → write weekly plan file.

---

### 4.6 `generate_carousels.py` — Full Carousel Generation Orchestrator

**Adapts**: `pinterest-pipeline/src/generate_pin_content.py`

**Flow for each carousel in the approved plan**:
1. Read carousel spec from `weekly-plan-W##-*.json`
2. Select visual template family based on `attributes.visual_template`
3. Generate hero images via `image_gen.py` for slides that need them (based on `image_prompts`)
4. Build `carousel_spec` dict with image data + template family injected
5. Call `carousel_assembler.assemble_carousel()` → get list of PNG paths
6. Upload PNGs to GCS via `gcs_api.py`
7. Write row to Google Sheet Content Queue with IMAGE() thumbnail formulas and attribute tags
8. Repeat for all 21 carousels
9. Send Slack notification: "21 carousels ready for review"

---

### 4.7 `post_carousels.py` — Daily Posting (3x/day)

**Adapts**: `pinterest-pipeline/src/post_pins.py`

**Key changes**:
- Posts **3 carousels per day, 7 days per week** (not 1/day Mon-Fri)
- Three time slots: morning (~10-11 AM), afternoon (~4-5 PM), evening (~7-8 PM)
- Each slot randomized by +/- 30-60 minutes daily to avoid bot detection patterns
- Uses TikTok API or manual-upload fallback

**Flow** (runs once per scheduled slot):
1. Read `carousel-schedule.json` for today's slot (morning/afternoon/evening)
2. Check `content-log.jsonl` for idempotency (skip if this slot already posted today)
3. If `TIKTOK_API_ENABLED=true`:
   - Read slide PNGs from GCS URLs
   - Call `tiktok_api.publish_carousel()`
   - Poll until `PUBLISH_COMPLETE` or `FAILED`
4. If `TIKTOK_API_ENABLED=false`:
   - Log `MANUAL_UPLOAD_REQUIRED`
   - Slack: "Manual upload needed — [GCS links to slides]"
5. Update Google Sheet Post Log (include all attribute tags from the carousel spec)
6. Append to `content-log.jsonl` (include attribute tags)
7. Slack: "Posted carousel: [title] [slot]" or "FAILED: [error]"

**Anti-bot jitter**: Each slot's target time is randomized by +/- 30-60 minutes from the base time. Additionally, a random 0-120 second delay is added before the actual API call. The gap between morning and afternoon varies between 5-7 hours; afternoon to evening varies between 2-4 hours. No two days should have identical posting times.

**Schedule assignment**: When 21 carousels are approved, `promote-and-schedule.yml` distributes them across 7 days × 3 slots. Assignment can be random or follow heuristics (e.g., explore posts get evening slots where audience is largest for fairer testing).

---

### 4.8 Google Sheet Structure

**New Google Sheet** (separate from Pinterest).

**Tab 1: Weekly Review**
| Column | Content |
|--------|---------|
| A | Week number |
| B | Status: `pending_review` / `approved` / `rejected` |
| C | Plan summary (auto-filled — 21 carousel titles + attribute breakdown) |
| D | Exploit/explore split summary |
| E | Feedback (human writes if rejecting) |

**Tab 2: Content Queue**
| Column | Content |
|--------|---------|
| A | Carousel ID (e.g., W12-01) |
| B | Scheduled date |
| C | Scheduled slot (morning/afternoon/evening) |
| D | Topic |
| E | Angle |
| F | Structure |
| G | Hook type |
| H | Slide count |
| I | Visual template |
| J | Explore? (TRUE/FALSE) |
| K | Caption text |
| L | Thumbnail (IMAGE() formula → GCS URL of slide 1) |
| M | All slides link (GCS folder URL) |
| N | Status: `pending_review` / `approved` / `rejected` |
| O | Feedback |

**Tab 3: Post Log**
| Column | Content |
|--------|---------|
| A | Carousel ID |
| B | Date posted |
| C | Time slot |
| D | TikTok post ID (or "MANUAL") |
| E | Status: `posted` / `failed` / `manual_upload_required` |
| F | Error message (if failed) |
| G-L | Attribute tags (topic, angle, structure, hook_type, slide_count, visual_template) |

**Tab 4: Performance Data** (populated by `pull_analytics.py`)
| Column | Content |
|--------|---------|
| A | Carousel ID (links to Post Log) |
| B | Views |
| C | Saves |
| D | Shares |
| E | Comments |
| F | Save rate (saves/views) |
| G | Share rate (shares/views) |
| H-M | Attribute tags (copied from Post Log for easy filtering/pivoting) |
| N | Explore? |
| O | Days since posted |

This tab is the raw data source for the feedback loop. `pull_analytics.py` reads it, computes per-attribute averages, and writes `data/performance-summary.json`.

**Apps Script trigger**: Same pattern as Pinterest — watch status cell changes, fire `repository_dispatch` to GitHub Actions.

---

### 4.9 GitHub Actions Workflows

**4 workflows**:

#### `weekly-analysis.yml`
- **Trigger**: Cron Sunday 7pm ET
- **Steps**:
  1. `pull_analytics.py` — pull TikTok Display API metrics for all posts from last 7+ days
  2. Join metrics with attribute tags from Post Log
  3. Compute per-attribute performance averages (save rate, share rate, swipe-through by topic, angle, structure, hook type, slide count, visual template)
  4. Write `data/performance-summary.json`
  5. Update `content-memory-summary.md` with last 2 weeks of posted content
  6. Slack: weekly performance summary (top/bottom performers, attribute trends)
- **Concurrency**: single group `tiktok-analysis`

#### `weekly-generate.yml`
- **Trigger**: Cron Sunday 8pm ET (runs after `weekly-analysis.yml` completes)
- **Steps**:
  1. `compute_attribute_weights.py` — read performance summary + taxonomy → compute 21 topic+structure allocations → write `data/attribute-weights-W##.json`
  2. `generate_weekly_plan.py` — build Claude prompt with allocations + performance data + brand voice + content memory → generate 21 carousel specs → write weekly plan JSON
  3. `generate_carousels.py` — render all 21 carousels (image gen → Puppeteer → PNGs)
  4. `publish_content_queue.py` — upload to GCS, write all 21 rows to Content Queue sheet
  5. Slack: "21 carousels ready for Monday morning review"
- **Concurrency**: single group `tiktok-generate`

#### `promote-and-schedule.yml`
- **Trigger**: `repository_dispatch` type `tiktok-content-approved`
- **Steps**:
  1. Read approved carousels from Content Queue (status = `approved`)
  2. Distribute across 7 days × 3 slots with randomized times
  3. Write `carousel-schedule.json`
  4. Slack: "21 carousels scheduled for the week"
- **Concurrency**: single group `tiktok-promote`

#### `daily-post.yml`
- **Trigger**: 3 cron triggers daily, every day:
  - `cron: '0 15 * * *'` (10am ET — morning slot)
  - `cron: '0 21 * * *'` (4pm ET — afternoon slot)
  - `cron: '0 0 * * *'` (7pm ET — evening slot)
- **Steps**: `post_carousels.py` with slot parameter → post → update Sheet + log with attribute tags → Slack
- **Note**: `post_carousels.py` adds its own random jitter (+/- 30-60 min) on top of the cron trigger, so actual post times vary daily. GitHub Actions cron is the outer trigger; the script handles fine-grained timing.
- **Concurrency**: single group `tiktok-post`

---

### 4.10 `pull_analytics.py` — Performance Data & Feedback Loop

**New build**. This is the spine of the feedback loop — without it, the generation system is flying blind.

**Runs**: Sunday 7pm ET via `weekly-analysis.yml`, before weekly generation.

**Flow**:
1. Call TikTok Display API `get_video_list()` for all posts from the last 7+ days
2. For each post, pull: views, saves, shares, comments
3. Read Post Log from Google Sheet to get attribute tags for each post
4. Join metrics with attribute tags
5. Write raw per-post data to Performance Data tab (Tab 4) in the Sheet
6. Compute per-attribute performance averages:
   - Save rate by topic, angle, structure, hook type, slide count, visual template
   - Share rate by same dimensions
   - Swipe-through rate by hook type (if available from API)
   - Include sample sizes (number of posts per attribute value)
7. Identify top 5 and bottom 5 posts (by save rate) with full attribute breakdowns
8. Write `data/performance-summary.json`:

```json
{
  "generated_at": "2026-03-15T19:00:00Z",
  "total_posts_analyzed": 147,
  "window_weeks": 4,
  "by_attribute": {
    "topic": {
      "grocery_savings": {"save_rate": 0.032, "share_rate": 0.018, "posts": 47},
      "meal_prep": {"save_rate": 0.021, "share_rate": 0.012, "posts": 38}
    },
    "structure": {
      "listicle": {"save_rate": 0.029, "posts": 52},
      "tutorial": {"save_rate": 0.023, "posts": 31}
    },
    "angle": { ... },
    "hook_type": { ... },
    "slide_count": { ... },
    "visual_template": { ... }
  },
  "top_posts": [
    {"carousel_id": "W10-02", "save_rate": 0.081, "attributes": {...}}
  ],
  "bottom_posts": [
    {"carousel_id": "W09-15", "save_rate": 0.004, "attributes": {...}}
  ]
}
```

9. Update `content-memory-summary.md` with last 2 weeks of posted topics+angles (for dedup in generation prompt)
10. Slack: weekly summary with top/bottom performers and attribute trend changes

**Lookback window**: Performance averages use the last 4 weeks of data (rolling window), not all-time. This ensures the system adapts to shifts in what works rather than being anchored to early data.

**TikTok Display API note**: Requires separate API access from Content Posting API. Apply for both. If Display API is not available initially, manual entry of metrics into the Performance Data tab is a viable interim approach.

---

### 4.11 `data/attribute-taxonomy.json` — Attribute Space Definition

Defines the full set of attribute values the generation system can draw from. Grows over time as you add new topics, angles, or visual templates.

```json
{
  "topics": [
    "grocery_savings",
    "meal_prep",
    "kitchen_hacks",
    "budget_meals",
    "seasonal_recipes"
  ],
  "angles": [
    "contrarian",
    "transformation",
    "social_proof",
    "problem_solution",
    "comparison",
    "lifestyle",
    "data_driven"
  ],
  "structures": [
    "listicle",
    "tutorial",
    "comparison",
    "story_arc",
    "problem_solution",
    "before_after",
    "data_dump"
  ],
  "hook_types": [
    "curiosity_gap",
    "bold_claim",
    "relatable_problem",
    "proof_first",
    "question",
    "shocking_stat",
    "mistake"
  ],
  "slide_counts": [3, 5, 7, 8, 10],
  "visual_templates": [
    "clean_educational",
    "dark_bold",
    "photo_forward",
    "comparison_grid"
  ]
}
```

**Maintenance**: Add new entries as you identify adjacent topics, develop new visual templates, or discover new structural patterns that work. Never remove entries — just let the weighting system naturally deprioritize underperformers. The explore allocation ensures every value gets tested periodically.

---

### 4.12 Environment Variables

```bash
# TikTok API
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_ACCESS_TOKEN=
TIKTOK_REFRESH_TOKEN=
TIKTOK_API_ENABLED=false          # Set to true once API access approved

# Claude (shared with Pinterest)
ANTHROPIC_API_KEY=

# Image Generation (shared with Pinterest)
OPENAI_API_KEY=
REPLICATE_API_TOKEN=
IMAGE_GEN_PROVIDER=openai

# Google Services
GOOGLE_SHEETS_CREDENTIALS_JSON=   # base64-encoded service account
TIKTOK_GOOGLE_SHEET_ID=           # Separate sheet from Pinterest
TIKTOK_GOOGLE_SHEET_URL=

# GCS (shared with Pinterest)
GCS_BUCKET=

# Slack (shared with Pinterest)
SLACK_WEBHOOK_URL=
```

---

## 5. Dependencies

### Python (`requirements.txt`)
```
anthropic>=0.40.0
requests>=2.31.0
Pillow>=10.0.0
google-api-python-client>=2.90.0
google-auth>=2.22.0
google-cloud-storage>=2.10.0
numpy>=1.24.0
```

### Node.js (`package.json`)
```json
{
  "dependencies": {
    "puppeteer": "^24.37.5"
  }
}
```

Same as Pinterest — no new dependencies needed.

---

## 6. Build Sequence

Implementation should proceed in this order (dependencies are sequential):

### Phase 1: Rendering Engine (no external APIs needed)

1. **Create carousel HTML/CSS templates** — all 4 visual families (`templates/carousels/`)
   - `clean-educational/`, `dark-bold/`, `photo-forward/`, `comparison-grid/`, `shared/`
   - Each family: hook-slide, content-slide, cta-slide with shared variable interface
   - Test with hardcoded data in a browser first
2. **Build `render_carousel.js`** — adapt from Pinterest `render_pin.js`
   - Update to 1080x1920, add manifest-based multi-slide batch mode
3. **Build `carousel_assembler.py`** — adapt from Pinterest `pin_assembler.py`
   - Template family selection based on `visual_template` attribute
   - Template loading, variable injection, CSS inlining, subprocess call
   - Write tests with sample carousel specs across all 4 families
4. **Validate end-to-end**: hardcoded carousel spec → rendered PNGs for each family

### Phase 2: Content Generation Pipeline

5. **Create `data/attribute-taxonomy.json`** — initial attribute space
6. **Write Claude prompt template** (`prompts/weekly_plan.md`)
   - Full 6-section prompt structure (see Section 4.5)
   - Cold start handling for weeks with no performance data
7. **Build `compute_attribute_weights.py`** — reads performance data + taxonomy, outputs 21 topic+structure allocations
   - Include cold-start mode (even distribution when no data)
8. **Build `generate_weekly_plan.py`** — adapt from Pinterest
   - Load allocations, performance summary, brand voice, content memory
   - Build prompt, call Claude, parse 21 carousel specs with attribute tags
9. **Write additional prompts** (`prompts/`)
   - `carousel_content.md` — slide text + caption generation
   - `image_prompt.md` — food photography prompts (adapt from Pinterest)
10. **Build `generate_carousels.py`** — new orchestrator
    - Image gen → carousel assembly (with visual template selection) → GCS upload → Sheet write
    - Handle 21 carousels per batch
11. **Set up Google Sheet** — create sheet, configure all 4 tabs with attribute columns
12. **Build `publish_content_queue.py`** — adapt from Pinterest
    - Write 21 carousel rows with IMAGE() thumbnails + attribute tags to Content Queue tab
13. **Write Apps Script trigger** — adapt from Pinterest
    - Watch approval cells → `repository_dispatch`

### Phase 3: Posting & Feedback Loop

14. **Build `tiktok_api.py`** — TikTok Content Posting API wrapper
    - Start with manual-upload fallback mode
    - Add real API integration when access is approved
15. **Build `post_carousels.py`** — 3x/day posting script
    - 3 time slots with randomized jitter, 7 days/week
    - Schedule reading, idempotency, API or manual fallback
    - Attribute tag logging on every post
16. **Build `pull_analytics.py`** — TikTok Display API integration
    - Pull metrics, join with attribute tags, compute per-attribute averages
    - Write `data/performance-summary.json`
    - Update content memory
    - If Display API not available: build manual-entry mode via Sheet
17. **Create GitHub Actions workflows** (all 4)
18. **Adapt `slack_notify.py`** — add TikTok event types, weekly performance summary
19. **Create `content-log.jsonl`** structure with attribute tag fields

### Phase 4: Go Live

20. **Apply for TikTok Content Posting API + Display API** (can start this in parallel with Phase 1)
21. **Set up TikTok Business Account** (for immediate bio link)
22. **Generate first week of 21 carousels** through the full pipeline (cold start mode — even attribute distribution)
23. **Start posting** 3x/day (manual upload initially)
24. **Wire up automated posting** once API approved
25. **First feedback loop cycle** — after week 2, `pull_analytics.py` has enough data to start weighting. Review the performance summary and attribute weights before week 3's generation runs.

---

## 7. Monthly Cost Estimate

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| Claude API (Sonnet) | $12-20 | 21 specs generated in one batch prompt/week + weekly analysis prompt. Shared key with Pinterest. |
| DALL-E image generation | $5-12 | ~1-2 generated images per carousel (hook slides + select content slides). Most slides are text-on-background and don't need image gen. |
| Google Cloud Storage | $2-4 | ~840 carousel PNGs/month (~500KB each, 21 carousels × ~5 slides × 4 weeks) |
| GitHub Actions | $3-8 | 21 daily posting runs + weekly generation + analytics. May exceed free tier. |
| Linktree | $0 | Free tier |
| Google Sheets | $0 | Free |
| Slack | $0 | Free tier webhook |
| **Total** | **$22-44/mo** | |

**Comparison to previous plan**: $9-23/mo at 5 posts/week → $22-44/mo at 21 posts/week. ~4x the content for ~2x the cost. Image gen does not scale linearly because most carousel slides use template graphics, not generated photography.

Optional future additions:
- Video pipeline (ElevenLabs + Epidemic Sound + Creatomate): +$125-180/mo
- Comment automation (NapoleonCat): +$31/mo

---

## 8. Open Items Requiring Human Decision Before Build

1. **TikTok account handle** — needed for CTA slide templates
2. **Brand colors + fonts** — needed for `shared/base-styles.css` across all 4 visual families (can pull from existing Slated brand if available)
3. **App logo asset** — needed for CTA slide template
4. **Link-in-bio URL** — what URL goes in the TikTok bio
5. **Strategy docs** — `strategy/` directory needs to be populated by the content strategy agent before the planning step can run
6. **Initial attribute taxonomy** — the starter set of topics for `data/attribute-taxonomy.json`. Angles, structures, hook types, and visual templates have sensible defaults; topics are niche-specific and need to be defined.
7. **TikTok Display API access** — needed for `pull_analytics.py` to close the feedback loop. Separate application from Content Posting API. If not available initially, manual metric entry via Sheet is the interim approach.
8. **Post-publish engagement capacity** — 3 posts/day = ~5 hrs/week of engagement windows. Confirm this is manageable or plan for partial coverage (e.g., only engage on morning + evening slots, skip afternoon).
