# Image Quality Analysis -- Final Report

**Date:** 2026-02-24
**Scope:** Week 9 content run (2026-02-23) -- 10 blog posts, 28 pins
**Data sources:** Initial generation Excel, regen results Excel, GitHub Actions regen logs, full code trace of image generation and regen flows, AI/stock image provider research

---

## 1. Executive Summary

### Core Problems

- **55% of all content items (21 of 38) required image regen.** The initial image selection pipeline failed more often than it succeeded for recipe-specific content. Of 28 pins, 15 needed regen (54%); of 10 blog hero images, 6 needed regen (60%).
- **The #1 failure mode is "wrong food subject."** Stock photo search returns visually similar but semantically wrong images (e.g., chicken with oranges instead of lemon herb chicken, broccoli instead of beef and broccoli stir-fry). The ranking model (Claude Haiku at thumbnail resolution) cannot reliably distinguish between similar-looking food items.
- **Blog image regen was completely broken** during this run due to a data lookup bug. All 6 blog regen requests failed with "Blog regen not supported." This has since been fixed in commit `fd655ea`.
- **8 of 28 pins (29%) were template-only pins that the reviewer wanted as stock images.** The weekly plan over-assigned Tier 3 (template-only) to pins that needed real food photography, forcing manual regen.
- **Regen feedback does not reach the ranking model effectively.** The reviewer's complaint about what was wrong is appended to a JSON blob but the `image_rank.md` prompt has zero instructions to consider it. Haiku can re-select images with the same defect.

### Top Recommendations

- **P0: Surface regen feedback to the ranking model's system message.** Small code change in `claude_api.py` that directly addresses the regen failure loop. (Section 7, Recommendation A1)
- **P0: Use multiple search queries during regen instead of just the first.** Already designed and ready to implement. Expands the candidate pool from ~20 to ~30+ images. (Section 7, Recommendation A2)
- **P1: Upgrade the ranking model from Haiku to Sonnet for food-subject identification,** or increase thumbnail resolution. Haiku misidentifies food at ~200px thumbnails. (Section 7, Recommendation C1)
- **P1: Reduce Tier 3 (template-only) assignments in the weekly plan prompt.** 8 pins were assigned template-only but needed stock images. The plan prompt should default recipe-adjacent pins to stock. (Section 7, Recommendation B1)
- **P1: Upgrade AI fallback from gpt-image-1 to gpt-image-1.5 (medium quality).** Drop-in model name change, better photorealism, same or lower cost. (Section 7, Recommendation E1)

---

## 2. How Initial Image Generation Works (Step-by-Step)

**Entry point:** `src/generate_pin_content.py`, function `generate_pin_content()` (line 47)

For each pin in the weekly plan:

1. **Generate pin copy** (title, description, alt text, text overlay) -- Claude Sonnet 4 at temperature 0.7, batched 6 pins per API call using `prompts/pin_copy.md`. Alt text is generated here, BEFORE the image is sourced, meaning it describes what the image *should* look like based on the topic, not what it actually contains.

2. **Determine image source tier** from the weekly plan's `image_source_tier` field:
   - **Tier 1 (Stock):** Unsplash + Pexels free APIs. Default for recipe-pin, tip-pin, listicle-pin.
   - **Tier 2 (AI):** OpenAI gpt-image-1 or Replicate Flux Pro. Used as fallback when stock scores too low.
   - **Tier 3 (Template-only):** No image sourced. Used for infographic-pin and some problem-solution pins.

3. **Stock image path (Tier 1):**
   - 3a. **Generate search queries** -- Claude Sonnet 4 at temperature 0.8 reads `prompts/image_search.md` and produces 3-5 queries ranked specific-to-broad. **Only the first query is used** (`queries[0]`); the rest are discarded.
   - 3b. **Search both APIs** -- The single query goes to Unsplash (max 10 results) and Pexels (max 10 results), producing ~20 candidates.
   - 3c. **Download top 5 thumbnails** (~200px) and send to Claude Haiku 4.5 for visual ranking at temperature 0.3 using `prompts/image_rank.md`. Scoring: 9-10 perfect, 7-8 good, 5-6 acceptable, 3-4 poor, 1-2 unusable. "Wrong food subject = score 1-2" per the prompt.
   - 3d. **Quality gate:** If best score >= 6.5, select that image. If all < 6.5, retry with a broader query (same process). If retry best < 5.0, fall back to Tier 2 (AI generation).

