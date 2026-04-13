# Weekly Performance Analysis — Week 16, April 8–14, 2026

---

## ⚠️ Data Quality & Context Notices

**Notice 1 — Impression recovery this week.** Total impressions rose from 67 (last week) to 291 this week — a 334% increase. This is the largest single-week impression gain recorded in the account. However, context is critical: last week's 67 was the account's lowest recorded total and likely reflected a pipeline/indexing failure (the board_id blank issue flagged in prior analyses). This week's 291 is more plausibly a partial recovery than a genuine growth signal. The rolling 4-week average is 184 impressions; this week's 291 is 58% above that average. Interpret with caution — one week of recovery does not confirm the pipeline is healthy.

**Notice 2 — Board ID field remains blank on all W13–W15 pins.** Every pin in the W13, W14, and W15 content plans shows `board_id: ""`. This is the same failure mode flagged in Weeks 12, 13, 14, and 15. The impression collapse last week and partial recovery this week are both consistent with this failure mode causing inconsistent posting/indexing. **This is the account's most urgent operational issue. It has been flagged for five consecutive weeks without resolution. Until board_id assignment is confirmed working, all performance data is suspect.**

**Notice 3 — W15 pins are in distribution lag.** The W15 content plan (April 8–14) represents this week's new posts. Per the established distribution lag pattern, W15 pins will not appear in top/bottom performers for 1–2 more weeks. This week's performance data reflects primarily W9–W12 era pins.

**Notice 4 — Treatment tracker is in critical violation.** The content memory shows 22 URLs now at or above the 5-treatment limit — up from 18 last week. An additional 30+ URLs are at 3–4 treatments (approaching limit). The W15 content plan includes fresh treatments for URLs already at or near limit. Specifically: `sheet-pan-chicken-drumsticks-roasted-vegetables` (W15-12, treatment 3, now at 6/5 — AT LIMIT), `high-protein-turkey-meatball-bowls` (W15-14, treatment 2, now at 6/5 — AT LIMIT), `stop-being-the-only-one-who-decides-dinner` (W15-01 and W15-15, treatments 1 and 1 of the same URL — possible double-treatment in a single week), `weekly-plan-summer-grilling-dinners` (W15-02, W15-05, W15-13, W15-18, W15-26 — five pins linking to the same URL in a single week, now at 9/5 AT LIMIT). **The pipeline is systematically ignoring treatment limits. This compounds suppression risk every week it continues.**

**Notice 5 — `weekly-plan-summer-grilling-dinners` over-treated in W15.** Five W15 pins link to this single URL: W15-02 (plan-level), W15-05 (recipe-pull), W15-13 (recipe-pull), W15-18 (recipe-pull), W15-26 (recipe-pull). This URL is now at 9/5 treatments — nearly double the limit. The strategy explicitly states "Maximum 5 pin treatments per URL in the first 60 days." This is a critical execution failure.

**Notice 6 — `weekly-plan-5-quick-one-pan-meals` similarly over-treated.** W15 pins W15-08, W15-10, W15-16, W15-20, W15-28 all link to this URL — five pins in a single week. Combined with prior treatments, this URL is now at 7/5 treatments AT LIMIT.

**Notice 7 — "Spring dinner ideas" keyword still in pipeline.** 3 pins this week, 0 impressions. Lifetime: 58+ uses, 0 saves, 0 outbound clicks. This keyword has been flagged for removal in every analysis since Week 12. It remains active. **Remove immediately.**

**Notice 8 — Blog URL error: unresolved for sixth consecutive week.** Pins linking to `goslated.com/blog` (homepage) with empty `blog_slug` fields cannot convert. First flagged Week 11.

**Notice 9 — No pin meets the 100-impression threshold for statistically valid rate analysis.** Top performer W10-04 had 136 impressions this week — the first time any pin has crossed the 100-impression threshold in the account's history. This is the only pin where rate metrics carry any statistical weight, and even at 136 impressions the sample is small. All other pins' rates are directional signals only.

---

## Key Metrics Summary

| Metric | This Week (W16 period) | Last Week (W15 period) | Change |
|--------|------------------------|------------------------|--------|
| Impressions | 291 | 67 | **+334%** |
| Saves | 1 | 0 | +1 (absolute) |
| Save Rate | 0.34% | 0.0% | +0.34 pp |
| Outbound Clicks | 12 | 3 | **+300%** |
| Outbound Click Rate | 4.12% | 4.48% | −0.36 pp |
| Pin Clicks | 16 | 4 | +300% |
| New Pins Posted | 26 (W15 pins) | 28 (W14 pins) | −2 |
| Active Pins | 182 | 156 | +26 |
| Impressions per Active Pin | 1.60 | 0.43 | **+272%** |

