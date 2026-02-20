# API Integration Layer Implementation Report

**Date:** 2026-02-20
**Scope:** Full implementation of 8 API integration modules for the Pinterest automation pipeline

---

## 1. What Was Implemented

### src/token_manager.py — Pinterest OAuth Token Manager
- **TokenManager class** with full 60-day continuous refresh token support (NOT legacy 365-day tokens)
- `get_valid_token()` — main entry point, checks expiry and auto-refreshes if within 5-day threshold
- `needs_refresh()` — checks access token expiry against configurable threshold (5 days)
- `refresh_token()` — calls POST /v5/oauth/token with grant_type=refresh_token, stores both new access and refresh tokens
- `initial_auth(authorization_code)` — one-time exchange of auth code for tokens, includes `continuous_refresh=true`
- Token storage: reads from `data/token-store.json` first, falls back to env vars
- On refresh failure: sends Slack alert via lazy-loaded SlackNotify (avoids circular import)
- CLI support: `python -m src.token_manager` for check/refresh, `python -m src.token_manager auth <CODE>` for initial auth
- Refresh token expiry check: warns and fails early if the 60-day refresh window has lapsed

### src/apis/pinterest_api.py — Pinterest v5 API Wrapper
- **PinterestAPI class** with full CRUD operations
- `create_pin()` — POST /v5/pins, supports both image_url and image_base64 media sources, enforces title/description length limits
- `get_pin()` — GET /v5/pins/{pin_id}
- `delete_pin()` — DELETE /v5/pins/{pin_id}
- `list_boards()` / `get_boards()` — GET /v5/boards with full pagination via bookmark
- `create_board()` — POST /v5/boards with name, description, privacy
- `create_board_section()` — POST /v5/boards/{board_id}/sections
- `get_pin_analytics()` — GET /v5/pins/{pin_id}/analytics with date range, granularity, metric types
- `get_account_analytics()` — GET /v5/user_account/analytics
- **Rate limit handling:** reads X-RateLimit-Limit/Remaining/Reset headers, logs warnings at <20%, sleeps and retries on 429 using reset header or exponential backoff
- **Error handling:** descriptive PinterestAPIError exceptions for 401 (auth), 403 (forbidden), 404 (not found), 429 (rate limit), 5xx (server errors)
- **Retry logic:** up to 3 retries with exponential backoff for 429 and 5xx errors
- **Environment switching:** PINTEREST_ENV=sandbox uses api-sandbox.pinterest.com, production (default) uses api.pinterest.com

### src/apis/claude_api.py — Claude API Wrapper
- **ClaudeAPI class** wrapping the Anthropic Python SDK
- `load_prompt_template(name)` — loads .md files from prompts/ directory
- `_render_template(template, context)` — injects {{VARIABLE}} placeholders from context dict
- `generate_weekly_plan()` — Sonnet, accepts strategy doc + analysis + content memory + seasonal + keyword data + negative keywords, returns structured JSON
- `generate_pin_copy()` — Sonnet, batches 5-7 pins per call, returns title/description/alt_text/text_overlay per pin
- `generate_blog_post()` — Sonnet, routes to type-specific prompt template (recipe/weekly-plan/guide/listicle), returns complete MDX
- `generate_image_prompt()` — Sonnet, generates AI prompts or stock search queries
- `generate_image_search_query()` — convenience wrapper for stock photo queries
- `analyze_weekly_performance()` / `generate_weekly_analysis()` — Sonnet, weekly analytics
- `run_monthly_review()` / `generate_monthly_review()` — **Opus** for deeper reasoning
- **Model routing:** claude-sonnet-4-20250514 for routine, claude-opus-4-20250514 for monthly reviews
- **Token/cost tracking:** logs input/output token counts per call, tracks cumulative session cost in USD
- **JSON parsing:** strips markdown code fences from responses before parsing
- **Retry on rate limits:** 3 retries with progressive backoff (10s, 20s, 40s)

