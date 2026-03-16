# Weekly Performance Analysis — Week 11, March 11–17, 2026

---

## ⚠️ Data Integrity Notices (Read Before Any Analysis)

**Notice 1 — Complete impression collapse: all metrics are zero.** This week's data shows 0.0 impressions, 0.0 saves, 0.0 outbound clicks, and 0.0 pin clicks across all 28 pins. Last week showed 8 total impressions (already near-zero). The account has now posted 160 pins over approximately 10 weeks and has accumulated a lifetime total of approximately 75 impressions with 1 save. **This is not a performance problem — this is a delivery problem.** The data is consistent with pins not being published or indexed at all, not with pins being published and simply underperforming.

**Notice 2 — Board ID failure is now in its second consecutive week at 100% scope.** Every single pin in the Week 11 content plan has `"board_id": ""`. This is the same failure mode flagged last week for all 28 Week 10 pins. Two consecutive weeks of universal board ID failure is the most likely explanation for zero impressions. If pins are being posted without board assignment, Pinterest cannot classify or distribute them. **This is the #1 operational priority before any content decisions are made.**

**Notice 3 — Four pins link to `goslated.com/blog` (homepage) instead of a specific blog post.** W11-19 (lemon garlic butter shrimp pasta), W11-22 (slow cooker white bean kale soup), W11-26 (toddler dinner ideas / mini turkey taco bowls), and W11-28 (tired of meal kits) all have `"blog_slug": ""` and link to the blog root. This is a recurring content production error — three pins had the same issue last week (W10-16, W10-18, W10-23). The error is not being caught in the approval gate. These four pins cannot drive outbound clicks or CTA conversions regardless of distribution.

**Notice 4 — Treatment tracker shows critical overrun.** The content memory treatment tracker shows six blog post URLs already at or exceeding the 5-treatment limit (some at 9–12 treatments), and sixteen URLs approaching the limit at 4/5. The strategy's fresh pin rules (Section 8.2) cap URLs at 5 treatments in 60 days. The pipeline is violating this constraint at scale. This is not a performance issue this week, but it is a content integrity issue that will suppress distribution as Pinterest detects near-duplicate content pointing to the same URLs.

**Notice 5 — Engagement targets are not applicable.** This is Week 3 of active posting (Week 11 of the overall project). The >2% save rate and >0.5% outbound CTR targets are Month 3+ benchmarks. The meaningful question is not whether targets are met — it is whether pins are being delivered and indexed at all. The answer, based on two consecutive weeks of zero impressions on new pins, is: **no, or nearly no.**

**Notice 6 — Rolling 4-week average discrepancy.** The account-level trends data shows a rolling 4-week average save rate and CTR of 1.27% each. This appears to be a data artifact — the raw data shows 0 saves and 0 outbound clicks across all pins in the content plan, and the content memory confirms 0.0% save rate on all keywords except `high protein dinner recipes` (1 save, 9.1% rate, 11 impressions). The 1.27% rolling average likely reflects a single early save event inflating the percentage on a tiny impression base. It should not be interpreted as a meaningful benchmark.

---

## Key Metrics Summary

| Metric | This Week (W11) | Last Week (W10) | Change |
|--------|-----------------|-----------------|--------|
| Impressions | 0 | 8 | −100% |
| Saves | 0 | 0 | — |
| Save Rate | 0.0% | 0.0% | — |
| Outbound Clicks | 0 | 0 | — |
| Outbound Click Rate | 0.0% | 0.0% | — |
| Pin Clicks | 0 | 0 | — |
| Pins Posted | 28 scheduled (delivery unconfirmed) | 28 scheduled (delivery unconfirmed) | — |
| Impressions per Pin | 0.00 | 0.29 | −100% |
| Rolling 4-wk Avg Impressions | 20 (account-level) | ~11 (per prior analysis) | — |

**vs. Targets:** Save rate and CTR targets (>2% and >0.5%) are Month 3+ benchmarks and are not applicable at Week 3. These targets are not the concern. The concern is that this week shows zero impressions across 28 pins — a complete absence of any distribution signal. The rolling 4-week average of 20 impressions reflects the account's entire history, which is itself extremely low. No performance targets can be evaluated until the board ID failure is resolved and pins are confirmed as delivered.

**Trend note:** Impressions per pin have declined three consecutive weeks: Week 9 (estimated ~1.5+), Week 10 (0.29), Week 11 (0.00). This is a declining trend, not noise.

---

## Top 5 Performing Pins