**Rolling 4-week context:** The rolling 4-week average is 184 impressions. This week's 291 is 58% above the rolling average. Last week's 67 was 64% below it. The swing from −64% to +58% relative to the rolling average in a single week is anomalous and consistent with a pipeline failure last week partially resolving this week — not with organic growth.

**vs. Targets:** The account is in Month 3, when the strategy's >2% save rate and >0.5% outbound CTR targets apply. Save rate: 0.34% vs. 2.0% target — well below. Outbound CTR: 4.12% vs. 0.5% target — exceeds on paper, but this is driven almost entirely by a single pin (W10-04: 136 impressions, 9 outbound clicks = 6.6% CTR). Remove W10-04 and the remaining 181 active pins generated 3 outbound clicks on 155 impressions (1.9% CTR — still driven by 2–3 pins). Portfolio-level save rate and outbound click rate are not meaningful at this impression volume.

**The impression recovery is the dominant story this week.** The 334% increase is real but likely reflects pipeline normalization after last week's collapse, not organic growth. The underlying account health remains unchanged.

---

## Top 5 Performing Pins

*W10-04 is the only pin meeting the 100-impression minimum threshold for rate analysis. All other rates are directional signals only.*

| Rank | Pin | Pillar | Template | Impressions | Saves | Outbound Clicks | Save Rate | CTR |
|------|-----|--------|----------|-------------|-------|-----------------|-----------|-----|
| 1 | W10-04: Easy Dinners Kids Will Eat — Sheet Pan Chicken Drumsticks | P2 | recipe-pin | 136 | 1 | 9 | **0.74%** | **6.62%** |
| 2 | W12-02: High Protein Dinner Recipes — Sheet Pan Chicken & Asparagus | P5 | recipe-pin | 19 | 0 | 1 | 0.0% | 5.26% |
| 3 | W11-10: Honey Garlic Pork Stir Fry — 25-Minute Family Dinner | P1 | recipe-pin | 18 | 0 | 1 | 0.0% | 5.56% |
| 4 | W9-16: High Protein Turkey Meatball Bowls — Healthy Dinner Kids Actually Eat | P5 | recipe-pin | 13 | 0 | 0 | 0.0%* | 0.0% |
| 5 | W10-11: Simple Dinner Recipe: One-Pan Honey Mustard Pork Tenderloin | P3 | recipe-pin | 12 | 0 | 1 | 0.0% | 8.33% |

*W9-16's data shows a `save_rate` of 0.017094 in the raw data — this appears to be a lifetime figure carried forward in the data structure, not a this-week figure. This week's saves for W9-16 are 0.*

**Why W10-04 leads — for the fourth consecutive week.** W10-04 ("Easy Dinners Kids Will Eat — Sheet Pan Chicken Drumsticks") has now been the #1 performer for four straight weeks. This week: 136 impressions, 1 save (0.74% save rate), 9 outbound clicks (6.62% CTR). This is the first week any pin has crossed 100 impressions, making W10-04's metrics the account's first statistically meaningful rate data. The keyword "easy dinners kids will eat" and the board "Family Dinner Ideas Even Picky Eaters Love" are the account's only confirmed engagement surface.

**W10-04 impression trend:** The four-week impression trend for W10-04 is: [unknown] → 64 (W14 period) → 19 (W15 period) → 136 (W16 period). The spike from 19 to 136 is likely a function of last week's impression collapse recovering, not genuine growth. The pin appears to be in a distribution cycle — it will likely decay again. The 0.74% save rate is below the 2% target but is the account's strongest confirmed rate signal.

**W10-04 outbound click rate (6.62%) is the account's most reliable conversion signal.** 9 outbound clicks on 136 impressions is meaningful. The "easy dinners kids will eat" + "Family Dinner Ideas Even Picky Eaters Love" board combination is driving users to click through to the blog. This validates the P2 keyword and board pairing.

**Why W12-02 and W11-10 appear at ranks 2–3.** Both are recipe-pins with 18–19 impressions and 1 outbound click each. The CTRs (5.26% and 5.56%) are directional signals only at these impression levels. Both are W11–W12 era pins consistent with the distribution lag pattern.

**Why W9-16 holds rank 4 with 0 engagement.** W9-16 (High Protein Turkey Meatball Bowls) has now appeared in the top 5 for multiple consecutive weeks on impression volume alone, with 0 saves and 0 outbound clicks this week. The pin is receiving distribution but not converting. This is a concern for the "high protein dinner recipes" keyword — 8 pins, 36 impressions, 0 saves this week.

