# Weekly Performance Analysis — Week 12, March 18–24, 2026

---

## ⚠️ Data Integrity Notices

**Notice 1 — Board ID failure appears resolved.** This week's data shows 34 total impressions across 77 active pins, up from 0 impressions last week (W11) and 29 impressions the week prior (W10, which itself reflected mostly older pins). Critically, the current week's content plan (W11 pins) shows board assignments populated — the `board_id: ""` failure that caused two consecutive weeks of near-zero delivery appears to have been corrected. This is the most important operational development this week.

**Notice 2 — Impression base is still extremely small.** 34 total impressions across 77 active pins means most pins received 0 impressions this period. The top pin (W9-12, Teriyaki Salmon) accounts for 16 of 34 total impressions — 47% of all weekly impressions concentrated in a single pin. No statistical conclusions can be drawn from this data. All save rates and CTRs are computed on impression bases of 9 or fewer, well below the 100-impression minimum threshold for meaningful rate analysis.

**Notice 3 — The data appears to reflect Week 9 pins, not Week 11 pins.** The top performers listed (W9-12, W9-16, W9-17, W9-02, W9-05) are all Week 9 pins. The bottom performers are also Week 9 pins. Week 11 pins (W11-xx) do not appear in the top or bottom performer lists despite being the most recently posted. This is consistent with Pinterest's distribution lag — new pins take days to weeks to enter distribution. The metrics this week likely reflect the tail-end distribution of older pins (W9 era) rather than W11 content. **This means W11's board ID fix has not yet produced measurable impressions — those will appear in coming weeks.**

**Notice 4 — Treatment tracker is in critical violation.** Six URLs are at 12/5, 10/5, 10/5, 10/5, 10/5, and 9/5 treatments — all far exceeding the 60-day limit of 5. An additional 16 URLs are at 4/5 (approaching limit). The pipeline is generating fresh treatments for URLs that are already at 2x–3x the allowed limit. This is a content integrity issue that will suppress distribution as Pinterest detects near-duplicate content. **This must be resolved before next week's plan is generated.**

**Notice 5 — Four W11 pins link to `goslated.com/blog` (homepage) instead of a specific post.** W11-19, W11-22, W11-26, and W11-28 have `blog_slug: ""`. This is the third consecutive week this error has appeared. It is not being caught in the approval gate.

---

## Key Metrics Summary

| Metric | This Week (W12 period) | Last Week (W11) | Change |
|--------|------------------------|-----------------|--------|
| Impressions | 34 | 0 | +∞ (from zero) |
| Saves | 1 | 0 | +1 |
| Save Rate | 2.9% | 0.0% | +2.9 pp |
| Outbound Clicks | 1 | 0 | +1 |
| Outbound Click Rate | 2.9% | 0.0% | +2.9 pp |
| Pin Clicks | 2 | 0 | +2 |
| New Pins Posted | 29 (W11 pins, delivery now confirmed) | 28 (delivery unconfirmed) | — |
| Impressions per Active Pin | 0.44 | 0.00 | Recovery |
| Rolling 4-wk Avg Impressions | 32 | ~20 | +60% |

**vs. Targets:** Save rate (>2%) and outbound CTR (>0.5%) targets are Month 3+ benchmarks and are not applicable as performance criteria at Week 12. The account is in Month 3 of the launch phase. However, it is worth noting that the single meaningful engagement event this week — W9-16 (High Protein Turkey Meatball Bowls) — produced a 11.1% save rate and 11.1% outbound CTR on 9 impressions. This is a single data point and not statistically significant, but it is the second time this pin/keyword has generated the account's only save event. The signal is consistent even if the sample is too small to act on definitively.

