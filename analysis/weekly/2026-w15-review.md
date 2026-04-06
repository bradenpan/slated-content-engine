# Weekly Performance Analysis — Week 15, April 1–7, 2026

---

## ⚠️ Data Quality & Context Notices

**Notice 1 — Severe impression collapse this week.** Total impressions dropped from 193 (last week) to 67 this week — a 65% decline in a single period. This is the most significant single-week drop recorded in the account. The cause is not yet established. Possible explanations include: (a) distribution lag for recently-posted W14 pins not yet indexed, (b) W10-era pins that were driving the bulk of last week's impressions cycling out of their distribution windows, or (c) a posting/indexing failure related to the persistent `board_id: ""` issue. **This requires immediate investigation before attributing to content quality.**

**Notice 2 — Board ID field remains blank on all W14 pins.** Every pin in the W14 content plan shows `board_id: ""`. This is the same failure mode flagged in Weeks 12, 13, and 14. Last week's analysis confirmed W11 pins with blank board IDs generated near-zero impressions. If the pipeline requires a board ID to correctly assign pins, W14 pins may be unposted or misclassified. The impression collapse this week is consistent with this failure mode. **Verify W14 posting status before any content interpretation.**

**Notice 3 — Zero saves this week.** The account recorded 0 saves on 67 impressions. Last week: 1 save on 193 impressions. The prior week: 2 saves on 152 impressions. The save trend is: 2 → 1 → 0 over three consecutive weeks. This is a genuine declining trend, not noise. However, with 67 total impressions, the absolute sample is too small to distinguish between "the audience isn't saving" and "the right audience isn't seeing the pins." The impression collapse is the more urgent diagnostic question.

**Notice 4 — Treatment tracker is in critical and worsening violation.** The content memory shows 18 URLs now at or above the 5-treatment limit — up from 15 last week. The W14 content plan includes fresh treatments for URLs already at limit. Specifically: `hellofresh-alternative-why-families-switch-custom-meal-planning` (W14-28, treatment 4, now at 5/5 AT LIMIT), `lemon-garlic-butter-shrimp-pasta` (W14-08, treatment 3, now at 3/5 — approaching), `smashed-burger-tacos` (W14-27, treatment 3, now at 3/5). The 9 most-treated plan post URLs (weekly-plan-5-easy-weeknight-meals at 18/5; shrimp-avocado-tacos at 12/5; multiple others at 10/5) are generating near-duplicate suppression risk that compounds every week this is unaddressed. **This is the highest-priority operational issue in the account. It has appeared in every weekly analysis and has not been resolved.**

**Notice 5 — Blog URL error: unresolved for fifth consecutive week.** Pins linking to `goslated.com/blog` (homepage) with empty `blog_slug` fields cannot convert even if they receive impressions. This issue was first flagged in Week 11 and has not been corrected.

**Notice 6 — "Spring dinner ideas" keyword confirmed dead, still appearing in pipeline.** Content memory shows 58 lifetime uses, 0 saves, 0 outbound clicks. This week: 3 pins, 0 impressions. This keyword should be removed from the pipeline's keyword list immediately. It has been flagged in every analysis since Week 12.

**Notice 7 — W14 pins are in distribution lag.** The W14 content plan (April 1–7) represents this week's new posts. Per the established distribution lag pattern, W14 pins will not appear in top/bottom performers for 1–2 more weeks. This week's performance data reflects W10–W12 era pins primarily.

**Notice 8 — No 100-impression threshold met by any individual pin.** Top performer W10-04 had 19 impressions this week — down from 64 last week. No pin meets the minimum threshold for statistically valid rate analysis. All rates cited are directional signals only.

---

## Key Metrics Summary

| Metric | This Week (W15 period) | Last Week (W14 period) | Change |
|--------|------------------------|------------------------|--------|
| Impressions | 67 | 193 | **−65%** |
| Saves | 0 | 1 | −100% |
| Save Rate | 0.0% | 0.52% | −0.52 pp |
| Outbound Clicks | 3 | 6 | −50% |
| Outbound Click Rate | 4.48% | 3.11% | +1.37 pp |
| Pin Clicks | 4 | 13 | −69% |
| New Pins Posted | 28 (W14 pins) | 28 (W13 pins) | 0 |
| Active Pins | 156 | 132 | +18% |
| Impressions per Active Pin | 0.43 | 1.46 | **−71%** |

**Rolling 4-week average impressions:** 137 (per content memory). This week's 67 is 51% *below* the rolling average — a significant negative departure. Last week's 193 was 41% *above* the rolling average. The swing from +41% to −51% in a single week is anomalous and warrants investigation before drawing content conclusions.

