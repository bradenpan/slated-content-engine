# Weekly Performance Analysis — Week 14, March 25–31, 2026

---

## ⚠️ Data Quality & Context Notices

**Notice 1 — Sample size remains sub-threshold for rate analysis.** 193 total impressions across 132 active pins. No individual pin meets the 100-impression minimum for statistically valid rate analysis. All save rates and CTRs cited are directional signals only.

**Notice 2 — This week's data reflects W10/W11 pins, not W13 pins.** The top performers (W10-04, W9-16, W10-11, W9-12, W9-17) are from Weeks 9–10. W13 pins (posted March 25–31) are in distribution lag and will not appear in top/bottom lists for 1–2 more weeks. Bottom performers (W11-era pins) reflect the same lag pattern.

**Notice 3 — Treatment tracker is in critical violation and worsening.** The content memory shows 15 URLs now at or above the 5-treatment limit, including the account's primary plan posts (weekly-plan-5-easy-weeknight-meals at 18/5; shrimp-avocado-tacos at 12/5; multiple plan posts at 10/5). W13's content plan includes fresh treatments for URLs already at limit — specifically W13-16 (one-pan-maple-dijon-salmon, treatment 4, now at 6/5 AT LIMIT) and W13-21 (turkey-meatballs-zucchini-noodles, treatment 4, now at 5/5 AT LIMIT). This is not a new flag — it has appeared in every weekly analysis. **This is the highest-priority operational issue in the account and it is not being resolved.** Pinterest's near-duplicate suppression is a real distribution risk that compounds weekly.

**Notice 4 — Board ID field is blank on all W13 pins.** Every pin in the W13 content plan has `board_id: ""`. This was the same failure mode that caused W11's near-zero impressions (confirmed in last week's analysis). If the posting pipeline requires a board ID to assign pins correctly, W13 pins may be misclassified or unposted. This needs immediate verification before W14 content posts.

**Notice 5 — Blog URL error persists for the fourth consecutive week.** W12-22 (`instant pot dinner ideas`) links to `goslated.com/blog` (homepage) with `blog_slug: ""`. W12-26 (`last minute dinner ideas`) has the same error. This issue has appeared in every weekly analysis and has not been corrected. These pins cannot convert even if they receive impressions.

**Notice 6 — "Spring dinner ideas" keyword confirmed dead.** Content memory shows 58 lifetime uses, 0 saves, 0 outbound clicks. This week's keyword data: 3 pins, 0 impressions. W13 content plan still includes it as a secondary keyword on W13-08 and W13-19. This keyword should be removed from the pipeline's keyword list immediately.

**Notice 7 — P5 save rate is declining.** Performance history shows P5 trend as "declining" (recent: 0.0%, prior: 2.2%). This week's P5 data: 38 impressions, 0 saves. Last week P5 had 1 save (W9-16). The decline is consistent with W9-16 cycling out of its distribution window — the account's most reliable performer may be losing momentum. This warrants monitoring.

---

## Key Metrics Summary

| Metric | This Week (W14 period) | Last Week (W13 period) | Change |
|--------|------------------------|------------------------|--------|
| Impressions | 193 | 152 | +27% |
| Saves | 1 | 2 | −50% |
| Save Rate | 0.52% | 1.32% | −0.80 pp |
| Outbound Clicks | 6 | 5 | +20% |
| Outbound Click Rate | 3.11% | 3.29% | −0.18 pp |
| Pin Clicks | 13 | 11 | +18% |
| New Pins Posted | 28 (W13 pins) | 28 (W12 pins) | 0 |
| Active Pins | 132 | 104 | +27% |
| Impressions per Active Pin | 1.46 | 1.46 | 0% |

**Rolling 4-week average impressions:** 126 (per content memory). This week's 193 is 53% above the rolling average — a genuine improvement in distribution reach.

**vs. Targets:** The account is now in Month 3, when the strategy's >2% save rate and >0.5% outbound CTR targets apply. This week's save rate (0.52%) falls well below the 2% target. Outbound CTR (3.11%) substantially exceeds the 0.5% target — but this figure is driven almost entirely by a single pin (W10-04: 6 outbound clicks on 64 impressions). Remove W10-04 and the remaining 132 active pins generated 0 outbound clicks on 129 impressions. The outbound CTR "success" is a single-pin artifact, not a portfolio signal.

**Save rate decline is a genuine concern.** Last week: 2 saves on 152 impressions (1.32%). This week: 1 save on 193 impressions (0.52%). Impressions grew 27% while saves dropped 50%. This is the second consecutive week where the impression base has grown faster than saves — consistent with more pins entering distribution without generating engagement. However, the absolute numbers (1–2 saves/week) are too small for trend conclusions. *Interpretation: the account is reaching more users but not yet finding the save-intent audience at scale.*