### src/apis/image_stock.py — Unsplash + Pexels Wrapper
- **ImageStockAPI class** with unified interface across both providers
- `search_images(query, source, count)` — public interface matching requirement spec
- `search(query, num_results, orientation, sources)` — full search with fallback logic
- `_search_unsplash()` — GET /search/photos with orientation=portrait, returns standardized result dicts
- `_search_pexels()` — GET /v1/search with orientation=portrait, returns standardized result dicts
- **Fallback logic:** if primary source returns no results, automatically tries the other
- `download_image(image, output_path, width)` — downloads at specified width, Unsplash width parameter appended
- `filter_previously_used(candidates, used_image_ids)` — accepts "source:id" format strings, filters exact matches
- **Rate limit tracking:** reads X-Ratelimit-Remaining headers from both APIs, logs warnings when low
- Standardized return format: source, id, url, thumbnail_url, preview_url, download_url, width, height, photographer, description

### src/apis/image_gen.py — DALL-E / Flux Pro Wrapper
- **ImageGenAPI class** supporting OpenAI gpt-image-1 and Replicate Flux Pro
- `generate_image(prompt, provider, size)` — public interface matching requirement spec, returns dict with path/provider/cost
- `generate(prompt, width, height, output_path, style, max_retries)` — full generation with retry
- `get_image_status(job_id)` — polls Replicate async predictions
- `_generate_openai()` — calls gpt-image-1, handles both b64_json and URL responses, maps dimensions to supported sizes (1024x1024, 1024x1536, 1536x1024)
- `_generate_replicate()` — creates prediction, polls for completion with timeout, downloads result
- **Retry logic:** up to 2 retries with slight prompt modification (adds composition modifiers)
- **Quality validation:** checks minimum file size (10KB), Pillow-based format/dimension verification with 10% tolerance
- **Cost tracking:** per-image and session cumulative cost
- Provider selection via IMAGE_GEN_PROVIDER env var with constructor override

### src/apis/sheets_api.py — Google Sheets API Wrapper
- **SheetsAPI class** using google-api-python-client + google-auth
- Service account authentication via base64-encoded JSON
- **Weekly Review tab:** `write_weekly_review()` writes analysis + plan with plan_status="pending_review"; `read_plan_approval_status()` reads the status cell
- **Content Queue tab:** `write_content_queue(blog_posts, pins)` with header row and all columns the Apps Script expects; `read_content_approvals()` returns status for all items; `update_content_status(row, status)` updates individual items; `get_approved_pins_for_slot(date, time_slot)` filters by "YYYY-MM-DD/slot" schedule format
- **Post Log tab:** `append_post_log(pin_data)` appends rows; `read_post_log(date_range)` reads with optional date filtering; `update_pin_status()` as an append operation for full audit trail
- **Dashboard tab:** `update_dashboard(metrics)` / `update_dashboard_metrics()` writes key-value metric pairs
- Column index constants defined at module level to match Apps Script expectations
- All tab names are constants: "Weekly Review", "Content Queue", "Post Log", "Dashboard"

### src/apis/github_api.py — GitHub API for Blog Deployment
- **GitHubAPI class** using PyGithub library
- `commit_blog_post(slug, mdx_content, hero_image_path)` — single post commit to content/blog/{slug}.mdx + public/assets/blog/{slug}.ext
- `commit_blog_posts(mdx_files, images, branch)` — batch commit from (filepath, content) tuples, matches requirement interface
- `commit_multiple_posts(posts)` — batch commit from post dicts with slugs
- **Atomic multi-file commits** via Git Data API (create tree + commit + update ref) — all files in one commit
- `verify_deployment(slug_or_urls, max_wait_seconds)` — polls with exponential backoff (5s initial, 20s cap), accepts slugs or full URLs
- `create_branch(name, source_branch)` — creates branch from specified source
- `get_file_contents(path, branch)` — reads file content from repo
- Binary file support: hero images encoded as base64 blobs