**Cannot be reported.** Zero impressions across all 28 Week 11 pins. The minimum threshold for save-rate analysis is 100 impressions per pin. No pin approaches this threshold. Ranking is not meaningful.

**What the data does show:** The only non-zero performance signal in the entire account history is from the content memory's Performance History section:

- `high protein dinner recipes`: 4 pins, 11 impressions, **1 save, 9.1% save rate** — the account's only recorded save, on a Pillar 5 pin targeting a P5 primary keyword. This is a single data point on 11 impressions and is not statistically significant, but it is the only positive signal in 160 pins of history and is worth noting for Week 12 planning.

All other keywords show 0.0% save rate. No other top-performer analysis is possible.

---

## Bottom 5 Performing Pins

**Cannot be reported** for the same reasons. All pins have 0 impressions, 0 saves, 0 clicks.

**Structural flags from the Week 11 content plan:**

| Pin | Issue | Impact |
|-----|-------|--------|
| W11-19 | `blog_slug: ""` — links to `goslated.com/blog` | Cannot convert; no specific content delivered |
| W11-22 | `blog_slug: ""` — links to `goslated.com/blog` | Cannot convert; no specific content delivered |
| W11-26 | `blog_slug: ""` — links to `goslated.com/blog` | Cannot convert; no specific content delivered |
| W11-28 | `blog_slug: ""` — links to `goslated.com/blog` | Cannot convert; no specific content delivered |
| W11-14 | `image_id: ""` — template-only image source | Possible distribution suppression (pattern from prior weeks) |
| W11-07 | `problem-solution-pin` template — 0 impressions across 4 pins over 2 weeks | Consistent zero-impression pattern on this template type |
| W11-20 | `problem-solution-pin` template — same concern | Same pattern |

Additionally, the treatment tracker shows that the two P4 pins this week (W11-09 `better-than-hello-fresh-build-your-own-meal-plan` at 4/5 treatments, W11-20 `better-than-hello-fresh-build-your-own-meal-plan` also at 4/5) are approaching the treatment limit on URLs that have already been heavily treated. The `better-than-hello-fresh` URL has now received 4 treatments; one more treatment is the limit before the 60-day window resets.

---

## Pillar Performance

| Pillar | Pins This Week | Impressions | Save Rate | CTR | Trend vs. Last Week |
|--------|---------------|-------------|-----------|-----|---------------------|
| P1: Your Whole Week, Planned | 10 | 0.0 | 0.0% | 0.0% | ↓ (was 0 last week too; no change) |
| P2: Everyone Eats, Nobody Argues | 6 | 0.0 | 0.0% | 0.0% | Flat |
| P3: Dinner, Decided | 7 | 0.0 | 0.0% | 0.0% | Flat |
| P4: Smarter Than a Meal Kit | 2 | 0.0 | 0.0% | 0.0% | Flat |
| P5: Your Kitchen, Your Rules | 3 | 0.0 | 0.0% | 0.0% | Flat |

**Pillar ranking by save rate:** Cannot be ranked — all save rates are 0.0%.

**Pillar mix this week vs. strategy targets:**

| Pillar | This Week % (of 28 pins) | Strategy Target | Gap |
|--------|--------------------------|-----------------|-----|
| P1 | 36% (10/28) | 32–36% | Within range |
| P2 | 21% (6/28) | 25–29% | −4–8 pp under target |
| P3 | 25% (7/28) | 18–21% | +4–7 pp over target |
| P4 | 7% (2/28) | 7–10% | Within range |
| P5 | 11% (3/28) | 14–18% | −3–7 pp under target |

**Pillar mix observations:**

- **P2 is under-represented at 21% vs. 25–29% target.** The strategy identifies P2 as "blue ocean" — the highest-differentiation pillar with no competitive content on Pinterest. Under-producing here is a strategic miss, not just a mix issue. This week's 6 P2 pins include 3 recipe pins (W11-03, W11-18, W11-26) and 2 guide/problem-solution pins (W11-07, W11-14), plus 1 fresh treatment (W11-26). The guide/problem-solution content is correct for P2's conversion intent, but the overall count is below target.

- **P3 is over-represented at 25% vs. 18–21% target.** Standalone recipe content is the commodity backbone, not the differentiator. Running 4–7 pp over target on P3 while P2 and P5 are under target is a content generation gap — the pipeline is defaulting to the easiest content type (standalone recipes) rather than the strategically important types.