4. **AI image path (Tier 2):**
   - 4a. **Generate AI prompt** -- Claude Sonnet 4 reads `prompts/image_prompt.md`, producing a detailed prompt with style anchors, composition guidance, and a negative prompt (which is generated but never actually used -- see Issue 6 below).
   - 4b. **Generate image** -- OpenAI gpt-image-1 at 1024x1536, quality "high" (~$0.08/image). Up to 3 attempts with modifier prefixes on retry ("Professional food photography style," etc.).
   - 4c. **Validate with vision** -- Claude Sonnet 4 at temperature 0.3 evaluates the full-size image using `prompts/image_validate.md`. If score < 6.5, one retry with feedback appended to prompt. If still < 6.5, accept with `low_confidence=True` flag.

5. **Assemble final pin** -- HTML/CSS template (`templates/pins/{template}/template.html`) + image + copy rendered to 1000x1500 PNG via Puppeteer. Images > 500KB are converted to JPEG (quality 88).

6. **Save results** to `data/pin-generation-results.json` with image source, image ID, quality scores, and metadata.

### Models Used at Each Step

| Step | Model | Temperature | Purpose |
|------|-------|-------------|---------|
| Copy generation | Claude Sonnet 4 | 0.7 | Title, description, alt text, text overlay |
| Search query generation | Claude Sonnet 4 | 0.8 | Stock photo search queries |
| AI prompt generation | Claude Sonnet 4 | 0.8 | Image generation prompts |
| Stock image ranking | Claude Haiku 4.5 | 0.3 | Visual evaluation of thumbnails |
| AI image validation | Claude Sonnet 4 | 0.3 | Quality gate for AI images |
| Image generation (default) | OpenAI gpt-image-1 | N/A | AI image generation |
| Image generation (alt) | Replicate Flux Pro | N/A | AI image generation |

---

## 3. How Image Regen Works (Step-by-Step)

**Entry point:** `src/regen_content.py`, function `regen()` (line 51)

### Trigger Mechanism

1. Reviewer marks rows in the Content Queue Google Sheet with `regen_image`, `regen_copy`, or `regen` (both) in column J (Status).
2. Reviewer writes specific feedback in column L (Feedback).
3. Reviewer types `run` in cell N1.
4. Google Apps Script (`src/apps-script/trigger.gs`) fires a `repository_dispatch` event to GitHub Actions with event type `regen-content`.
5. `regen_content.py` runs on the GitHub Actions runner.

### Regen Process for Pins

1. **Read regen requests** from Sheets API -- columns A through L, filtering for rows where Status starts with "regen."

2. **Reconstruct pin_spec** from `pin-generation-results.json`:
   - **Key difference from initial gen:** `pin_topic` is set to the AI-generated *title* (e.g., "Lemon Herb Chicken with Spring Vegetables -- Easy One Pan Dinner") instead of the original plan topic (e.g., "Lemon herb chicken with spring vegetables"). The generated title may be shorter or reworded, potentially producing different search queries.
   - Feedback is attached as `pin_spec["_regen_feedback"]`.

3. **Determine image source tier** -- locked to the original tier. Stock stays stock, AI stays AI. Template-only pins fall through to the `else` branch which defaults to stock (this is accidental but correct behavior when the reviewer requests a stock image).

4. **Source new image** -- uses the exact same `source_image()` function as initial gen. Same prompts, same search APIs, same ranking model.

5. **Re-render pin** with the new image (and new copy if `regen` type).

6. **Upload to GCS** and update the Content Queue sheet.

### What Changes vs Initial Gen

| Aspect | Initial Gen | Regen |
|--------|------------|-------|
| `pin_topic` source | Weekly plan topic | Generated title (from results JSON) |
| Search query prompt | Base `image_search.md` | Same + feedback appended to system message |
| Ranking prompt | Base `image_rank.md` | Same (feedback buried in PIN_SPEC JSON, not surfaced) |
| AI prompt | Base `image_prompt.md` | Same + feedback appended to system message AND prompt text |
| AI validation | Base `image_validate.md` | Same (no regen awareness) |
| Number of search queries used | 1 of 3-5 | 1 of 3-5 (same limitation) |
| Image tier | From weekly plan | Locked to original tier |

### Where Regen Feedback Reaches vs Where It Gets Lost

| Stage | Feedback Reaches? | How? | Effective? |
|-------|-------------------|------|------------|
| Search query generation | YES | Appended to system message with "IMPORTANT" prefix | Yes -- queries correctly pivot (e.g., "overhead lemon herb chicken" instead of original query) |
| Stock candidate ranking | PARTIALLY | Buried as `_regen_feedback` field in JSON dump | **No** -- prompt has no instructions about regen feedback; Haiku ignores it |
| AI image prompt generation | YES | System message + appended to prompt text with "CRITICAL" prefix | Yes |
| AI image validation | NO | Not passed at all | N/A |
| Copy regen | YES | `_copy_feedback` checked explicitly, added to system message | Yes |