### src/apis/slack_notify.py — Slack Webhook Wrapper
- **SlackNotify class** with method for every pipeline notification event
- `notify_review_ready(analysis_summary)` — weekly review with Sheet link
- `notify_content_generation_started()` — progress notification
- `notify_content_ready(num_pins, num_blog_posts)` — content review needed
- `notify_week_live(num_pins_scheduled, num_blog_posts_deployed)` — deployment confirmation
- `notify_posting_complete(slot, posted, total)` — daily posting results with color-coded severity
- `notify_failure(workflow, error)` — error alerts with truncated details (1500 char limit)
- `notify_monthly_review_ready(summary)` — monthly strategy review
- `notify_approval_reminder()` — Monday 6pm reminder
- `notify(message, level)` — generic notification with level-based colors
- `notify_reminder(pending_items)` — generic reminder
- **Slack Block Kit** formatting with color-coded attachment sidebars (green/yellow/red)
- Graceful degradation: if SLACK_WEBHOOK_URL not set, logs messages but doesn't fail

---

## 2. Environment Variables / Credentials Needed Before Testing

All variables are defined in `.env.example`. Here is what each module requires:

| Module | Required Env Vars |
|--------|-------------------|
| token_manager.py | `PINTEREST_APP_ID`, `PINTEREST_APP_SECRET`, and one of: `PINTEREST_ACCESS_TOKEN`+`PINTEREST_REFRESH_TOKEN` (env vars) or `data/token-store.json` (file) |
| pinterest_api.py | `PINTEREST_ACCESS_TOKEN` (or obtained via token_manager), optionally `PINTEREST_ENV` ("sandbox" or "production") |
| claude_api.py | `ANTHROPIC_API_KEY` |
| image_stock.py | `UNSPLASH_ACCESS_KEY` and/or `PEXELS_API_KEY` (at least one required) |
| image_gen.py | `OPENAI_API_KEY` (for DALL-E) and/or `REPLICATE_API_TOKEN` (for Flux Pro), optionally `IMAGE_GEN_PROVIDER` |
| sheets_api.py | `GOOGLE_SHEETS_CREDENTIALS_JSON` (base64-encoded service account JSON), `GOOGLE_SHEET_ID` |
| github_api.py | `GOSLATED_GITHUB_TOKEN`, `GOSLATED_REPO` (format: "owner/repo") |
| slack_notify.py | `SLACK_WEBHOOK_URL`, optionally `GOOGLE_SHEET_URL` (for Sheet links in messages) |

**Setup order for first-time testing:**
1. Set up Pinterest developer app, run initial OAuth flow via `python -m src.token_manager auth <CODE>`
2. Set all env vars in `.env` file
3. Test each module's smoke test via `python -m src.apis.<module_name>` or `python src/apis/<module_name>.py`

---

## 3. Design Decisions

### Token Manager: File-first, env-var fallback
The token manager reads from `data/token-store.json` first, then falls back to environment variables. This supports both local development (file-based) and GitHub Actions (env var bootstrap on first run, file for subsequent runs after commit-back). This aligns with the setup guide's "Approach A" recommendation.

### Token Manager: 60-day continuous refresh tokens
The skeleton docstring said "365-day lifetime" which is the deprecated legacy behavior. I corrected this to 60-day continuous refresh per the setup guide and the automation plan. The `initial_auth()` method sends `continuous_refresh=true` in the token exchange request.

### Pinterest API: Environment-based URL switching
Rather than hardcoding the sandbox URL for testing, the API client reads `PINTEREST_ENV` to switch between sandbox and production. This keeps the code identical for both environments.

### Claude API: Batch processing for pin copy
Pin copy generation batches 5-7 pins per API call as specified in the plan. This balances cost efficiency (fewer API calls) with response quality (not overloading a single prompt with too many items).

### Claude API: JSON response parsing
Claude sometimes wraps JSON in markdown code fences. The `_parse_json_response` method strips these before parsing. This is a pragmatic workaround for a common LLM behavior.

### Image Stock: Unified result format
Both Unsplash and Pexels return different response structures. The wrapper normalizes these into a consistent dict format with `source:id` composite keys for dedup tracking. This matches the content-log.jsonl format described in the plan.

### Image Generation: Prompt modification on retry
When image generation fails, retries use a slightly modified prompt (prepending composition style modifiers) to increase variance and improve the chance of success. This addresses the documented 10-25% failure rate.

### Sheets API: Append-only post log
Rather than finding and updating existing rows in the Post Log tab, `update_pin_status()` appends new rows. This provides a complete audit trail and avoids race conditions if multiple posting windows overlap.