**Trend note:** Impressions have now moved: W9 (~34 impressions from that week's pins), W10 (29 impressions, mostly older pins), W11 (0 impressions — board ID failure), W12 period (34 impressions, recovery). The recovery is real but the absolute level remains extremely low. The board ID fix is necessary but not sufficient for growth.

---

## Top 5 Performing Pins

*The 100-impression minimum threshold for statistically meaningful save rate analysis cannot be met by any pin in the portfolio. The account's all-time top performer has 16 impressions. All rankings below are by raw impressions and engagement events, not save rate. Treat as directional signals only.*

| Rank | Pin | Pillar | Template | Impressions | Saves | Outbound Clicks | Notes |
|------|-----|--------|----------|-------------|-------|-----------------|-------|
| 1 | W9-12: 15-Minute Teriyaki Salmon Bowls | P3 | recipe-pin | 16 | 0 | 0 | Highest reach; zero conversion |
| 2 | W9-16: High Protein Turkey Meatball Bowls | P5 | recipe-pin | 9 | 1 | 1 | Only save + click this week |
| 3 | W9-17: Spring Chicken and Rice Skillet | P1 | recipe-pin | 3 | 0 | 0 | Recipe-pull pin |
| 4 | W9-02: Lemon Herb Chicken with Spring Vegetables | P1 | recipe-pin | 2 | 0 | 0 | Recipe-pull pin |
| 5 | W9-05: Family Meal Planning Made Simple | P1 | tip-pin | 2 | 0 | 0 | Plan-level pin |

**Why W9-12 leads on impressions:** "Quick weeknight dinners" is the primary keyword — this keyword has accumulated 19 total impressions across 4 pins in the account's history, the highest impression volume of any keyword. The board ("Easy Dinner Ideas for Families") has 20 impressions this period — the highest-performing board. The recipe-pin template is the account's dominant impression driver (32 of 34 total impressions). However, 16 impressions with 0 saves suggests the content is being surfaced but not resonating enough to earn a save. This could reflect image quality, title framing, or simply that 16 impressions is too small a sample to draw conclusions.

**Why W9-16 is the only pin generating engagement:** "High protein dinner recipes" is the only keyword in the account's history with a recorded save (1 save, 9.1% rate, 11 impressions lifetime). This week it generated the account's only save and only outbound click again. The keyword targets a specific dietary intent (P5) rather than a generic dinner search — this specificity may be why it converts when generic keywords don't. The "Healthy Family Dinner Recipes" board has the account's only non-zero save rate (11.1% this period). This is a consistent signal across two separate measurement periods, though the sample remains too small for statistical confidence.

**Why W9-17, W9-02, W9-05 appear:** These are Week 9 pins still receiving tail-end distribution. Their 1-3 impressions each represent the long tail of Pinterest's distribution window, not new traction. No engagement on any of them.

---

## Bottom 5 Performing Pins

*Same caveat: minimum impression threshold cannot be met. Bottom performers are those with impressions but zero engagement, or zero impressions entirely.*

| Rank | Pin | Pillar | Template | Impressions | Saves | Issue |
|------|-----|--------|----------|-------------|-------|-------|
| 1 | W9-08: Sheet Pan Sausage and Vegetables | P1 | recipe-pin | 1 | 0 | Minimal reach; unsplash image source |
| 2 | W9-18: Easy Beef and Broccoli Stir-Fry | P1 | recipe-pin | 1 | 0 | Minimal reach |
| 3 | W9-17: Spring Chicken and Rice Skillet | P1 | recipe-pin | 3 | 0 | In top 5 by impressions but zero conversion |
| 4 | W9-02: Lemon Herb Chicken | P1 | recipe-pin | 2 | 0 | Zero conversion |
| 5 | W9-05: Family Meal Planning Made Simple | P1 | tip-pin | 2 | 0 | Zero conversion |

**Pattern:** All bottom performers are Pillar 1 pins. All are recipe-pull pins or plan-level pins from Week 9. All have zero saves and zero clicks. This is consistent with the broader data: P1 has 28 pins and 9 impressions lifetime with 0 saves — the weakest save rate of any pillar with meaningful impression volume. However, this may reflect keyword competitiveness (P1 targets high-volume, highly competitive keywords like "easy dinner ideas" and "easy weeknight dinners") rather than content quality. The algorithm may be testing these pins against established accounts and finding Slated's domain authority insufficient to rank.

**Structural underperformers not in top/bottom lists (zero impressions this week):**
- All 11 guide-type pins: 0 impressions
- All 6 problem-solution-pin template pins: 0 impressions (now 3+ consecutive weeks)
- All 11 listicle-pin template pins: 0 impressions
- All 4 infographic-pin template pins: 0 impressions
- All 9 secondary pin types: 0 impressions
- All 11 fresh-treatment pins: 0 impressions

The recipe-pin template on AI-generated images is the only format generating any distribution at all.

---

## Pillar Performance

| Pillar | Pins (portfolio) | Impressions | Saves | Save Rate | CTR | Trend vs. Last Week |
|--------|-----------------|-------------|-------|-----------|-----|---------------------|
| P1: Your Whole Week, Planned | 28 | 9 | 0 | 0.0% | 0.0% | ↑ (was 0) |
| P2: Everyone Eats, Nobody Argues | 16 | 0 | 0 | 0.0% | 0.0% | Flat (0 both weeks) |
| P3: Dinner, Decided | 13 | 16 | 0 | 0.0% | 0.0% | ↑ (was 0) |
| P4: Smarter Than a Meal Kit | 5 | 0 | 0 | 0.0% | 0.0% | Flat (0 both weeks) |
| P5: Your Kitchen, Your Rules | 6 | 9 | 1 | 11.1% | 11.1% | ↑ (was 0) |

**Pillar ranking by save rate:** P5 (11.1%) > P1/P2/P3/P4 (0.0% — tied)

*Critical caveat: P5's 11.1% rate is computed on 9 impressions, all from a single pin (W9-16). This is not a statistically valid rate. It is a directional signal only.*

**Pillar mix this week vs. strategy targets:**

| Pillar | Portfolio % (of 77 pins) | Strategy Target | Gap |
|--------|--------------------------|-----------------|-----|
| P1 | 36% (28/77) | 32–36% | Within range |
| P2 | 21% (16/77) | 25–29% | −4–8 pp under |
| P3 | 17% (13/77) | 18–21% | −1–4 pp under |
| P4 | 6% (5/77) | 7–10% | −1–4 pp under |
| P5 | 8% (6/77) | 14–18% | −6–10 pp under |

**Persistent pillar mix gaps:** P2 and P5 have been under-represented for the entire account history (P2: 21% vs. 25–29% target; P5: 11% lifetime vs. 14–18% target). This is not a single-week anomaly — the content memory confirms these gaps have persisted across all 10 weeks. P5 is the account's only pillar with a recorded save, making its under-representation a strategic concern: the one content area showing any engagement signal is also the most under-produced.

---

## Content Type Performance

| Template | Pins | Impressions | Saves | Save Rate | CTR | Notes |
|----------|------|-------------|-------|-----------|-----|-------|
| recipe-pin | 37 | 32 | 1 | 3.1% | 3.1% | Sole driver of all impressions and engagement |
| tip-pin | 18 | 2 | 0 | 0.0% | 0.0% | Minimal distribution |
| listicle-pin | 11 | 0 | 0 | 0.0% | 0.0% | Zero impressions, 3+ consecutive weeks |
| problem-solution-pin | 6 | 0 | 0 | 0.0% | 0.0% | Zero impressions, 3+ consecutive weeks |
| infographic-pin | 4 | 0 | 0 | 0.0% | 0.0% | Zero impressions |

**Template ranking:** recipe-pin dominates entirely. All other templates are generating zero distribution.

**Important context:** The recipe-pin template's apparent outperformance may partly reflect that it is the most-used template (37 of 76 classified pins) and that recipe content targets high-volume search keywords. However, the pattern is now consistent across 3+ weeks: non-recipe-pin templates generate no impressions. This warrants investigation — either these templates are being suppressed by Pinterest's algorithm, or the keywords they target (planning, strategy, picky eaters) have insufficient search volume to surface a new account's content.

**The problem-solution-pin pattern is the most concerning:** 6 pins, 3+ weeks, 0 impressions. This template is used primarily for P2 and P4 conversion content — the highest-intent content in the strategy. If it cannot achieve distribution, the conversion layer of the funnel is effectively non-functional.

---

## Board Performance

| Board | Pins (portfolio) | Impressions | Saves | Save Rate | CTR | Notes |
|-------|-----------------|-------------|-------|-----------|-----|-------|
| Easy Dinner Ideas for Families | 16 | 20 | 0 | 0.0% | 0.0% | Highest impression volume |
| Healthy Family Dinner Recipes | 6 | 9 | 1 | 11.1% | 11.1% | Only board with saves/clicks |
| Quick Weeknight Dinner Recipes | 15 | 3 | 0 | 0.0% | 0.0% | Disproportionately low vs. pin count |
| Weekly Meal Plans & Meal Planning Tips | 6 | 2 | 0 | 0.0% | 0.0% | Recovering from W11 zero |
| Dinner Ideas Even Picky Eaters Love | 9 | 0 | 0 | 0.0% | 0.0% | Zero impressions |
| Family Meal Planning Strategies | 9 | 0 | 0 | 0.0% | 0.0% | Zero impressions |
| Better Than a Meal Kit | 6 | 0 | 0 | 0.0% | 0.0% | Zero impressions |
| Air Fryer & Instant Pot Dinner Recipes | 3 | 0 | 0 | 0.0% | 0.0% | Zero impressions |
| Meal Planning & Grocery Tips | 5 | 0 | 0 | 0.0% | 0.0% | Zero impressions |
| Gluten-Free Dinner Ideas | 1 | 0 | 0 | 0.0% | 0