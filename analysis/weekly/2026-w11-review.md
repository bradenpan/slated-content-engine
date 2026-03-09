# Weekly Performance Analysis — Week 10, March 4–10, 2026

---

## ⚠️ Data Integrity Notices (Read Before Any Analysis)

**Notice 1 — Impression collapse vs. last week.** This week shows 8 total impressions across 28 pins. Last week showed 37 impressions across 24 pins. That is a **-78% decline in raw impressions** week-over-week. Before treating this as a performance signal, two alternative explanations must be considered: (a) the 37 impressions from last week were partially attributable to the tail of Week 9 pins still accumulating, and this week's 28 new pins simply haven't had time to index; or (b) there is a data pipeline issue — impressions may not yet be fully populated for pins posted March 4–10. **This ambiguity cannot be resolved from the dataset alone.** The impression collapse is flagged as a priority operational check before drawing conclusions.

**Notice 2 — All 28 pins show `"status": "scheduled"` and all have empty `board_id` fields.** Every single pin in the Week 10 content plan has `"board_id": ""`. Last week, 4 pins had empty board IDs and were flagged as a concern. This week, the problem is universal across all 28 pins. If board assignment failed at publishing for all Week 10 pins, these pins are unclassified and Pinterest cannot properly categorize or distribute them. This is the most likely explanation for the near-zero impression count and is an **urgent operational issue requiring immediate verification in the Pinterest dashboard.**

**Notice 3 — Three pins link to `goslated.com/blog` (homepage) instead of a specific blog post.** W10-16 (`kid friendly dinners` / hidden veggie mac and cheese), W10-18 (`hellofresh alternative`), and W10-23 (`easy dinner ideas` / lemon herb chicken) all have `"blog_slug": ""` and link to the blog root. These pins cannot drive meaningful outbound clicks or CTA conversions. This is a content production error, not a performance issue.

**Notice 4 — Content memory shows channel filter as `tiktok`.** The content memory summary was generated with `channel filter: tiktok`, which means it reports zero history for Pinterest. This is a pipeline configuration error. The content memory is not providing useful Pinterest-specific context this week. Keyword saturation and topic coverage analysis below is based on the content plan data directly rather than the memory summary.

**Notice 5 — Engagement targets are not applicable.** This is Week 2 of a new Pinterest account (Week 10 of the overall project, but Week 2 of active posting). The >2% save rate and >0.5% outbound CTR targets are Month 3+ benchmarks. Zero saves and zero outbound clicks are expected at this stage. The meaningful questions are: (a) are pins being indexed at all, and (b) are operational issues suppressing even the minimal distribution a new account should receive?

---

## Key Metrics Summary

| Metric | This Week | Last Week | Change |
|--------|-----------|-----------|--------|
| Impressions | 8 | 37 | −78% |
| Saves | 0 | 0 | — |
| Save Rate | 0.0% | 0.0% | — |
| Outbound Clicks | 0 | 0 | — |
| Outbound Click Rate | 0.0% | 0.0% | — |
| Pin Clicks | 0 | 0 | — |
| Pins Posted | 28 scheduled (delivery unconfirmed) | 24 | +4 pins |
| Impressions per Pin | 0.29 | 1.54 | −81% |

**Rolling 4-week average impressions:** 11 (per account-level trends data). This week's 8 is below the rolling average, continuing a pattern where the account has not yet established a rising impression baseline.

**vs. Targets:** Save rate and CTR targets are not applicable at Week 2. The only meaningful benchmark at this stage is whether pins are receiving *any* distribution signal. At 0.29 impressions per pin this week (down from 1.54 last week), the answer is: minimally, and declining. This warrants investigation before attributing to normal new-account noise.

---

## Top 5 Performing Pins

**Cannot be reported.** The minimum impression threshold for save-rate analysis is 100 impressions per pin. No pin in the Week 10 dataset approaches this threshold. All saves are 0. Ranking pins by save rate is not meaningful.

**What the data does show at a cluster level:** The 8 total impressions this week are distributed as follows by the available dimensional breakdowns:

- **By pin type:** Secondary pins (7 pins, all from Week 9 carryover) received 7 of the 8 impressions. Recipe-pull pins received 1. Primary pins received 0. Fresh-treatment pins received 0.
- **By image source:** Unsplash pins (5 pins) received 5 impressions. AI-generated pins (20 pins) received 1 impression. Pexels (1 pin) received 1 impression. Template-only (2 pins) received 1 impression.
- **By content type:** The 8 pins with null/empty content type received all 8 impressions. All properly-typed content types (weekly-plan, guide, recipe, listicle) received 0.