### Blog Regen Limitations

- **Blog copy regen is not supported** -- blog text lives in committed MDX files.
- **Blog image regen was broken** during this run (data lookup bug, fixed in `fd655ea`).
- Blog images are raw stock/AI photos (not rendered through pin templates).

---

## 4. Root Cause Analysis -- Why ~55% of Initial Images Failed

### Failure Category 1: Wrong Food Subject (7 pins)

**Affected pins:** W9-02, W9-09, W9-12, W9-16, W9-17, W9-18, W9-27

**What went wrong:** The stock photo search returned images of the wrong food. The ranking model (Haiku) scored them 6.5+ because the images were high-quality food photography that looked superficially relevant, but showed the wrong dish.

**Specific examples:**
- **W9-02** (Lemon Herb Chicken): Received a score of 9.0 from Haiku, but showed "chicken with oranges" -- visually similar but wrong recipe. Reviewer: *"this is chicken with oranges, the recipe talks about lemon herb chicken."*
- **W9-18** (Beef and Broccoli Stir-Fry): Scored 9.0, but showed just broccoli with no beef. Reviewer: *"this is a picture of broccoli, not a picture of beef and broccoli stir-fry."*
- **W9-17** (Chicken and Rice Skillet): Scored 9.0, but showed an unidentifiable dish. Reviewer: *"i have no idea what this is a picture of but it is not chicken and rice in one pan."*
- **W9-27** (Pasta Primavera): Scored 6.5, showed flowers instead of food. Reviewer: *"this is a picture of flowers. the recipe is pasta primavera with vegetables."*

**Why the system allows this:**
1. **Haiku evaluates ~200px thumbnails.** At this resolution, different food dishes look similar -- a bowl of citrus can resemble lemon herb chicken, and broccoli florets alone can look like a stir-fry from above.
2. **Only 1 of 3-5 generated queries is used.** The search produces only ~20 candidates, limiting the pool. A broader search might find more on-topic images.
3. **The ranking prompt says "wrong food = score 1-2"** but Haiku fails to detect the wrong food at thumbnail resolution, so the rule never triggers.

### Failure Category 2: Template-Only Assigned to Pins Needing Photos (8 pins)

**Affected pins:** W9-19, W9-20, W9-21, W9-22, W9-23, W9-24, W9-25, W9-26

**What went wrong:** The weekly plan generation assigned `image_source_tier: "template"` (Tier 3) to pins that needed real food photography. These pins rendered with text-only designs, but the reviewer wanted stock food images.

**Specific examples:**
- All 8 pins received identical feedback: *"this should be a stock image not a template."*
- These were secondary/supporting pins (recipe-pull, listicle, tip types) for topics like "Hidden Veggie Recipes," "Family Meal Planning," "30 Minute Meals," and "Air Fryer Chicken Dinners" -- all food-related topics where photography significantly outperforms text-only designs.

**Why the system allows this:**
1. **The weekly plan prompt determines the tier.** If the plan prompt assigns Tier 3 to a pin type that would benefit from photography, there is no override mechanism.
2. **No reviewer preview before generation.** The tier assignment is baked into the plan and cannot be adjusted before images are generated.
3. **The plan prompt may be over-assigning Tier 3** to non-primary pins. Looking at the data: all 8 template-only pins were secondary pins (not the "primary" pin for each blog post). The plan prompt appears to reserve stock photos for primary pins and default secondary pins to template-only, even when the secondary pin topic is food-specific.

### Failure Category 3: Wrong/Missing Blog Hero Images (6 blog posts)

**Affected blogs:** W9-P03, W9-P04, W9-P06, W9-P08, W9-P09, W9-P10

**What went wrong:** Blog hero images either showed the wrong food or were missing entirely.

**Specific examples:**
- **W9-P03** (Hidden Veggie Mac and Cheese): *"this is a picture of vegetables, not a picture of mac and cheese WITH vegetables."*
- **W9-P04** (Family Dinner Agreement Guide): *"there is no picture here. what is supposed to go in this spot?"*
- **W9-P06** (Teriyaki Salmon): *"this picture has noodles, the recipe is just salmon teriyaki."*
- **W9-P08** (HelloFresh Alternative): *"there is no picture."*
- **W9-P10** (Turkey Meatball Bowls): *"this is a picture of meatballs in tomato sauce. the recipe calls for meatball bowls with quinoa and vegetables."*

**Why the system allows this:** Same root causes as Category 1 (wrong food subject detection) plus missing images suggest the stock search returned zero acceptable candidates and the fallback path failed silently for some blog items.

### Failure Summary

