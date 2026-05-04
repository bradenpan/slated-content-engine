# Weekly Performance Analysis — Week 19, April 29 – May 5, 2026

---

## ⚠️ Data Quality & Context Notices

**Notice 1 — Analytics data is 14 days old (last pull: April 20, 2026).** This is a deterioration from last week's 7-day lag. The current pull reflects activity through approximately April 20. W16 pins (posted April 15–21) are at the edge of the data window and may be partially reflected. W17 and W18 pins are not reflected at all. **The analytics lag has doubled. This must be resolved before any meaningful optimization is possible.**

**Notice 2 — Week-over-week comparison is not independent.** Last week's data and this week's data both draw from the same April 20 snapshot. The numbers are structurally identical: 31 impressions, 0 saves, 1 outbound click, 3 pin clicks. This is not stability — it is the same data viewed twice. **Do not interpret "flat" as confirmation of any trend.**

**Notice 3 — Board ID field blank on ALL W13–W16 pins — EIGHTH consecutive week unresolved.** The content plan shows `board_id: ""` on every pin from W13 through W16. This has been flagged in every analysis since Week 12. With 213 active pins and the majority of recent pins unclassified, this is the single most likely cause of the impression collapse. **This is the account's most urgent operational issue. No content optimization is meaningful until this is resolved.**

**Notice 4 — Treatment tracker violations are now severe.** The treatment tracker shows **19 URLs confirmed AT LIMIT** (≥6 treatments, well above the 5-treatment maximum), including `weekly-plan-summer-backyard-grilling` at 9/5 and multiple plan posts at 8–13/5. An additional **30+ URLs are at 3–4 treatments and approaching limit**. The pipeline is systematically ignoring treatment caps. This is a confirmed suppression risk.

**Notice 5 — "Spring dinner ideas" keyword still present — ninth consecutive week flagged.** 3 pins use this keyword, 0 impressions lifetime. This flag has been raised every week since Week 11 without resolution.

**Notice 6 — Blog URL error unresolved — ninth consecutive week.** Pins linking to `goslated.com/blog` with empty `blog_slug` fields cannot convert. First flagged Week 11.

**Notice 7 — No new pins posted this week (0 of planned 28).** The content plan shows 0 new pins this week. This is a full posting gap. Per the strategy: "Post every single day. Pinterest's algorithm penalizes accounts that go quiet and then burst." A week of zero posts is the worst possible outcome for algorithm consistency.

**Notice 8 — No pin meets the 100-impression threshold for statistically valid rate analysis.** W10-04 has 30 impressions this week — the only pin with any engagement signal. All rate metrics are directional signals only.

---

## Key Metrics Summary

| Metric | This Week (W19 period) | Last Week (W18 period) | Change |
|--------|------------------------|------------------------|--------|
| Impressions | 31 | 31 | **0% — data freeze, not stability** |
| Saves | 0 | 0 | 0 |
| Save Rate | 0.0% | 0.0% | 0.0 pp |
| Outbound Clicks | 1 | 1 | 0 |
| Outbound Click Rate | 3.23% | 3.23% | 0.0 pp |
| Pin Clicks | 3 | 3 | 0 |
| New Pins Posted | **0 of 28 planned** | 0 of 28 planned | **−100%** |
| Active Pins | 213 | 213 | 0 |
| Impressions per Active Pin | 0.15 | 0.15 | 0% |

> **Critical data caveat:** Both weeks draw from the same April 20 analytics snapshot. These are not two independent measurements. The identical numbers confirm the data pipeline has not refreshed in at least two weeks. The rolling 4-week average is 130 impressions; this week's 31 is **76% below that average** — but this comparison is also compromised by the data freeze.

**vs. Targets:** The account is now past Month 3, placing it in the window where the strategy's >2% save rate and >0.5% outbound CTR targets formally apply. Current save rate: 0.0% vs. 2.0% target (−2.0 pp). Outbound CTR: 3.23% on paper — driven entirely by a single click on W10-04's 30 impressions, which is not a meaningful rate at this sample size. At 31 total impressions across 213 active pins, portfolio-level rate metrics are uninterpretable. **The targets cannot be evaluated this week, and will not be evaluable until the analytics pipeline is repaired and the board_id issue is resolved.**

---

## Top Performing Pins

*No pin meets the 100-impression minimum threshold for statistically valid rate analysis. Only 2 pins generated any impressions this week. All metrics are directional only.*