**Critical interpretation:** The 8 impressions appear to be coming from Week 9 pins (secondary pin type, Unsplash images, null content type) that are still accumulating impressions from last week's posting — not from new Week 10 content. This is consistent with the board_id issue: if Week 10 pins were not properly published or classified, they would show 0 impressions while Week 9 pins continue their slow accumulation.

---

## Bottom 5 Performing Pins

**Cannot be reported** for the same reasons stated above. All pins have 0 saves, 0 clicks, and impressions below any statistically meaningful threshold.

**Structural flags worth noting from the content plan:**

| Pin | Issue |
|-----|-------|
| W10-16 | Links to `goslated.com/blog` (no slug). Content production error — pin cannot convert. |
| W10-18 | Links to `goslated.com/blog` (no slug). Content production error. |
| W10-23 | Links to `goslated.com/blog` (no slug). Content production error. |
| W10-25 | Template-only image source (`"image_id": ""`). Pattern from Week 9 suggests template-only pins may receive suppressed distribution. |
| W10-13 | Template-only image source (`"image_id": ""`). Same concern. |

Additionally, W9-27 (Spring Pasta Primavera) links to `goslated.com/blog/shrimp-avocado-tacos` — a URL mismatch flagged in last week's analysis that has not been corrected. This pin remains live with a mismatched destination.

---

## Pillar Performance

| Pillar | Pins This Week | Impressions | Save Rate | CTR | Trend vs. Last Week |
|--------|---------------|-------------|-----------|-----|---------------------|
| P1: Your Whole Week, Planned | 8 | 0.0 | 0.0% | 0.0% | ↓ (was 12 impr. last week — but those were W9 P1 pins) |
| P2: Everyone Eats, Nobody Argues | 6 | 0.0 | 0.0% | 0.0% | Flat (0 last week) |
| P3: Dinner, Decided | 3 | 0 | 0.0% | 0.0% | Flat (0 last week) |
| P4: Smarter Than a Meal Kit | 2 | 0.0 | 0.0% | 0.0% | Flat (0 last week) |
| P5: Your Kitchen, Your Rules | 1 | 0 | 0.0% | 0.0% | Flat (0 last week) |
| Unknown/null pillar | 8 | 8 | 0.0% | 0.0% | Carryover from W9 |

**Pillar ranking by save rate:** Cannot be ranked — all save rates are 0.0%.

**Pillar mix this week (by pin count, excluding null-pillar W9 carryover):**

| Pillar | This Week % (of 20 assigned pins) | Target Range | Gap |
|--------|-----------------------------------|--------------|-----|
| P1 | 40% (8/20) | 32–36% | +4–8 pp over target |
| P2 | 30% (6/20) | 25–29% | +1–5 pp over target |
| P3 | 15% (3/20) | 18–21% | −3–6 pp under target |
| P4 | 10% (2/20) | 7–10% | Within range |
| P5 | 5% (1/20) | 14–18% | −9–13 pp under target |

**Pillar mix observation:** P5 (Your Kitchen, Your Rules) is significantly under-represented at 5% vs. its 14–18% target. The strategy calls for 4–5 P5 pins per week covering dietary and appliance-specific content. This week delivered only 1 (W10-06, slow cooker white bean kale soup, and its fresh treatment W10-21). P3 is also slightly under at 15% vs. 18–21%. P1 and P2 are both slightly over. This is a content generation gap, not a performance issue — the pipeline is not producing enough P5 content.

---

## Content Type Performance

| Template | Pins | Impressions | Save Rate | CTR | Notes |
|----------|------|-------------|-----------|-----|-------|
| recipe-pin | 11 | 1.0 | 0.0% | 0.0% | 0.09 impr/pin — lowest ratio |
| tip-pin | 7 | 3.0 | 0.0% | 0.0% | 0.43 impr/pin — best ratio this week |
| listicle-pin | 6 | 3 | 0.0% | 0.0% | 0.50 impr/pin — tied for best |
| infographic-pin | 2 | 1 | 0.0% | 0.0% | 0.50 impr/pin; both use template-only images |
| problem-solution-pin | 2 | 0.0 | 0.0% | 0.0% | 0 impr/pin — two consecutive weeks of zero impressions |