| Category | Count | % of Total (38) | Root Cause |
|----------|-------|-----------------|------------|
| Wrong food subject (pins) | 7 | 18% | Haiku misidentifies food at thumbnail resolution; limited candidate pool |
| Template-only needing stock (pins) | 8 | 21% | Weekly plan over-assigns Tier 3 to secondary pins |
| Wrong/missing blog images | 6 | 16% | Same as wrong food subject + possible blog path bugs |
| **Total needing regen** | **21** | **55%** | |
| Approved on first pass | 17 | 45% | |

---

## 5. Root Cause Analysis -- Why Regen Often Failed Too

### Post-Regen Results from the Regen Excel

Of the 21 regen requests:
- **6 blog regens failed completely** (blog regen bug -- now fixed)
- **15 pin regens technically succeeded** (new images sourced)

Of the 15 pin regens that produced new images, the reviewer's post-regen status in the regen Excel shows:

| Pin | Regen Score | Post-Regen Status | Post-Regen Feedback |
|-----|-------------|-------------------|---------------------|
| W9-02 | 8.0 | regen_image | *"this is a picture of a lemon with some vegetables. the recipe is lemon herb chicken"* |
| W9-09 | 9.0 | regen_image | *"this is a bunch of vegetables. there is no mac and cheese"* |
| W9-12 | 7.5 | regen_image | *"there is no salmon in this picture"* |
| W9-16 | 7.5 | regen_image | *"this is eggs in a sauce. the alt image text provides the right description"* |
| W9-17 | 9.0 | regen_image | *"this is an asian chicken (which looks good) but the alt image description is the right description"* |
| W9-18 | 7.5 | regen_image | *"this is incorrect. the alt image description is the right one to look for"* |
| W9-19 | 8.5 | approved | -- |
| W9-20 | 8.0 | approved | -- |
| W9-21 | 8.5 | approved | -- |
| W9-22 | 8.5 | approved | -- |
| W9-23 | 8.5 | approved | -- |
| W9-24 | 7.5 | regen_image | *"this image does not relate to the text. please regen"* |
| W9-25 | 8.0 | approved | -- |
| W9-26 | 9.0 | approved | -- |
| W9-27 | 8.0 | approved | -- |

**Key finding:** 7 of 15 pin regens (47%) were rejected again after regen. All 8 template-to-stock conversions succeeded, but 6 of 7 "wrong food subject" regens failed again, plus 1 template-to-stock pin (W9-24).

### Why "Wrong Food Subject" Regens Keep Failing

1. **Feedback does not reach the ranking model.** This is the most critical gap. The reviewer says "this is chicken with oranges, not lemon herb chicken" and the search query correctly pivots to "overhead lemon herb chicken vegetables one pan" (confirmed in logs). But when Haiku ranks the new candidates, it has no knowledge of the complaint. The `_regen_feedback` field is buried in a JSON dump inside `{{PIN_SPEC}}`, and `image_rank.md` has zero instructions about regen feedback. So Haiku scores purely on visual match and can select another image with the same problem.

2. **Haiku still misidentifies food at thumbnail resolution.** Even with a corrected search query, Haiku evaluates ~200px thumbnails and cannot reliably distinguish between similar food items. For W9-02, the regen query was correct ("overhead lemon herb chicken"), Haiku scored the result 8.0, but the reviewer still saw "a lemon with some vegetables" -- no chicken.

3. **Only one search query is used.** During regen, Claude generates 3-5 queries but only `queries[0]` is sent to stock APIs. W9-12's regen query "teriyaki salmon bowl rice vegetables overhead" returned 0 Unsplash results and only 10 Pexels results -- a very small pool. Using all 3 queries would have produced ~30 candidates.

4. **pin_topic uses the generated title, not the original plan topic.** During regen, `pin_topic` is the AI-generated title, which may differ from the raw plan topic. This can produce subtly different (and potentially worse) search queries.

5. **No memory of what was already tried.** The regen system does not track what search queries were used or what candidates were evaluated during initial gen. It can generate the same query and select the same type of wrong image.

### Why Template-to-Stock Regens Mostly Succeeded

The 8 template-to-stock conversions had a 88% success rate (7/8 approved). These succeeded because:
- They were genuinely easier -- any relevant food photo was an improvement over a text-only template.
- The stock search for general food topics ("creamy pasta," "air fryer chicken") returns many relevant results.
- The quality bar was lower -- the reviewer accepted any on-topic food photo.

---

## 6. AI Image Generation vs Stock Photos -- Cost/Quality Summary

### Comparison Table