---

## Top 5 Performing Pins

*No pin meets the 100-impression minimum threshold for statistically valid rate analysis. Rankings are by raw engagement events and impression volume. All rates are directional only.*

| Rank | Pin | Pillar | Template | Impressions | Saves | Outbound Clicks | Save Rate | CTR |
|------|-----|--------|----------|-------------|-------|-----------------|-----------|-----|
| 1 | W10-04: Easy Dinners Kids Will Eat — Sheet Pan Chicken Drumsticks | P2 | recipe-pin | 64 | 1 | 6 | 1.56% | 9.38% |
| 2 | W9-16: High Protein Turkey Meatball Bowls — Healthy Dinner Kids Actually Eat | P5 | recipe-pin | 35 | 0 | 0 | 0.0% | 0.0% |
| 3 | W10-11: Simple Dinner Recipe: One-Pan Honey Mustard Pork Tenderloin | P3 | recipe-pin | 23 | 0 | 0 | 0.0% | 0.0% |
| 4 | W9-12: 15-Minute Teriyaki Salmon Bowls — Quick Weeknight Dinners | P3 | recipe-pin | 13 | 0 | 0 | 0.0% | 0.0% |
| 5 | W9-17: Spring Chicken and Rice Skillet — Easy Weeknight Dinner in One Pan | P1 | recipe-pin | 13 | 0 | 0 | 0.0% | 4.0% |

**Why W10-04 leads:** "Easy dinners kids will eat" is now the account's #1 keyword by outbound CTR (9.38% this week, 6 outbound clicks on 64 impressions). This is the second consecutive week W10-04 has appeared in the top 2. The "Family Dinner Ideas Even Picky Eaters Love" board is driving all outbound click activity in the account — 6 outbound clicks, 1 save, 9 pin clicks, 9.38% CTR. This board is the account's only board generating meaningful conversion behavior. *Caveat: 64 impressions. Directional, not conclusive.*

**Why W9-16 drops to rank 2 with 0 saves:** Last week W9-16 had 1 save; this week 0. The pin still generated 35 impressions (the second-highest in the portfolio), but the save did not recur. Two interpretations: (a) the pin is cycling through a new audience segment that doesn't save, or (b) the prior save was a single-user event and the underlying save rate is lower than the 2.1% figure suggested. The "Healthy Family Dinner Recipes" board generated 37 impressions this week with 0 saves — a notable drop from last week's 1 save. *This is the P5 declining trend flagged in Notice 7.*

**Why W10-11 and W9-12 rank 3–4:** Both are generating impressions (23 and 13 respectively) with zero engagement. "Simple dinner recipes" (W10-11, 23 impressions) and "quick weeknight dinners" (W9-12, 13 impressions) are reaching users but not converting to saves. This is consistent with the broader pattern: high-volume generic keywords generate distribution but not save-intent behavior.

**Why W9-17 appears at rank 5:** 13 impressions, 0 saves, but a 4.0% pin click rate — users are expanding the pin to look more closely. This is a weak positive signal on the image or title, but without a save or outbound click it doesn't advance the account's goals.

**Key shift from last week:** W9-16 (P5) was the save leader last week; W10-04 (P2) is the engagement leader this week. P2 is now the account's most commercially active pillar for the second consecutive week. P5's save signal has not recurred.

---

## Bottom 5 Performing Pins

*All bottom performers are W11-era pins with 1 impression each — consistent with distribution lag for recently-posted content. It is too early to evaluate these pins on performance.*

| Rank | Pin | Pillar | Template | Impressions | Saves | Primary Issue |
|------|-----|--------|----------|-------------|-------|---------------|
| 1 | W11-01: Weekly Dinner Plan for Spring — 5 Light, Fresh Meals | P1 | tip-pin | 1 | 0 | New pin, distribution lag; tip-pin template underperforming (8 impr / 29 pins) |
| 2 | W11-04: Instant Pot Chicken and Rice — Easy Family Dinner | P5 | recipe-pin | 1 | 0 | New pin, distribution lag; Air Fryer & Instant Pot board generating near-zero (1 impr / 4 pins) |
| 3 | W11-05: Family Meal Planning Made Easy — 5 Dinners Under 30 Minutes | P1 | tip-pin | 1 | 0 | New pin, distribution lag; tip-pin template; "family meal planning" keyword: 2 impr / 5 pins lifetime |
| 4 | W11-08: Shrimp Tacos with Mango Slaw — Easy Spring Dinner | P1 | recipe-pin | 1 | 0 | New pin, distribution lag; recipe-pull pin type underperforming (38 impr / 37 pins = 1.03/pin) |
| 5 | W11-09: Better Than Hello Fresh — Build Your Own Flexible Weekly Meal Plan | P4 | tip-pin | 1 | 0 | New pin, distribution lag; P4 structural underperformance (1 impr / 9 pins); "better than hello fresh" keyword: 1 impr lifetime |