**vs. Targets:** The account is in Month 3, when the strategy's >2% save rate and >0.5% outbound CTR targets apply. Save rate: 0.0% vs. 2.0% target — well below. Outbound CTR: 4.48% vs. 0.5% target — exceeds on paper, but this figure is driven by 3 outbound clicks on 67 impressions, with 2 of those 3 clicks coming from a single pin (W10-04, 19 impressions, 2 outbound clicks). The outbound CTR "success" is a single-pin artifact. Remove W10-04 and the remaining 155 active pins generated 1 outbound click on 48 impressions (2.1% CTR — still from one pin, W10-11 or similar). The portfolio-level signal is not meaningful at this impression volume.

**The impression collapse is the dominant story this week.** Every other metric is downstream of it. Interpretation requires resolving whether this is a pipeline failure (board_id blank → pins not posting) or organic distribution decay (W10-era pins cycling out, W14 pins not yet indexed).

---

## Top 5 Performing Pins

*No pin meets the 100-impression minimum threshold for statistically valid rate analysis. Rankings are by raw engagement events and impression volume. All rates are directional only. Save rates shown in the data appear to be lifetime figures carried forward in the data structure, not this-week figures — all this-week saves are 0.*

| Rank | Pin | Pillar | Template | Impressions (this week) | Saves (this week) | Outbound Clicks | CTR |
|------|-----|--------|----------|------------------------|-------------------|-----------------|-----|
| 1 | W10-04: Easy Dinners Kids Will Eat — Sheet Pan Chicken Drumsticks | P2 | recipe-pin | 19 | 0 | 2 | 10.5% |
| 2 | W9-16: High Protein Turkey Meatball Bowls — Healthy Dinner Kids Actually Eat | P5 | recipe-pin | 12 | 0 | 0 | 0.0% |
| 3 | W10-11: Simple Dinner Recipe: One-Pan Honey Mustard Pork Tenderloin | P3 | recipe-pin | 6 | 0 | 0 | 0.0% |
| 4 | W10-02: Dinner Ideas for Picky Eaters — How a Family Vote System Ends the Argument | P2 | problem-solution-pin | 4 | 0 | 0 | 0.0% |
| 5 | W9-12: 15-Minute Teriyaki Salmon Bowls — Quick Weeknight Dinners That Deliver | P3 | recipe-pin | 3 | 0 | 0 | 0.0% |

**Why W10-04 leads — again.** W10-04 ("Easy Dinners Kids Will Eat — Sheet Pan Chicken Drumsticks") has now appeared as the #1 performer for three consecutive weeks. This week: 19 impressions, 2 outbound clicks (10.5% CTR). Last week: 64 impressions, 6 outbound clicks (9.38% CTR). The pin is decaying in impression volume (64 → 19) but maintaining its click-through behavior — users who see it are still clicking through. This is the account's most durable signal. The "easy dinners kids will eat" keyword and the "Family Dinner Ideas Even Picky Eaters Love" board continue to be the account's only consistent engagement surface. *Caveat: 19 impressions. Directional only.*

**W10-04 impression decay is notable.** Three-week impression trend for W10-04: [unknown W13 period] → 64 (W14 period) → 19 (W15 period). This is consistent with a pin cycling through its initial distribution window. If this trend continues, the account's primary engagement driver will lose reach within 1–2 more weeks. No replacement performer is visible in the current data.

**Why W9-16 holds rank 2 with 0 engagement.** W9-16 generated 12 impressions this week with 0 saves and 0 outbound clicks. Last week: 35 impressions, 0 saves. The week before: 1 save. W9-16's save signal has not recurred in two consecutive weeks. The pin is still receiving distribution (12 impressions) but the save-intent audience is not present in this week's sample. The P5 declining trend continues.

**Why W10-02 appears at rank 4.** W10-02 ("Dinner Ideas for Picky Eaters — How a Family Vote System Ends the Argument") is a guide/problem-solution pin that generated 4 impressions this week. This is notable because problem-solution pins as a template have been near-zero across the portfolio (6 impressions across 11 pins in the template breakdown). W10-02 is the only problem-solution pin generating any distribution. Its presence in the top 5 is more a function of the overall impression collapse than strong performance.

**Pattern across top 5:** All top performers are W9–W10 era pins. Zero W11, W12, W13, or W14 pins appear in the top 5. This is consistent with distribution lag, but also consistent with the board_id failure mode suppressing newer pins entirely.

---

## Bottom 5 Performing Pins