| Provider | Type | Cost/Image | Food Quality | Integration Effort | Notes |
|----------|------|-----------|-------------|-------------------|-------|
| Unsplash + Pexels | Stock | Free | Variable | Already done | Current primary source |
| Shutterstock | Stock | $1-29/image | Excellent | Moderate | Not cost-effective at 150 images/month |
| Getty Images | Stock | $100+/image | Premium | Moderate | Prohibitively expensive |
| Foodiesfeed | Stock | $49 lifetime | Excellent (food-only) | None (no API) | Manual supplement only |
| gpt-image-1 (current) | AI | $0.08 | Good | Already done | Aging; occasional artifacts |
| **gpt-image-1.5 medium** | **AI** | **$0.05** | **Very Good** | **Trivial (model name change)** | **Recommended upgrade** |
| gpt-image-1.5 high | AI | $0.20 | Excellent | Trivial | Expensive at scale |
| **Flux 2 Pro (Replicate)** | **AI** | **$0.03-0.04** | **Very Good** | **Low (already partially integrated)** | **Best photorealism for food** |
| Flux 2 Max (Replicate) | AI | $0.05-0.08 | Excellent | Low | Premium option |
| Adobe Firefly | AI | $0.02 | Good | Moderate | IP-safe (indemnified) |
| Stable Image Ultra | AI | $0.08 | Moderate | Moderate | Not food-specialized |
| Ideogram | AI | $0.06 | Moderate | Moderate | Best text rendering in images |
| Midjourney | AI | N/A | Excellent | **Not viable** | No official API |

### Food Photography Quality Rankings (AI providers)

1. **Flux 2 Max** -- Best photorealism for material physics, lighting, and textures
2. **GPT-Image-1.5 (high)** -- Best overall quality + text rendering
3. **Flux 2 Pro** -- Sweet spot of quality and price for food content
4. **GPT-Image-1.5 (medium)** -- Good balance of cost and quality
5. **gpt-image-1 (current)** -- Decent but aging; occasional utensil/hand artifacts

### Monthly Cost Estimates (~150 images/month)

| Scenario | Monthly Cost | Image Quality |
|----------|-------------|---------------|
| **Current** (Unsplash/Pexels + gpt-image-1 fallback) | ~$3.79 | Good |
| **Recommended** (Unsplash/Pexels + Flux 2 Pro primary AI + gpt-image-1.5 secondary) | ~$2.32 | Very Good |
| AI-only (gpt-image-1.5 medium) | ~$7.50 | Good-Very Good |
| Premium stock (Shutterstock) | $150-$450 | Excellent |

### Licensing Considerations

- **Free stock (Unsplash + Pexels):** Irrevocable, nonexclusive, free for commercial use. Very low risk. Not exclusive.
- **AI-generated images:** Generally permitted for commercial use by all major providers. Not copyrightable under current US guidance. No exclusivity. Food photography is a low-risk use case for IP concerns.
- **Adobe Firefly advantage:** If IP risk ever becomes a concern, Firefly is the safest AI option -- trained exclusively on licensed Adobe Stock content, with commercial indemnification.
- **Pinterest platform:** No current restrictions against AI-generated content, but this could change.

---

## 7. Prioritized Recommendations

### Group A: Quick Wins (Small Effort, High Impact)

#### A1: Surface regen feedback to ranking model system message
- **What:** In `src/apis/claude_api.py`, method `rank_stock_candidates()`, add regen feedback to the system message: *"CRITICAL: This is a re-selection. The previous image was rejected with this feedback: '{feedback}'. Any candidate matching this complaint MUST score 1-2."*
- **Why:** Addresses the #1 regen failure mode -- the ranking model re-selecting images with the same defect (Section 5). Currently 6 of 7 "wrong food" regens failed again because feedback never reaches the ranker.
- **Effort:** Small -- ~5 lines of code in one file
- **Impact:** High -- directly prevents the regen failure loop for wrong-food-subject complaints
- **Priority:** P0

#### A2: Use multiple search queries during regen
- **What:** In `src/generate_pin_content.py`, method `_source_stock_image()`, use up to 3 of the generated queries (instead of just `queries[0]`) when `_regen_feedback` is present. Deduplicate candidates across queries.
- **Why:** Addresses the limited candidate pool problem (Section 4, Category 1). W9-12's regen got 0 Unsplash results; using 3 queries would have tripled the search surface.
- **Effort:** Small -- ~15 lines, already fully designed in `regen-quality-improvements.md`
- **Impact:** High -- more candidates means better chance of finding the correct food subject
- **Priority:** P0

#### A3: Store image search queries and AI prompts in results JSON
- **What:** Save `_image_search_query` and `_image_prompt` to `pin-generation-results.json` and include previous values in regen history.
- **Why:** Currently debugging image failures requires reading full GitHub Actions logs. Stored prompts enable quick diagnosis and comparison across regens.
- **Effort:** Small -- add 2 fields to the results dict in 2 files
- **Impact:** Medium -- improves debugging speed, no direct quality improvement
- **Priority:** P1