- **P5 is under-represented at 11% vs. 14–18% target** for the second consecutive week (last week: 5% vs. 14–18%). The strategy calls for 4–5 P5 pins per week covering dietary and appliance-specific content. This week delivered 3 (W11-04 Instant Pot, W11-12 dairy-free curry, W11-22 slow cooker soup, W11-25 gluten-free curry — actually 4 pins; the per-pillar data shows count: 3, which may reflect a data discrepancy). Even at 4 pins, P5 is below its 14–18% target on a 28-pin week (target: 4–5 pins).

**Lifetime pillar mix (from content memory):** P1: 37%, P2: 21%, P3: 19%, P4: 8%, P5: 11%. P2 and P5 are both running below their strategy targets on a cumulative basis. This is a persistent pipeline gap, not a single-week anomaly.

---

## Content Type Performance

| Template | Pins This Week | Impressions | Save Rate | CTR | Notes |
|----------|---------------|-------------|-----------|-----|-------|
| recipe-pin | 12 | 0.0 | 0.0% | 0.0% | Largest template type; 0 impressions |
| tip-pin | 8 | 0.0 | 0.0% | 0.0% | Includes P1 plan pins and P5 dietary content |
| listicle-pin | 4 | 0.0 | 0.0% | 0.0% | Used across P2, P3, P5 |
| infographic-pin | 2 | 0.0 | 0.0% | 0.0% | W11-14 (template-only image); W11-05 (ai_generated) |
| problem-solution-pin | 2 | 0.0 | 0.0% | 0.0% | W11-07 (P2 guide), W11-20 (P4 meal kit); **0 impressions for 3rd consecutive week across 6 total problem-solution pins** |

**Template pattern worth flagging:** The `problem-solution-pin` template has now accumulated 6 pins across 3 weeks with 0 impressions total. This is the only template type with a consistent zero-impression pattern. However, given that all templates show 0 impressions this week due to the board ID failure, it is not possible to isolate whether this is a template-specific issue or a delivery issue. The pattern predates this week's total collapse — problem-solution pins also showed 0 impressions in Week 10 when other templates showed minimal impressions. This warrants monitoring once delivery is confirmed.

---

## Board Performance

| Board | Pins This Week | Impressions | Save Rate | CTR | Notes |
|-------|---------------|-------------|-----------|-----|-------|
| Easy Dinner Ideas for Families | 6 | 0.0 | 0.0% | 0.0% | Highest pin count; 0 impressions |
| Quick Weeknight Dinner Recipes | 6 | 0.0 | 0.0% | 0.0% | 0 impressions for 3rd consecutive week (9 total pins) |
| Family Meal Planning Strategies | 4 | 0.0 | 0.0% | 0.0% | 0 impressions |
| Healthy Family Dinner Recipes | 3 | 0.0 | 0.0% | 0.0% | 0 impressions |
| Weekly Meal Plans & Meal Planning Tips | 2 | 0.0 | 0.0% | 0.0% | Was top board in W9 (5 impr); 0 for 2 consecutive weeks |
| Family Dinner Ideas Even Picky Eaters Love | 2 | 0.0 | 0.0% | 0.0% | Was 2nd-best board in W9 (5 impr); 0 for 2 consecutive weeks |
| Meal Planning & Grocery Tips | 2 | 0.0 | 0.0% | 0.0% | 0 impressions |
| Better Than a Meal Kit | 2 | 0.0 | 0.0% | 0.0% | 0 impressions |
| Air Fryer & Instant Pot Dinner Recipes | 1 | 0.0 | 0.0% | 0.0% | 0 impressions |
| Gluten-Free Dinner Ideas | 0 | — | — | — | No pins assigned this week per board data |

**Board observations:**

1. **Every board shows 0 impressions this week.** This is consistent with the board ID failure hypothesis — if pins are not being delivered with board assignments, no board receives new content to distribute.

2. **"Weekly Meal Plans & Meal Planning Tips" and "Family Dinner Ideas Even Picky Eaters Love" have both dropped from their Week 9 highs (5 impressions each) to 0 for two consecutive weeks.** These were the two best-performing boards in the account's history. Their collapse coincides exactly with the board ID failure beginning in Week 10.

3. **"Quick Weeknight Dinner Recipes" has now received 9 pins across 3 weeks with 0 impressions total.** This board's zero-impression pattern predates the universal board ID failure (it showed 0 in Week 10 even when other boards showed minimal impressions). This may indicate a board-level classification issue independent of the delivery problem, or it may simply reflect that this is a highly competitive keyword space where a new account with no domain authority cannot break through. Cannot distinguish these explanations from current data.

4. **Cumulative board distribution (from content memory, 10 weeks):** "Easy Dinner Ideas for Families" (34 pins) and "