**Pattern:** All 5 bottom performers are W11 pins (approximately 2–3 weeks old). Distribution lag is the primary explanation. However, compounding structural issues are present in each: tip-pin template consistently underperforms (0.28 impressions/pin this week), P4 generates near-zero distribution regardless of age, and the recipe-pull pin type averages only 1.03 impressions/pin this week vs. 2.32 for primary pins.

---

## Pillar Performance

| Pillar | Pins (portfolio) | Impressions | Saves | Save Rate | Outbound CTR | Trend vs. Last Week |
|--------|-----------------|-------------|-------|-----------|--------------|---------------------|
| P1: Your Whole Week, Planned | 47 | 45 | 0 | 0.0% | 0.0% | ↔ Flat (was 29 impr, 0 saves last week — impressions up slightly, saves unchanged) |
| P2: Everyone Eats, Nobody Argues | 27 | 70 | 1 | 1.43% | 8.57% | ↑ Impressions up (was 43), saves maintained, CTR dominant |
| P3: Dinner, Decided | 24 | 38 | 0 | 0.0% | 0.0% | ↔ Flat (was 30 impr, 0 saves) |
| P4: Smarter Than a Meal Kit | 9 | 1 | 0 | 0.0% | 0.0% | ↔ Flat (near-zero both weeks) |
| P5: Your Kitchen, Your Rules | 17 | 38 | 0 | 0.0% | 0.0% | ↓ **Declining** — was 48 impr, 1 save last week; impressions down 21%, saves dropped to 0 |

**Pillar ranking by save rate:** P2 (1.43%) > P1/P3/P4/P5 (0.0%)

**Pillar ranking by outbound CTR:** P2 (8.57%) > P1/P3/P4/P5 (0.0%)

**P2 is the account's only active engagement pillar for the second consecutive week.** 70 impressions (36% of total), 1 save, 6 outbound clicks, 9 pin clicks. All meaningful engagement in the account flows through P2 and specifically through the "Family Dinner Ideas Even Picky Eaters Love" board and the "easy dinners kids will eat" keyword. This is the clearest signal the account has produced.

**P5 declining trend confirmed.** Two consecutive weeks of declining performance: Week 13 (48 impr, 1 save) → Week 14 (38 impr, 0 saves). The performance history in content memory flags this as "declining (recent=0.0%, prior=2.2%)." W9-16 was the sole save generator for P5; without a new save from that pin this week, P5's save rate has collapsed. The P5 portfolio (17 pins) is generating distribution (38 impressions) but not saves. *This is a genuine concern, not strategy-predicted underperformance.*

**P1 structural concern deepens.** 47 pins, 45 impressions, 0 saves, 0 outbound clicks. P1 is the largest pillar (36% of portfolio) and the strategy's primary differentiator. It has generated 0 lifetime saves across 96 pins and 106 lifetime impressions. The plan-level content thesis remains entirely unvalidated. The recipe-pull sub-type (37 pins, 38 impressions, 0 saves this week) is performing marginally better on impressions-per-pin than plan-level pins (11 pins, 7 impressions) but neither is generating saves.

**Pillar mix vs. strategy targets:**

| Pillar | Portfolio % (132 pins) | Strategy Target | Gap |
|--------|------------------------|-----------------|-----|
| P1 | 36% (47/132) | 32–36% | At ceiling |
| P2 | 20% (27/132) | 25–29% | −5–9 pp under |
| P3 | 18% (24/132) | 18–21% | Within range |
| P4 | 7% (9/132) | 7–10% | Within range |
| P5 | 13% (17/132) | 14–18% | −1–5 pp under |

P2 remains persistently under-represented at 20% vs. the 25–29% target — despite being the account's only pillar generating saves and outbound clicks. This is the most actionable gap in the portfolio.

---

## Content Type Performance

| Content Type | Pins | Impressions | Saves | Save Rate | Outbound CTR | Notes |
|--------------|------|-------------|-------|-----------|--------------|-------|
| recipe | 55 | 140 | 1 | 0.72% | 4.29