### Group B: Prompt/Query Improvements

#### B1: Reduce Tier 3 over-assignment in the weekly plan prompt
- **What:** Update the weekly plan generation prompt to default secondary/supporting pins for food topics to Tier 1 (stock) instead of Tier 3 (template-only). Reserve Tier 3 only for infographic-pin and explicitly non-visual content.
- **Why:** Addresses Section 4, Category 2 -- 8 of 28 pins (29%) were template-only but needed food photography. All were secondary pins.
- **Effort:** Small-Medium -- modify `prompts/weekly_plan.md` with clearer tier assignment rules
- **Impact:** High -- eliminates the single largest failure category by count
- **Priority:** P1

#### B2: Improve search query specificity for recipe pins
- **What:** Add a "critical ingredients" instruction to `prompts/image_search.md` that forces the first query to include the specific protein AND presentation style (e.g., "lemon herb chicken pan" not just "dinner chicken vegetables").
- **Why:** The current query generator sometimes produces queries that are too generic for specific recipes, leading to wrong-food results (Section 4, Category 1).
- **Effort:** Small -- prompt text update
- **Impact:** Medium -- helps but doesn't solve the ranking model limitation
- **Priority:** P1

#### B3: Add regen-specific instructions to image_rank.md prompt
- **What:** Add a conditional section to `prompts/image_rank.md` that is activated when `_regen_feedback` is present in the PIN_SPEC, explicitly instructing the model to read and apply the feedback as a hard constraint.
- **Why:** Complements recommendation A1 (system message) with in-prompt instructions. Belt-and-suspenders approach for the most critical failure mode.
- **Effort:** Small -- prompt text update
- **Impact:** Medium -- reinforces A1
- **Priority:** P1

### Group C: Ranking and Evaluation Improvements

#### C1: Upgrade ranking model or increase thumbnail resolution
- **What:** Either (a) use Claude Sonnet instead of Haiku for stock candidate ranking, or (b) increase thumbnail resolution from ~200px to ~400-500px, or (c) both.
- **Why:** Haiku at ~200px cannot reliably distinguish between similar food items (Section 4, Category 1). Example: scoring "lemon and vegetables" as 8.0 for a "lemon herb chicken" pin.
- **Effort:** Medium -- (a) is a model name change but increases cost from ~$0.002 to ~$0.01 per ranking call; (b) requires changing the thumbnail download size
- **Impact:** High -- directly addresses the core food misidentification problem
- **Priority:** P1
- **Cost note:** At 150 images/month with ~5 thumbnails per ranking call, upgrading to Sonnet adds ~$1.20/month. Increasing resolution also increases Haiku token costs slightly.

#### C2: Add post-selection visual verification step
- **What:** After selecting the best stock image candidate, download the full-size image and run a second Claude Sonnet vision check asking "Does this image show [specific food from pin_topic]? Yes/No." Reject and try next candidate if No.
- **Why:** The ranking model evaluates thumbnails. A full-size verification catches misidentifications that thumbnails hide.
- **Effort:** Medium -- add a verification step after image selection, before rendering
- **Impact:** High -- catches wrong-food errors that slip through thumbnail ranking
- **Priority:** P2 (implement after C1 if C1 alone is insufficient)

#### C3: Use alt text as verification reference during regen
- **What:** The reviewer noted multiple times that "the alt image description is the right description to look for." During regen, pass the existing `alt_text` to the ranking model as the ground truth for what the image should show.
- **Why:** Alt text is generated from the pin topic before image sourcing and describes the ideal image. It provides a clear reference for what the image should contain.
- **Effort:** Small -- add alt_text to the ranking context
- **Impact:** Medium -- gives the ranker a concrete description to match against
- **Priority:** P1

### Group D: Regen-Specific Improvements

#### D1: Add regen feedback to AI image validation prompt
- **What:** When `_regen_feedback` is present, append it to the `image_validate.md` context so the validation model can check whether the AI-generated image avoids the complained-about defect.
- **Why:** Currently AI image validation has zero regen awareness (Section 3 feedback propagation table). The validator can pass an image with the same defect.
- **Effort:** Small -- add feedback to template context
- **Impact:** Medium -- only affects AI-generated images (Tier 2), not stock path
- **Priority:** P1