**Pattern across top 5:** All top performers are W9–W12 era pins. Zero W13, W14, or W15 pins appear in the top 5. This is consistent with distribution lag, but the board_id failure mode for W13+ pins remains unresolved and may be suppressing newer content entirely.

---

## Bottom 5 Performing Pins

*All bottom performers have 1 impression each. With 291 total impressions across 182 active pins, approximately 120+ pins generated 0 impressions this week. The "bottom 5" are selected from the provided data as representative of structural failure patterns.*

| Rank | Pin | Pillar | Template | Impressions | Saves | Primary Issue |
|------|-----|--------|----------|-------------|-------|---------------|
| 1 | W12-10: Gluten Free Dinner Ideas: Lemon Herb Baked Cod | P5 | recipe-pin | 1 | 0 | Distribution lag; "gluten free dinner ideas": 4 pins, 1 impression total this week |
| 2 | W12-15: What to Make for Dinner Tonight — Smashed Burger Tacos | P3 | recipe-pin | 1 | 0 | Distribution lag; URL `smashed-burger-tacos` now at 4/5 treatments approaching limit |
| 3 | W12-18: Easy Weeknight Dinners — Sesame Ginger Noodles with Edamame | P1 | recipe-pin (recipe-pull) | 1 | 0 | Distribution lag; recipe-pull pin type: 39 impressions across 48 pins (0.81/pin) |
| 4 | W12-20: The Best HelloFresh Alternative — A Flexible Home Cooking Plan | P4 | problem-solution-pin | 1 | 0 | Distribution lag + structural: problem-solution-pin template: 4 impressions across 15 pins (0.27/pin) |
| 5 | W12-24: Easy Dinners Kids Will Eat — Teriyaki Chicken Rice Bowls | P2 | recipe-pin | 1 | 0 | Distribution lag; `teriyaki-chicken-rice-bowls` URL at 6/5 treatments AT LIMIT — near-duplicate suppression risk |

**Pattern:** All 5 bottom performers are W12 era pins with 1 impression each. Distribution lag is the primary explanation. However, structural issues compound in each case: the problem-solution-pin template continues to generate near-zero distribution (4 impressions across 15 pins = 0.27/pin), recipe-pull pins underperform primary pins (39 impressions across 48 pins vs. 245 impressions across 90 primary pins), and over-treated URLs face near-duplicate suppression.

**The more concerning story:** With 291 total impressions across 182 active pins, the average is 1.60 impressions/pin/week. The median is almost certainly 0. The portfolio is not distributing at scale. This is either a pipeline failure (board_id blank → pins not correctly posted/classified), a domain quality issue, or both.

---

## Pillar Performance

| Pillar | Pins | Impressions | Saves | Save Rate | Outbound CTR | Trend vs. Last Week |
|--------|------|-------------|-------|-----------|--------------|---------------------|
| P1: Your Whole Week, Planned | 62 | 39 | 0 | 0.0% | 2.6% | ↑ Up from 13 impr (+200%) |
| P2: Everyone Eats, Nobody Argues | 39 | 159 | 1 | **0.63%** | **5.66%** | ↑ Up from 26 impr (+512%) — driven almost entirely by W10-04 |
| P3: Dinner, Decided | 36 | 46 | 0 | 0.0% | 2.2% | ↑ Up from 13 impr (+254%) |
| P4: Smarter Than a Meal Kit | 14 | 3 | 0 | 0.0% | 0.0% | ↑ Up from 2 impr (marginal) |
| P5: Your Kitchen, Your Rules | 22 | 42 | 0 | 0.0% | 2.4% | ↑ Up from 12 impr (+250%) |

**Pillar ranking by save rate:** P2 (0.63%) > P1/P3/P4/P5 (all 0.0%)

**Pillar ranking by outbound CTR:** P2 (5.66%) > P1 (2.6%) > P5 (2.4%) > P3 (2.2%) > P4 (0.0%)

**Critical caveat on all pillar improvements:** Every pillar's impression increase this week is proportional to last week's collapse and recovery. P2's apparent dominance (159 impressions, 54.6% of all account impressions) is almost entirely attributable to a single pin: W10-04 (136 of P2's 159 impressions). Remove W10-04 and P2 has 23 impressions — comparable to P3 (46) and P5 (42). The pillar-level data is not meaningful without acknowledging this concentration.

**P1 structural concern persists.** 62 pins, 39 impressions, 0 saves, 0 out