*All bottom performers have 1 impression each. Given the total account impressions of 67 across 156 active pins, the majority of the portfolio (approximately 100+ pins) generated 0 impressions this week. The "bottom 5" selected from the data represent W11–W12 era pins, consistent with the lag pattern.*

| Rank | Pin | Pillar | Template | Impressions | Saves | Primary Issue |
|------|-----|--------|----------|-------------|-------|---------------|
| 1 | W11-15: Ground Turkey Taco Skillet — What to Cook for Dinner in 20 Minutes | P3 | recipe-pin | 1 | 0 | Distribution lag; "what to cook for dinner" keyword: 5 pins, 1 impression this week |
| 2 | W11-26: Toddler Dinner Ideas: Mini Turkey Taco Bowls | P2 | tip-pin | 1 | 0 | Distribution lag; tip-pin template: 4 impressions across 32 pins this week; treatment 4 of a URL approaching limit |
| 3 | W12-06: Kid Friendly Dinners — Teriyaki Chicken Rice Bowls | P2 | recipe-pin | 1 | 0 | Distribution lag; "kid friendly dinners" keyword: 7 pins, 1 impression this week |
| 4 | W12-12: Dinner Ideas for Picky Eaters: 3-Step System | P2 | infographic-pin | 1 | 0 | Distribution lag; template-sourced image; infographic-pin: 2 impressions across 7 pins |
| 5 | W12-21: Easy Dinner Ideas for Families — Honey Sriracha Salmon Bowls | P1 | recipe-pin | 1 | 0 | Distribution lag; recipe-pull pin type: 9 impressions across 42 pins (0.21/pin this week) |

**Pattern:** All 5 bottom performers are W11–W12 era pins with 1 impression each. Distribution lag is the primary explanation for all five. However, structural issues compound in each case: the tip-pin template continues to underperform (4 impressions across 32 pins = 0.13/pin), recipe-pull pins are generating minimal distribution (9 impressions across 42 pins = 0.21/pin), and the infographic-pin template with template-sourced images shows near-zero reach.

**The more concerning bottom-of-portfolio story:** With 67 total impressions across 156 active pins, approximately 100 pins generated 0 impressions this week. The portfolio is not distributing. This is either a pipeline failure, a domain quality issue, or both.

---

## Pillar Performance

| Pillar | Pins (portfolio) | Impressions | Saves | Save Rate | Outbound CTR | Trend vs. Last Week |
|--------|-----------------|-------------|-------|-----------|--------------|---------------------|
| P1: Your Whole Week, Planned | 54 | 13 | 0 | 0.0% | 0.0% | ↓ Down from 45 impr last week (−71%) |
| P2: Everyone Eats, Nobody Argues | 33 | 26 | 0 | 0.0% | 7.7% | ↓ Down from 70 impr last week (−63%); saves dropped from 1 to 0 |
| P3: Dinner, Decided | 31 | 13 | 0 | 0.0% | 7.7% | ↓ Down from 38 impr last week (−66%) |
| P4: Smarter Than a Meal Kit | 11 | 2 | 0 | 0.0% | 0.0% | ↔ Flat (was 1 impr last week — marginal change) |
| P5: Your Kitchen, Your Rules | 19 | 12 | 0 | 0.0% | 0.0% | ↓ Down from 38 impr last week (−68%) |

**Pillar ranking by save rate:** All pillars at 0.0% — no differentiation possible this week.

**Pillar ranking by outbound CTR:** P2 (7.7%) = P3 (7.7%) > P1/P4/P5 (0.0%). Both P2 and P3 CTRs are driven by 1–2 clicks each on very small impression bases. Not a meaningful signal.

**The uniform impression collapse across all pillars is diagnostic.** P1 dropped 71%, P2 dropped 63%, P3 dropped 66%, P5 dropped 68%. This is not a pillar-specific content quality issue — all pillars declined proportionally. This pattern is more consistent with a systemic distribution failure (pipeline issue, board_id problem, or domain-level suppression) than with content quality differences between pillars.

**P2 save rate collapse confirmed.** P2 generated 0 saves this week on 26 impressions. Last week: 1 save on 70 impressions. The week before: 1 save on 70 impressions (different save). P2's lifetime save rate is 1.4% (2 saves on 141 impressions), but both saves came from W10-04 — a single pin. The P2 "blue ocean" thesis has produced 2 lifetime saves from 1 pin. The remaining 32 P2 pins have generated 0 saves. This is a strategic concern, not just a weekly blip.

**P1 structural concern deepens.** 54 pins, 13 impressions, 0 saves, 0 outbound clicks. P1 is the largest pillar (35% of portfolio) and the strategy's primary differentiator. Lifetime: 112 pins, 119 impressions, 0 saves. The plan