#### D2: Use original plan topic instead of generated title for regen pin_topic
- **What:** Store the original `pin_topic` from the weekly plan in `pin-generation-results.json`. During regen, use the original topic instead of the generated title for search query generation.
- **Why:** The generated title is often shorter and "Pinterest-optimized," which can produce different (worse) search queries during regen (Section 5, root cause #4).
- **Effort:** Small -- add one field to results JSON, change one line in regen
- **Impact:** Low-Medium -- subtle improvement to search query quality
- **Priority:** P2

#### D3: Allow tier switching during regen
- **What:** Add a mechanism for the reviewer to specify a different image source tier in the feedback (e.g., "use AI" or "use stock"). Currently the tier is locked to the original.
- **Why:** Some images might be better served by AI generation (when stock photos consistently show the wrong food) or vice versa.
- **Effort:** Medium -- parse tier hints from feedback, add tier override logic
- **Impact:** Low -- edge case; most regens stay on the same tier
- **Priority:** P2

### Group E: Model/API Changes

#### E1: Upgrade AI fallback to gpt-image-1.5 (medium quality)
- **What:** Change the model name in `src/apis/image_gen.py` from `gpt-image-1` to `gpt-image-1.5` at medium quality.
- **Why:** Significant improvement in food photorealism and text rendering. Lower cost ($0.05 vs $0.08 per image). Drop-in change with no API integration work.
- **Effort:** Small -- one model name string change
- **Impact:** Medium -- only affects AI-generated images (~20% of total), but those images will be noticeably better
- **Priority:** P1

#### E2: Add Flux 2 Pro as primary AI fallback
- **What:** Update `src/apis/image_gen.py` to use Flux 2 Pro via Replicate as the primary AI provider, with gpt-image-1.5 as secondary (for text-in-image scenarios).
- **Why:** Flux 2 Pro has the best photorealism for food at $0.03-0.04/image. Already partially integrated via Replicate.
- **Effort:** Small-Medium -- update model ID in existing Replicate integration
- **Impact:** Medium -- better AI fallback quality at lower cost
- **Priority:** P2

#### E3: Apply for Unsplash Production rate limit
- **What:** Apply for Unsplash Production access (5,000 req/hr, free).
- **Why:** Current 50 req/hr limit constrains batch processing. Not a critical bottleneck for current volume but would become one at scale.
- **Effort:** Small -- fill out application form
- **Impact:** Low (at current volume)
- **Priority:** P2

### Group F: Architectural Improvements

#### F1: Use all search queries for initial gen too (not just regen)
- **What:** Extend A2 to also use multiple queries during initial generation, not just regen.
- **Why:** The limited candidate pool contributes to wrong-food selections in initial gen. More candidates = better ranking results.
- **Effort:** Small -- extend the multi-query logic from A2 to all stock searches
- **Impact:** Medium -- addresses Category 1 failures at the source
- **Priority:** P1 (implement alongside A2)

#### F2: Generate alt text AFTER image selection, not before
- **What:** Move alt text generation to after image sourcing. Use Claude Sonnet vision to describe the actual selected image, incorporating the primary keyword.
- **Why:** Currently alt text describes what the image *should* look like, not what it *actually* contains (Issue 4). This can be misleading for accessibility and Pinterest SEO.
- **Effort:** Medium -- restructure the copy generation flow to split alt text into a post-image step
- **Impact:** Medium -- improves Pinterest SEO accuracy, not directly related to image quality failures
- **Priority:** P2

#### F3: Add structured regen tracking/history
- **What:** Store regen attempts, search queries, candidate scores, and outcomes in a structured format (extend `pin-generation-results.json` with a `_regen_history` array).
- **Why:** Currently debugging regen requires reading raw GitHub Actions logs (Section 3, Finding 7). Structured tracking enables data-driven improvements.
- **Effort:** Medium -- add tracking to regen_content.py
- **Impact:** Low (operational improvement, no direct quality impact)
- **Priority:** P2

---

## 8. Recommended Implementation Order

### Phase 1: Immediate (address the regen failure loop)

1. **A1: Surface regen feedback to ranking model** -- ~30 minutes, directly fixes the regen failure loop
2. **A2: Use multiple search queries during regen** -- ~1 hour, already fully designed
3. **F1: Extend multi-query to initial gen** -- ~15 minutes, piggybacks on A2

*Expected impact: Reduces wrong-food regen failures from ~85% (6/7) to an estimated ~30-40% by giving the ranker actionable feedback and a larger candidate pool.*

### Phase 2: Near-term (address root causes in initial gen)

4. **B1: Reduce Tier 3 over-assignment** -- eliminates the largest failure category (8 of 21 failures)
5. **C1: Upgrade ranking model or thumbnail resolution** -- addresses food misidentification at the source
6. **C3: Use alt text as ranking reference** -- gives the ranker a concrete target description
7. **E1: Upgrade to gpt-image-1.5** -- better AI fallback quality, trivial change

*Dependencies: None between these; all can be done in parallel.*

### Phase 3: Refinements

8. **A3: Store search queries/prompts in results JSON** -- improves debuggability for all subsequent work
9. **B2: Improve search query specificity** -- tuning based on data from Phase 1-2 results
10. **B3: Add regen instructions to image_rank.md** -- reinforces A1
11. **D1: Add regen feedback to AI validation** -- completes feedback propagation
12. **D2: Use original plan topic for regen pin_topic** -- subtle improvement

### Phase 4: Optional/Future

13. **C2: Post-selection visual verification** -- only if C1 is insufficient
14. **E2: Add Flux 2 Pro as primary AI** -- quality improvement for AI-generated images
15. **E3: Apply for Unsplash Production rate limit** -- scale preparation
16. **F2: Generate alt text after image selection** -- accuracy improvement
17. **D3: Allow tier switching during regen** -- edge case convenience
18. **F3: Structured regen tracking** -- operational improvement

---

## Appendix A: Raw Data Summary

### Initial Generation Results (from Excel)

| ID | Type | Status | Score | Feedback |
|----|------|--------|-------|----------|
| W9-01 | pin | approved | 8.5 | -- |
| W9-02 | pin | regen_image | 9.0 | chicken with oranges, not lemon herb chicken |
| W9-03 | pin | approved | 8.5 | -- |
| W9-04 | pin | approved | 9.0 | -- |
| W9-05 | pin | approved | 8.0 | -- |
| W9-06 | pin | approved | 8.5 | -- |
| W9-07 | pin | approved | 9.0 | -- |
| W9-08 | pin | approved | 8.5 | -- |
| W9-09 | pin | regen (both) | 6.5 | vegetables not mac and cheese; title wrong |
| W9-10 | pin | approved | -- | -- |
| W9-11 | pin | approved | 9.0 | -- |
| W9-12 | pin | regen_image | 8.0 | noodles, should be salmon bowl |
| W9-13 | pin | approved | 9.0 | -- |
| W9-14 | pin | approved | -- | -- |
| W9-15 | pin | approved | 8.5 | -- |
| W9-16 | pin | regen_image | 9.0 | turkey meatballs in tomato sauce not over rice |
| W9-17 | pin | regen_image | 9.0 | not chicken and rice in one pan |
| W9-18 | pin | regen_image | 9.0 | broccoli, not beef and broccoli stir-fry |
| W9-19 | pin | regen | -- | should be stock image not template |
| W9-20 | pin | regen_image | -- | should be stock image not template |
| W9-21 | pin | regen_image | -- | should be stock image not template |
| W9-22 | pin | regen_image | -- | should be stock image not template |
| W9-23 | pin | regen_image | -- | should be stock image not template |
| W9-24 | pin | regen_image | -- | should be stock image not template |
| W9-25 | pin | regen_image | -- | should be stock image not template |
| W9-26 | pin | regen_image | -- | should be stock image not template |
| W9-27 | pin | regen_image | 6.5 | flowers, not pasta primavera |
| W9-28 | pin | approved | -- | -- |

**Quality gate stats from initial gen:** Stock: 17 ranked, 0 retried, 0 fell back to AI. AI: 0 validated, 0 regenerated, 0 low_confidence.

*Notable: Zero retries and zero AI fallbacks despite 7 wrong-food-subject failures. This means the quality gate (score >= 6.5) was met in every case -- Haiku consistently scored wrong-food images above 6.5.*

### Regen Run Stats (from logs)

- **Date:** 2026-02-23 21:39-21:44
- **Duration:** ~5 minutes
- **Total requests:** 21
- **Blog regens (all failed):** 6
- **Pin regens (all technically succeeded):** 15
- **Total API cost:** $0.2487
- **Average time per pin regen:** ~17 seconds
- **Retries needed:** 1 (W9-27, initial best score 3.0, retry got 8.0)

### Cross-Reference: Inconsistencies Between Research Documents

1. The regen flow analysis states that the blog regen bug was a key lookup mismatch (`blog_results.get(item_id)` returning None), but the log messages show "Blog regen not supported" which matches the `regen_copy` check path, not the data lookup path. The actual code path that triggered is ambiguous from the logs alone. The `fd655ea` commit likely clarified this.

2. The initial flow analysis lists the quality gate threshold as >= 6.5 for stock ranking, but the quality gate stats show "0 retried" despite multiple wrong-food images. This confirms that Haiku scored all wrong-food images above 6.5 -- the threshold is not the problem; the ranking model's food identification capability is.

3. The prior agent analysis (`regen-quality-improvements.md`) proposes the multi-query and ranking feedback fixes but does not address the Tier 3 over-assignment issue, which by count was the single largest failure category (8 of 21 failures).