| Rank | Pin | Pillar | Template | Impressions | Saves | Outbound Clicks | Save Rate | CTR |
|------|-----|--------|----------|-------------|-------|-----------------|-----------|-----|
| 1 | W10-04: Easy Dinners Kids Will Eat — Sheet Pan Chicken Drumsticks | P2 | recipe-pin | 30 | 0 | 1 | 0.0% | 3.33% |
| 2 | W14-16: 30 Minute Meal: Garlic Shrimp and Spring Vegetable Stir Fry | P1 | recipe-pin | 1 | 0 | 0 | 0.0% | 0.0% |

*Only 2 pins generated any impressions this week. The top-5 format cannot be meaningfully populated.*

**W10-04 — seventh consecutive week as top performer; signal is oscillating, not compounding.** Impression trend across recent weeks: 64 → 19 → 136 → 30 → 30 → 30. The pin has been flat at 30 impressions for three consecutive weeks with 0 saves in all three. Lifetime: 282 impressions, 3 saves (1.1% lifetime save rate). This remains the account's highest-performing pin by absolute saves and the only pin currently generating any distribution signal. The "easy dinners kids will eat" keyword and "Family Dinner Ideas Even Picky Eaters Love" board remain the account's only confirmed engagement surface. However, three consecutive weeks at 30 impressions with 0 saves suggests the pin has plateaued. The 1.1% lifetime save rate is below the 2% target but is the closest the account has come to it.

**W14-16 — 1 impression, 0 engagement.** Not meaningful. Listed for completeness only.

**Pattern:** 211 of 213 active pins generated 0 impressions this week. This is a distribution failure, not a content quality issue. The board_id failure is the most parsimonious explanation.

---

## Bottom Performing Pins

With 31 total impressions across 213 active pins, 211 pins (99%) generated 0 impressions. The bottom-performer concept is not meaningful when the portfolio is uniformly at zero. The structural failure is the finding.

**Segments generating zero impressions this week:**

- **P1 (72 pins): 1 impression total.** The account's largest pillar (35% of portfolio) is essentially invisible.
- **P3 (43 pins): 0 impressions.** The volume backbone generated nothing.
- **P4 (15 pins): 0 impressions.** Consistent with strategy expectations (intentionally low-volume pillar), but still zero.
- **P5 (25 pins): 0 impressions.** Zero for the third consecutive week.
- **Tip-pin template (45 pins): 0 impressions.** Zero for multiple consecutive weeks.
- **Problem-solution-pin (16 pins): 0 impressions.** Zero across the account's entire history. This template has never generated a meaningful impression in any week.
- **Listicle-pin (29 pins): 0 impressions.** Consistent zero.
- **Infographic-pin (9 pins): 0 impressions.** Consistent zero.

---

## Pillar Performance

| Pillar | Pins | Impressions | Saves | Save Rate | CTR | Trend vs. Last Week |
|--------|------|-------------|-------|-----------|-----|---------------------|
| P1: Your Whole Week, Planned | 72 | 1 | 0 | 0.0% | 0.0% | → Flat (data freeze) |
| P2: Everyone Eats, Nobody Argues | 45 | 30 | 0 | 0.0% | 3.33% | → Flat (data freeze) |
| P3: Dinner, Decided | 43 | 0 | 0 | 0.0% | 0.0% | → Flat (data freeze) |
| P4: Smarter Than a Meal Kit | 15 | 0 | 0 | 0.0% | 0.0% | → Flat (data freeze) |
| P5: Your Kitchen, Your Rules | 25 | 0 | 0 | 0.0% | 0.0% | → Flat (data freeze) |

> **Data caveat:** "Flat" reflects the analytics data freeze, not genuine stability. Both weeks draw from the same April 20 snapshot. These are not two independent data points.

**Pillar ranking by save rate:** All pillars at 0.0% this week. No ranking is possible.

**Lifetime context (from content memory):**
- P2: 330 lifetime impressions, 3 saves (0.9% lifetime save rate) — the account's only pillar with positive lifetime saves alongside P5
- P5: 151 lifetime impressions, 2 saves (1.3% lifetime save rate)
- P1: 159 lifetime impressions, 0 saves (0.0%) — 149 pins, 35% of portfolio, zero saves ever
- P3: 148 lifetime impressions, 0 saves (0.0%)
- P4: 8 lifetime impressions, 0 saves (0.0%)

**⚠️ Declining trend flag — P2 and P5 recent save rates at zero.** Both pillars that have ever generated saves are showing 0.0% recent save rates. This is a two-pillar declining trend persisting for multiple consecutive weeks. At small sample sizes this may be noise, but it warrants monitoring.

**⚠️ P1 structural concern — 149 pins, 0 lifetime saves.** The account's primary strategic differentiator (plan-level content, 35% of portfolio) has never generated a save. The strategy predicts this pillar should drive compounding growth. The data shows the opposite. This is the most important strategic question for the monthly review.

