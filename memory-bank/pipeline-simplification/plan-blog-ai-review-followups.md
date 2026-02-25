# Plan: Blog AI Comparison Review Follow-ups

Non-blocking items identified by Sr Staff Engineer review of Phase 8.1 (blog AI comparison images + regen crash fix). None affect correctness — all are code clarity and robustness improvements.

## NB1 + NB2: Simplify redundant guards and clarify pass block

**File:** `src/regen_content.py`, `_regen_blog_image()` ~lines 787-802

After the early return at line 772 (`if not image_path: return result`), `image_path` is guaranteed truthy. Two guards are redundant:

```python
# Current (redundant `image_path and`):
if image_path and image_source != "ai_generated":
    ...
elif image_path and image_source == "ai_generated":
    pass
```

**Change to:**
```python
if image_source != "ai_generated":
    ...
# (remove the elif/pass block entirely — it does nothing)
```

The comment on the `pass` block ("will become comparison after GCS upload below") is misleading since the actual resolution happens in `regen()` caller at lines 236-238. Removing the block eliminates the confusion.

## NB3: Pin/blog AI upload path asymmetry

**File:** `src/regen_content.py`

Pin AI images are uploaded to GCS in `regen()` (after `_regen_item()` returns). Blog AI images are uploaded inside `_regen_blog_image()`. Both work correctly but the inconsistency makes the code harder to follow.

**Options:**
- A) Move blog AI upload out of `_regen_blog_image()` into `regen()` to match the pin pattern
- B) Move pin AI upload into `_regen_item()` to match the blog pattern
- C) Leave as-is (both work, and the functions have different enough structures to justify the difference)

**Recommendation:** Option C (leave as-is). The asymmetry exists because `_regen_item()` returns a `new_pin_data` dict with file paths that `regen()` processes, while `_regen_blog_image()` handles GCS upload internally because blog images don't go through pin rendering. The different structures justify different upload locations.

## NB4: Store AI image score for blogs

**File:** `src/regen_content.py`, `_regen_blog_image()` ~line 795

The `ai_meta` dict from `_source_ai_image()` contains the quality score but it's never exposed in the result dict. Add:

```python
if ai_url:
    result["ai_image_url"] = ai_url
    result["ai_image_score"] = ai_meta.get("image_quality_score")
```

Low priority — only useful if we add score display for blog AI images in the future.

## NB5: Log blogs with no pin association during initial publish

**File:** `src/publish_content_queue.py`, after the `blog_ai_image_urls` mapping block

Add debug logging for blogs that don't get an AI image due to no associated pin:

```python
if blog_ai_image_urls:
    logger.info("Mapped %d blog AI comparison images from associated pins", len(blog_ai_image_urls))
for post in blog_entries:
    if post["post_id"] not in blog_ai_image_urls:
        logger.debug("Blog %s has no associated pin AI image for column M", post["post_id"])
```

Low priority — in practice all blog posts have associated pins.

## NB6: Use dynamic extension for AI hero remote names

**File:** `src/regen_content.py`, lines 358 and 794

Currently hardcoded to `.png`:
```python
remote_name=f"ai-heroes/{item_id}-ai-hero.png"
```

Change to use actual file extension:
```python
remote_name=f"ai-heroes/{item_id}-ai-hero{ai_hero_path.suffix}"
```

Low priority — `_source_ai_image()` always generates `.png` files currently.

## NB7: Compute summary row width from header

**File:** `src/apis/sheets_api.py`, lines 397-403

The quality gate summary row pads with 13 empty strings to match header width. If columns are added, this breaks silently.

**Change to:**
```python
summary_row = ["QUALITY GATE STATS", "", stock_summary, ai_summary]
summary_row.extend([""] * (len(rows[0]) - len(summary_row)))
rows.append(summary_row)
```

## Priority

| # | Priority | Effort | Impact |
|---|----------|--------|--------|
| NB1+NB2 | Low | 5 min | Code clarity |
| NB3 | Skip | — | Leave as-is per recommendation |
| NB4 | Low | 2 min | Future debugging data |
| NB5 | Low | 2 min | Observability |
| NB6 | Low | 2 min | Future-proofing |
| NB7 | Low | 5 min | Robustness |

All items are low priority. Recommend batching with the next feature change that touches these files rather than making a standalone commit.
