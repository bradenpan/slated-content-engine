# TikTok Pipeline — Technical Debt & Design TODOs

Tracked issues that are not bugs but require architectural attention. These were identified during code review (2026-03-06) and intentionally deferred because they need design decisions, not quick fixes.

---

## ALGORITHMIC — Feedback Loop

### 1. Composite Score Scale Mismatch (explore/exploit weights are decorative)
**File:** `src/tiktok/compute_attribute_weights.py:56-70`
**Status:** OPEN — blocks feedback loop effectiveness
**Impact:** HIGH — the entire explore/exploit system is the core differentiator of this pipeline

The `_composite_score` function computes:
```
(saves/posts)*0.40 + (shares/posts)*0.35 + (likes/posts)*0.15 + (impressions/posts)*0.10
```

Raw metric scales are vastly different. A typical post gets ~10,000 impressions, ~50 likes, ~5 saves, ~2 shares. So:
- Impressions term: `10000 * 0.10 = 1000`
- Saves term: `5 * 0.40 = 2`
- Shares term: `2 * 0.35 = 0.7`

Impressions completely dominate despite having only a 10% weight. The 40% saves weight is **decorative**. Attribute weights effectively track "which topics get the most impressions" rather than the intended blend.

**Fix options:**
- (a) **Normalize to rates:** Use `save_rate = saves/impressions`, `share_rate = shares/impressions`, etc. Then weight the rates. This eliminates scale differences naturally.
- (b) **Z-score normalization:** Compute z-scores across all attributes in a dimension before weighting. Puts all metrics on the same scale.
- (c) **Rank-based scoring:** Rank attributes by each metric, then combine ranks. Immune to scale differences.

**Recommendation:** Option (a) — rates are already computed by `compute_derived_metrics`. Change `_composite_score` to use `save_rate * 0.40 + share_rate * 0.35 + like_rate * 0.15 + 0.10` (impressions become the base, weight = reach proxy).

**When to fix:** Before the feedback loop has enough real data to matter (after ~20 posts across multiple topics). Currently in cold-start, so the bug is dormant.

---

### 2. Unbounded Performance History (no recency windowing)
**File:** `src/tiktok/pull_analytics.py:146-148`, `compute_attribute_weights.py:154-195`
**Status:** OPEN — becomes problematic after ~8 weeks of data
**Impact:** MEDIUM — weights become increasingly sticky over time

`_build_performance_summary` includes ALL TikTok entries ever posted (no date filter). `update_taxonomy_from_performance` resets counters and re-accumulates from all entries equally. This means:
- A topic that performed well 3 months ago but poorly last month still gets high weight
- Old cold-start posts permanently drag down attribute averages
- The system cannot adapt to trend shifts

**Fix options:**
- (a) **Rolling window:** Apply a 12-week lookback when building the performance summary
- (b) **Exponential decay:** Weight recent posts more heavily (e.g., half-life of 4 weeks)
- (c) **Separate windows:** Use 4-week for exploit weights, all-time for explore baseline

**Recommendation:** Option (a) — simplest, and 12 weeks gives enough data for statistical significance while allowing adaptation.

**When to fix:** Before week 8 of real posting data.

---

### 3. Top/Bottom Performer Overlap
**File:** `src/tiktok/pull_analytics.py:155-161`, `src/tiktok/weekly_analysis.py:129-135`
**Status:** OPEN — cosmetic but misleading
**Impact:** LOW — confuses Claude's weekly analysis

When fewer than 10 scored posts exist, `top_posts[:5]` and `bottom_posts[-5:]` overlap. With exactly 5 posts, they're identical. The Claude analysis prompt receives the same posts as both top and bottom performers.

**Fix:** `bottom_posts = [p for p in scored[-5:] if p not in top_posts]` or skip bottom when `len(scored) < 10`.

**When to fix:** After 10+ posts are tracked.

---

## ARCHITECTURAL — Data Flow

### 4. Partial Render Slide Index Problem (mitigated but not eliminated)
**File:** `src/tiktok/carousel_assembler.py:322-333`
**Status:** MITIGATED — partial renders now reject the carousel entirely
**Impact:** Was CRITICAL, now LOW

The current fix rejects the entire carousel when `render_pin.js` returns partial results. This prevents the index misalignment bug but means a single flaky slide render kills the whole carousel. A better solution would preserve index mapping:

**Ideal fix:** Have `render_pin.js` return `null` entries for failed slides (preserving array indices), then have the assembler retry only failed slides in a second pass. This requires changes to both `render_pin.js` and `carousel_assembler.py`.

**When to fix:** If partial render failures become frequent in production (monitor via Slack warnings).

---

### 5. `pin_id` Field Name for TikTok Carousel Entries
**File:** `src/tiktok/post_content.py:293`
**Status:** OPEN — naming debt, no functional impact
**Impact:** LOW — confusing for new developers

TikTok content log entries use `pin_id` (a Pinterest convention) to store `carousel_id`. This works because `is_content_posted()` checks the `pin_id` field regardless of channel. But it's confusing and will bite someone eventually.

**Fix:** Add a `content_id` alias or migrate to a channel-agnostic field name. Requires updating `is_content_posted`, `load_content_log` queries, and analytics joins.

**When to fix:** Next time we touch the content log schema.

---

## OPERATIONAL — Workflow Reliability

### 6. Workflow Data Freshness Gap
**File:** `.github/workflows/tiktok-weekly-review.yml`, `.github/workflows/collect-analytics.yml`
**Status:** PARTIALLY MITIGATED — staleness check added to `compute_attribute_weights.py`
**Impact:** MEDIUM — stale data produces misleading analysis

`collect-analytics.yml` (10:30 UTC) and `tiktok-weekly-review.yml` (11:30 UTC) are coupled by timing only. If analytics collection fails or is delayed, the weekly review runs on stale data. The staleness check warns but does not abort.

**Fix options:**
- (a) Convert to `workflow_call` dependency
- (b) Add staleness check to `weekly_analysis.py` that aborts if data is >2h old
- (c) Both

**When to fix:** After the first instance of stale-data analysis in production.

---

### 7. Google Sheets API Rate Limiting
**File:** `src/shared/apis/sheets_api.py` (all TikTok methods)
**Status:** OPEN — no retry on 429/quota errors outside `_clear_and_write`
**Impact:** MEDIUM at scale — partial scheduling failures

`promote_and_schedule` calls `update_tiktok_content_status` in a loop for each carousel. With 21 carousels, that's 21 sequential Sheet API calls with no backoff. Google's 60 req/min quota could be hit.

**Fix:** Add exponential backoff retry to the Sheet API wrapper's `execute()` calls.

**When to fix:** When batch sizes exceed ~15 carousels.

---

## Summary

| # | Category | Issue | Impact | Fix Timing |
|---|----------|-------|--------|------------|
| 1 | Algorithm | Composite score scale mismatch | HIGH | Before ~20 posts |
| 2 | Algorithm | Unbounded performance history | MEDIUM | Before week 8 |
| 3 | Algorithm | Top/bottom performer overlap | LOW | After 10+ posts |
| 4 | Architecture | Partial render index mapping | LOW (mitigated) | If renders flake often |
| 5 | Architecture | `pin_id` naming for TikTok | LOW | Next schema change |
| 6 | Operational | Workflow data freshness gap | MEDIUM | After first stale incident |
| 7 | Operational | Sheets API rate limiting | MEDIUM | At scale (>15 carousels) |