### GitHub API: Tree-based atomic commits
Multi-file commits use the Git Data API (create tree + create commit + update ref) instead of sequential file updates. This ensures all blog posts and images appear in a single commit, which triggers exactly one Vercel deployment.

### Slack: Graceful degradation
If `SLACK_WEBHOOK_URL` is not configured, the notifier logs messages at INFO level instead of raising errors. This allows the pipeline to run in development without Slack set up.

---

## 4. Concerns and Manual Verification Needed

### Pinterest API sandbox vs. production
- The sandbox base URL handling is based on the setup guide. Verify that Trial access actually allows POST operations on the sandbox endpoint.
- The rate limit header names (X-RateLimit-*) are based on the setup guide and plan. Verify the exact header names when you make your first API calls.

### Pinterest API pin creation with image_base64
- The `source_type: "image_base64"` format is based on the v5 API documentation. Verify the exact field names and content_type values when testing. Some API versions use different base64 encoding conventions.

### OpenAI gpt-image-1 API format
- The gpt-image-1 API response format (b64_json vs URL) may vary based on the request parameters. The implementation handles both. The `response_format` parameter is not explicitly set in the request, relying on the API default. If the API requires explicit `response_format: "b64_json"`, that will need to be added.

### Replicate Flux Pro model version
- The Replicate integration uses `"black-forest-labs/flux-pro"` as the version string. Replicate model identifiers change as new versions are published. Verify the current model ID on replicate.com before running.

### Google Sheets column structure
- The column indices (A through K) for the Content Queue tab are defined as constants. These must match the actual Google Sheet structure and the Apps Script trigger logic. If you adjust the Sheet layout, update the constants in sheets_api.py.

### Google Sheets tab names
- Tab names are hardcoded as "Weekly Review", "Content Queue", "Post Log", "Dashboard". These must exactly match the tabs in your Google Sheet.

### Token store file and .gitignore
- `data/token-store.json` is currently in `.gitignore`. For GitHub Actions to persist tokens across runs (Approach A from the setup guide), you need to either remove it from `.gitignore` or implement Approach B (GitHub Secrets API updates). This is a deliberate trade-off discussed in the setup guide.

---

## 5. Integration Points

These are the imports other scripts in the pipeline use from these modules:

### Importing patterns used by pipeline scripts:

```python
# src/post_pins.py
from src.token_manager import TokenManager
from src.apis.pinterest_api import PinterestAPI, PinterestAPIError
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify

# src/generate_weekly_plan.py
from src.apis.claude_api import ClaudeAPI
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify

# src/generate_pin_content.py
from src.apis.claude_api import ClaudeAPI
from src.apis.image_stock import ImageStockAPI
from src.apis.image_gen import ImageGenAPI
from src.apis.sheets_api import SheetsAPI

# src/generate_blog_posts.py
from src.apis.claude_api import ClaudeAPI
from src.apis.sheets_api import SheetsAPI

# src/blog_deployer.py
from src.apis.github_api import GitHubAPI, GitHubAPIError
from src.apis.slack_notify import SlackNotify

# src/pull_analytics.py
from src.token_manager import TokenManager
from src.apis.pinterest_api import PinterestAPI

# src/weekly_analysis.py
from src.apis.claude_api import ClaudeAPI
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify

# src/monthly_review.py
from src.apis.claude_api import ClaudeAPI
from src.apis.slack_notify import SlackNotify

# All GitHub Actions workflows run token_manager first:
# python -m src.token_manager
```

### Module dependency graph:
```
token_manager.py
  -> slack_notify.py (lazy-loaded for failure alerts)

pinterest_api.py
  -> (standalone, uses access_token from token_manager)

claude_api.py
  -> (standalone, reads prompt templates from prompts/)

image_stock.py
  -> (standalone)

image_gen.py
  -> (standalone, optionally uses Pillow for validation)

sheets_api.py
  -> (standalone, uses google-api-python-client)

github_api.py
  -> (standalone, uses PyGithub)

slack_notify.py
  -> (standalone, no dependencies on other pipeline modules)
```

The only cross-dependency is token_manager importing slack_notify for failure alerts, and it uses lazy loading to avoid circular imports.