---

## Content Type Performance

| Template | Pins | Impressions | Saves | Save Rate | CTR | Notes |
|----------|------|-------------|-------|-----------|-----|-------|
| recipe-pin | 109 | 31 | 0 | 0.0% | 3.23% | All impressions from W10-04 (30) + W14-16 (1); 107/109 pins at zero |
| tip-pin | 45 | 0 | 0 | 0.0% | 0.0% | Zero distribution; multiple consecutive weeks |
| listicle-pin | 29 | 0 | 0 | 0.0% | 0.0% | Zero distribution |
| problem-solution-pin | 16 | 0 | 0 | 0.0% | 0.0% | **Zero across entire account history — escalation item** |
| infographic-pin | 9 | 0 | 0 | 0.0% | 0.0% | Zero distribution |

**Recipe-pin is the only format generating any distribution signal.** However, this is attributable to a single pin (W10-04), not to the recipe-pin template broadly. 107 of 109 recipe-pins generated 0 impressions this week.

**⚠️ Problem-solution-pin: zero impressions across entire account history.** 16 pins, never a meaningful impression. The strategy assigns this template to P2 system-level content and P4 meal kit content — the conversion layer. If the conversion layer template is not distributing, the funnel has no bottom. This is an escalation item for the monthly review.

**Tip-pin: zero for multiple consecutive weeks.** 45 pins, 0 impressions. The strategy assigns tip-pins to plan-level content (P1) and guide content (P2). This template's consistent zero is directly correlated with P1's near-zero performance. Cannot determine whether this is a template issue or a board_id classification failure without resolving the pipeline issue first.

---

## Board Performance

| Board | Pins (portfolio) | Impressions | Saves | Save Rate | CTR | Notes |
|-------|-----------------|-------------|-------|-----------|-----|-------|
| Family Dinner Ideas Even Picky Eaters Love | 29 | 30 | 0 | 0.0% | 3.33% | Driven entirely by W10-04 |
| Easy Dinner Ideas for Families | 43 | 1 | 0 | 0.0% | 0.0% | W14-16 only |
| Quick Weeknight Dinner Recipes | 39 | 0 | 0 | 0.0% | 0.0% | Zero distribution |
| Weekly Meal Plans & Meal Planning Tips | 19 | 0 | 0 | 0.0% | 0.0% | Zero distribution |
| Family Meal Planning Strategies | 19 | 0 | 0 | 0.0% | 0.0% | Zero distribution |
| Better Than a Meal Kit | 16 | 0 | 0 | 0.0% | 0.0% | Zero distribution |
| Healthy Family Dinner Recipes | 16 | 0 | 0 | 0.0% | 0.0% | Zero distribution |
| Meal Planning & Grocery Tips | 15 | 0 | 0 | 0.0% | 0.0% | Zero distribution |
| Gluten-Free Dinner Ideas | 7 | 0 | 0 | 0.0% | 0.0% | Zero distribution |
| Air Fryer & Instant Pot Dinner Recipes | 5 | 0 | 0 | 0.0% | 0.0% | Zero distribution |

**"Family Dinner Ideas Even Picky Eaters Love" is the account's only board generating any distribution.** 97% of this week's impressions (30 of 31) come from this board, entirely attributable to W10-04. Remove that pin and this board is also at zero.

**8 of 10 boards generated zero impressions this week.** The board_id failure (blank board assignments on all W13–W16 pins) is the most likely cause for newer pins. However, older pins with correct board assignments are also generating zero — suggesting the issue is broader than just the board_id field.

**Board density context:** "Easy Dinner Ideas for Families" has 84 pins in the content memory and "Quick Weeknight Dinner Recipes" has 80 pins — the two most populated boards — yet both generated near-zero impressions this week. High pin count is not translating to distribution. This is consistent with the board_id failure suppressing classification signals.

---

## Keyword Insights

**Top performing keywords by lifetime save rate (from content memory):**

| Keyword | Lifetime Pins | Lifetime Impressions | Lifetime Saves | Save Rate | This Week Impressions |
|---------|--------------|---------------------|----------------|-----------|----------------------|
| easy dinners kids will eat | 23 (content memory) / 10 (this week's data) | 290 | 3 | **1.0%** | 30 |
| high protein dinner recipes | 19 (content memory) / 8 (this week's data) | 143 | 2 | **1.4%** | 0 |
| All other keywords | — | — | 0 | 0.0% | 0 |

**These two keywords are the only ones with lifetime saves.** Every other keyword in the account's history has generated zero saves. This is the most important signal in the data.

**Underperforming keywords (this