**Honest interpretation:** The impression differentials are too small (1–3 impressions per template type) to draw conclusions about template effectiveness. The only pattern worth flagging is that problem-solution-pin has now shown 0 impressions across 4 pins over 2 consecutive weeks. Both weeks, these pins used AI-generated or template-only images and targeted conversion-layer content. Whether this reflects the template, the image source, the board classification, or the board_id failure is not determinable from this data alone.

---

## Board Performance

| Board | Pins This Week | Impressions | Save Rate | CTR | Notes |
|-------|---------------|-------------|-----------|-----|-------|
| Meal Planning & Grocery Tips | 3 | 2.0 | 0.0% | 0.0% | 0.67 impr/pin |
| Healthy Family Dinner Recipes | 2 | 2 | 0.0% | 0.0% | 1.0 impr/pin — best ratio |
| Family Dinner Ideas Even Picky Eaters Love | 5 | 1.0 | 0.0% | 0.0% | 0.20 impr/pin |
| Better Than a Meal Kit | 3 | 1.0 | 0.0% | 0.0% | 0.33 impr/pin |
| Air Fryer & Instant Pot Dinner Recipes | 1 | 1 | 0.0% | 0.0% | 1.0 impr/pin |
| Family Meal Planning Strategies | 3 | 1 | 0.0% | 0.0% | 0.33 impr/pin |
| Weekly Meal Plans & Meal Planning Tips | 2 | 0 | 0.0% | 0.0% | ↓ Had 5 impressions last week — now 0 |
| Quick Weeknight Dinner Recipes | 4 | 0.0 | 0.0% | 0.0% | 0 for second week |
| Gluten-Free Dinner Ideas | 1 | 0 | 0.0% | 0.0% | New board, 1 pin |
| Easy Dinner Ideas for Families | 4 | 0 | 0.0% | 0.0% | ↓ Had 5 impressions last week — now 0 |

**Board observations:**

1. **"Weekly Meal Plans & Meal Planning Tips" dropped from 5 impressions (last week's top board) to 0.** This is the most important board for Slated's differentiated content (P1). The drop is likely attributable to the board_id failure — Week 10 pins assigned to this board may not have been published with the board association intact.

2. **"Easy Dinner Ideas for Families" dropped from 5 impressions to 0.** Same concern — this was last week's second-best board and now shows nothing.

3. **"Quick Weeknight Dinner Recipes" has shown 0 impressions for 2 consecutive weeks** across 9 total pins (5 last week + 4 this week). This board may have a classification or indexing issue independent of the board_id problem, or the keyword competition on this board is simply too high for a new account to break through yet.

4. **The boards showing any impressions this week (Healthy Family Dinner Recipes, Air Fryer & Instant Pot, etc.) are likely receiving carryover impressions from Week 9 secondary pins**, not new Week 10 content.

---

## Keyword Insights

**Impression leaders this week (not "top performers" — all save rates are 0):**

| Primary Keyword | Pins | Impressions | Impr/Pin | Save Rate |
|-----------------|------|-------------|----------|-----------|
| 30 minute meals | 2 | 1 | 0.50 | 0.0% |
| 15 minute meals | 1 | 1 | 1.00 | 0.0% |
| dinner ideas for family | 1 | 1 | 1.00 | 0.0% |
| meal kit alternative | 2 | 1 | 0.50 | 0.0% |
| air fryer dinner recipes | 1 | 1 | 1.00 | 0.0% |
| high protein dinner recipes | 1 | 1 | 1.00 | 0.0% |
| spring dinner ideas | 2 | 1.0 | 0.50 | 0.0% |
| picky eater meal ideas | 1 | 1 | 1.00 | 0.0% |
| weekly meal plan | 1 | 0 | 0.00 | 0.0% |
| easy weeknight dinners | 2 | 0 | 0.00 | 0.0% |
| easy dinner ideas | 1 | 0 | 0.00 | 0.0% |
| meal planning | 1 | 0 | 0.00 | 0.0% |
| hellofresh alternative | 1 | 0.0 | 0.00 | 0.0% |
| what to cook for dinner | 1 | 0.0 | 0.00 | 0.0% |

**Honest interpretation:** The impression differentials are within noise range (0–1 impressions per keyword). No keyword conclusions can be drawn. The most notable finding is that "weekly meal plan" — which showed 5 impressions last week and was the account's strongest keyword signal — dropped to 0 this week. This is consistent with the board_id failure hypothesis: last week's "weekly meal plan" pin (W9, secondary type) had accumulated impressions, while this week's W10-01 ("Weekly Meal Plan — 5 Light Spring Dinners") may not have been properly published.

**New keywords introduced this week (not previously tested):**
- `