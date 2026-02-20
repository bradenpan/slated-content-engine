# Slated — Pinterest Content Strategy

> **Version:** 2.1
> **Date:** February 19, 2026
> **Status:** Foundational — feeds into the automation pipeline as `strategy/current-strategy.md`
> **Owner:** Braden Pan
> **Input documents:** Pinterest Channel Research v2, Pinterest Organic Research, Slated Archetypes v3, Slated Product Overview, ASA Channel Learnings, AI Automation Plan, Pinterest Workflow Diagram

---

## 1. What This Document Is

This is the strategic brain of Slated's Pinterest automation pipeline. It defines *what* content to create, *who* it's for, *how* it should sound, and *why* each piece exists. The automation system reads this document as its primary input when generating weekly content plans.

**How this document connects to the pipeline:**

```
THIS DOCUMENT (strategy)
    ↓ read by
Weekly Content Plan Generator (AI + performance data + seasonal calendar)
    ↓ outputs
Weekly Content Plan (8-10 blog posts + derived pin assignments)
    ↓ approved by human, then
Content Generation Pipeline (blog posts, then pin images + copy)
    ↓ approved by human, then
Daily Posting (Pinterest API, 4x/day)
    ↓ measured by
Weekly Analysis → feeds back into next week's plan
Monthly Review → feeds back into THIS DOCUMENT (strategy updates)
```

**What this document does NOT cover:**
- Paid Pinterest advertising (organic-first; paid is a separate future strategy)
- Video pins (deferred to v2 per automation plan)
- Idea Pins / Carousels (deferred to v2)
- The technical automation infrastructure (covered in `ai-automation-plan.md`)

---

## 2. Strategic Foundation

### 2.1 Platform Thesis

Pinterest is a visual search engine, not a social network. Users arrive with planning intent — they search "quick weeknight dinners," not "[Brand] recipes." The platform processes ~5 billion searches/month, 97% unbranded. The audience skews 60-70% female, with mothers over-indexing at ~2x the general population.

**The critical alignment with Slated:** Pinterest users are doing *exactly* what Slated automates. They manually build meal plans by saving recipe pins to boards, creating mental shopping lists, and trying to solve the "what's for dinner" problem one pin at a time. Every search on Pinterest for dinner ideas is someone doing Slated's job by hand.

**The compounding model:** A pin's half-life is ~3.75 months (vs. hours on Instagram/TikTok). Content creation on Pinterest is an investment in compounding assets, not disposable posts. Every pin added to the library increases total search surface area. Domain quality improves as pins drive clicks, which improves the starting position for new pins. This is the economic engine.

**Time to traction:** 3-6 months for meaningful results. The first 90 days are about building signals. Payoff comes in months 4-12 and compounds from there.

### 2.2 Target Audience on Pinterest

Two primary personas, drawn from Slated Archetypes v3:

**The High-Velocity Parent (HVP)** — Optimizes for cognitive relief. Willing to pay to not think about dinner. Needs the entire cognitive chain handled: recipe selection, preference management, shopping list, shopping execution. Activation feature: the Ready-Made Plan.

**The Peacekeeper** — Optimizes for family harmony. Carries the cognitive AND emotional burden of the family food system. Needs the plan handled AND family buy-in. Activation feature: the Dinner Draft.

**Excluded personas:** Budget Optimizer ("cheap meals," "save money on food") and Perfectionist ("authentic recipes," "from scratch"). Content should not attract or speak to these audiences. If a content concept primarily appeals to cost-optimization or hobbyist cooking, do not produce it.

### 2.3 Targeting Principle: Behavioral Moments, Not Persona Identity

ASA data (Feb 10-18, 2026) confirmed that behavioral moments outperform persona-identity keywords. Users don't search "family meal planner" or "busy mom meal planner" — they search "what to cook for dinner" (the plan fell apart) or "tired of hello fresh" (the subscription failed them).

**This principle applies directly to Pinterest:** Target the behavioral search moment (what people are *doing*), not the persona label. Content should be organized around the problems and actions our personas share, not their self-identifiers.

### 2.4 Competitive Positioning on Pinterest

Every food blogger on Pinterest answers "what should I cook tonight?" one recipe at a time. The entire competitive landscape — Allrecipes, Taste of Home, Pinch of Yum, TheLazyDish, Mom on Timeout, and thousands of others — is recipe-level content.

**Slated's angle:** "What should your family eat *this week*?" — plan-level content, not just meal inspiration. The gap between recipe-level content and plan-level content is where this strategy lives.

Individual recipes are necessary for volume sustainability, Rich Pin eligibility, and search coverage. But they are the vehicle, not the destination. Recipes are contextualized within plans wherever possible, and every standalone recipe blog post includes CTAs that reframe toward planning and family participation.

### 2.5 Dinner Draft as Strategic Theme

Dinner Draft is not a feature of one pillar — it is a strategic theme that runs through the entire content strategy. It serves both personas for different reasons:

- **For the HVP:** Dinner Draft is a **delegation feature**. They push the plan out, the family approves, the HVP is out of the loop entirely. The plan goes from "system generates it" to "family ratifies it" without the HVP being the bottleneck.
- **For the Peacekeeper:** Dinner Draft is a **consensus feature**. The invisible work becomes visible. The family votes. When someone complains on Wednesday, the answer is "you already agreed to this."

**How Dinner Draft appears across the strategy:**
- **In blog post CTAs** — every pillar's CTA language includes a Dinner Draft angle (see Section 10)
- **In Pillar 2 (Everyone Eats)** — Dinner Draft is the centerpiece, framed as the system that solves family dinner friction broadly (not just picky eaters)
- **In Pillar 1 (Your Whole Week, Planned)** — "Your family already agreed to this plan"
- **In Pillar 4 (Smarter Than a Meal Kit)** — "Your family votes on the plan, unlike a box that decides for you"
- **In Pillar 5 (Your Kitchen, Your Rules)** — "Even with gluten-free + picky eater + 30-minute constraints, your family still gets a vote"

Dinner Draft should NOT appear on pins themselves (pins are search-optimized, useful content with no hard sell). It appears in the blog post layer where the CTA lives.

### 2.6 Content Funnel

Not all content serves the same purpose. The content library operates across three funnel layers:

| Layer | Purpose | % of Weekly Pins | Content Types |
|---|---|---|---|
| **Discovery** | Earn saves, build library, build domain quality. Genuinely useful content that attracts our personas at the behavioral moment. | 55-65% | Recipe pins (standalone and pulled from plans), dinner idea listicles, dietary-specific recipes |
| **Consideration** | Earn clicks, drive blog reads, introduce the planning concept. Content that shifts the user from "I need a recipe" to "I need a system." | 20-30% | Weekly plan showcases, meal planning guides, family strategy content, tips/how-tos |
| **Conversion** | Drive app awareness, position Slated as the solution. Problem-solution content with clear CTA. | 10-15% | Problem-solution pins (family dynamics, meal kit alternatives, "stop the dinner argument") |

The discovery layer builds the audience and the domain. The consideration layer reframes the problem. The conversion layer presents the solution. Most pins should be genuinely useful without mentioning Slated at all — the blog post CTA handles the conversion.

---

## 3. Content Pillars

Five pillars. Plan-level and family-dynamics content leads the strategy (~55-65% combined). Standalone recipes provide volume sustainability and search coverage (~18-21%). Behavioral intercept and long-tail content fill the remaining share.

### Pillar 1: "Your Whole Week, Planned" — Plan-Level Content

**Strategic purpose:** Primary differentiator AND volume driver. This is where Slated stands alone on Pinterest. Each blog post is a complete weekly meal plan containing 5 full recipes — which means a single blog post generates multiple pins (1 plan-level pin + individual recipe pulls from within the plan). This structure delivers both differentiation (the plan framing) and recipe search coverage (individual recipe pins).

**Maps to search clusters:** "Weekly Meal Plan" / "Meal Planning" (Cluster 2) + recipe pulls cover "What to Cook for Dinner" (Cluster 1) and "Easy Weeknight Dinners" (Cluster 3)

**Funnel layer:** Consideration (plan-level pins) + Discovery (recipe pull pins)

**Content angle:** Complete weekly meal plans with full recipes inside. Blog posts show the output of meal planning — "here's your whole week, with a combined grocery list." The blog posts are the proof of concept; the app is the automated version. Dinner Draft threads through: "your family already agreed to this plan before you bought the groceries."

**How pins work for this pillar:**
- **Plan-level pins** (Tip/How-To or Listicle template): "This Week's Family Dinner Plan — 5 Easy Meals, One Grocery List." These target planning-intent searches.
- **Recipe pull pins** (Recipe Pin template): Individual recipes pulled from within the plan post. "One-Pan Lemon Herb Chicken — from This Week's Family Dinner Plan." These target recipe searches but link to the same plan blog post, giving the user the recipe AND the planning context.

**Blog post structure:** Guide type containing 5 embedded recipes, each with full Recipe schema markup (enabling Rich Pins for the recipe pull pins). Combined grocery list. CTA positions Slated as the automated version of what the blog post demonstrates.

**Pin templates used:** Tip/How-To Pin (plan-level), Listicle Pin (plan-level), Recipe Pin (recipe pulls)

**Target search terms:**

| Priority | Search Terms |
|---|---|
| Primary (plan-level pins) | weekly meal plan, meal planning, weekly dinner plan, meal plan for the week, family meal planning |
| Primary (recipe pull pins) | what to cook for dinner, easy dinner ideas, easy weeknight dinners, dinner ideas for family, 30 minute meals |
| Secondary | meal planning for beginners, quick weeknight dinners, simple dinner recipes, one pot meals |
| Tertiary | busy mom weekly meal plan, meal prep for busy families, meal planning template |

**Weekly volume:** 9-10 pins (~32-36% of weekly total)
- 2 new plan blog posts/week → 2 plan-level pins + 4-6 recipe pull pins
- 2-4 fresh treatments of prior plan post URLs

**ASA validation:** "Weekly meal plan" at $17.56 CPI / 17% CR. "What to cook for dinner" at $3.47 / 100% CR. "Dinner ideas for family" at $4.81 / 50% CR.

---

### Pillar 2: "Everyone Eats, Nobody Argues" — Family Dynamics Content

**Strategic purpose:** Blue ocean. This is where Slated has zero competition. Massive Pinterest engagement exists for picky eater and family dinner content (TheLazyDish's picky eater post: 1M+ Pinterest shares), but ALL of it is recipe-level. Nobody addresses the systemic problem: how do you plan a whole week when everyone has different preferences, and how do you get buy-in before cooking starts?

This pillar is broader than picky eaters. It covers the full spectrum of family dinner friction: picky kids, dietary splits within the family, the "what's for dinner" complaint cycle, the invisible burden of solo meal planning, the short-order cook trap. Dinner Draft is the centerpiece — framed as the solution to all of these dynamics, not just pickiness.

**Maps to search cluster:** "Picky Eaters" / Family Preference Conflicts (Cluster 4) — but expanded beyond picky eaters into broader family harmony

**Funnel layer:** Mix of Discovery (kid-friendly recipes, picky eater recipes) and Conversion (system-level problem-solution content)

**Content angle — two sub-streams:**
1. **Recipe-level content** (Discovery): Kid-approved recipes, picky eater dinners, hidden veggie recipes, meals the whole family will eat. These compete in the high-engagement picky eater space and earn saves.
2. **System-level content** (Conversion): Content that reframes family dinner friction as a *planning and buy-in* problem, not just a recipe problem. "How to get your family to agree on dinner before you start cooking." "Stop being the short-order cook." This is where Dinner Draft is the answer nobody else on Pinterest has.

**Pin templates used:** Problem-Solution Pin (system content), Recipe Pin (family-friendly recipes), Listicle Pin

**Blog post types:** Guide (family dynamics strategies, Article schema), Recipe (kid-friendly, Schema.org Recipe markup → Rich Pins), Listicle

**Target search terms:**

| Priority | Search Terms |
|---|---|
| Primary | dinner ideas for picky eaters, kid friendly dinners, easy dinners kids will eat, family friendly meals |
| Primary | meals for picky families |
| Secondary | picky eater meal ideas, hidden veggie recipes, toddler dinner ideas |
| Secondary | vegetarian family meals (the "my teenager just went vegetarian" scenario) |
| Tertiary | food for fussy eaters (UK/AU variant) |

**Weekly volume:** 7-8 pins (~25-29% of weekly total)
- 1-2 new recipe blog posts/week (kid-friendly, family-approved)
- 1 guide blog post every 1-2 weeks (system-level, Dinner Draft-centric)
- Fresh treatments of prior family-content URLs

**ASA note:** "Picky eater meals" generated taps but 0 installs in ASA. Pinterest is a fundamentally different context — mid-funnel inspiration/planning vs. high-intent app search. The system-level content (Dinner Draft positioning) has zero competition on Pinterest. Do not let the ASA non-conversion disqualify this cluster.

---

### Pillar 3: "Dinner, Decided" — Standalone Recipe Content

**Strategic purpose:** Volume backbone for content sustainability. At 4 pins/day sustained indefinitely, Pillars 1, 2, 4, and 5 cannot produce enough unique topics to fill the content pipeline alone. Recipes have essentially infinite topic space. This pillar provides the steady stream of individual recipe content that keeps the library growing and the posting cadence consistent.

**Critical framing:** These are NOT generic food blogger recipes. They are short, practical, family-tested, and every blog post includes CTAs that reframe toward planning ("want your whole week of dinners like this one?") and Dinner Draft ("what if your family voted on the plan before you cooked?"). The recipe is the hook. The plan is the message.

**What makes Slated's recipe content different from food bloggers:**
- Shorter intros (no 800-word preamble about a trip to Tuscany)
- Realistic time estimates
- Practical substitution notes
- Family-tested framing ("your whole family will eat this")
- "This could be your Tuesday" positioning — the recipe as one night in a planned week

**Maps to search clusters:** "What to Cook for Dinner" (Cluster 1) + "Easy Weeknight Dinners" (Cluster 3)

**Funnel layer:** Discovery

**Pin templates used:** Recipe Pin (primary), Listicle Pin

**Blog post types:** Recipe (Schema.org Recipe markup → Rich Pins)

**Target search terms:**

| Priority | Search Terms |
|---|---|
| Primary | what to cook for dinner, easy dinner ideas, dinner ideas for family, what to make for dinner |
| Primary | easy weeknight dinners, quick weeknight dinners, 30 minute meals, simple dinner recipes |
| Secondary | last minute dinner ideas, one pot meals, one pan dinners, 15 minute meals |
| Secondary | easy family dinner recipes, weeknight dinner ideas, quick family meals |

**Weekly volume:** 5-6 pins (~18-21% of weekly total)
- 3-4 new standalone recipe blog posts/week
- 1-2 fresh treatments of prior recipe URLs

---

### Pillar 4: "Smarter Than a Meal Kit" — Life After Subscriptions

**Strategic purpose:** Behavioral intercept at a proven conversion moment. ASA data shows Meal Kit Breakup was the highest-volume conversion source (12 installs, $7.09 CPI, 18.5% CR). On Pinterest, this translates to evergreen content for people cycling through meal kit subscriptions.

**Maps to search cluster:** "Meal Kit Alternative" / Subscription Exit (Cluster 5)

**Funnel layer:** Primarily Conversion

**Content angle:** "What comes next" content for people leaving or questioning meal kits. Not attacking meal kits — empathizing with the frustration and presenting home cooking with a plan as the better alternative. Dinner Draft angle: "Your family votes on the plan, unlike a box that decides for you."

**Important nuance:** On Pinterest, this is less about intercepting acute frustration (that's ASA's strength) and more about providing the "what comes next" content for people in the consideration phase. Pinterest users plan ahead — someone pinning "hello fresh alternative" may not cancel for weeks, but the pin is saved and returns to them when ready.

**Pin templates used:** Problem-Solution Pin (primary), Listicle Pin, Tip/How-To Pin

**Blog post types:** Guide (comparison/alternative content), Listicle

**Target search terms:**

| Priority | Search Terms |
|---|---|
| Primary | hellofresh alternative, better than hello fresh |
| Secondary | meal kit comparison, hello fresh vs home cooking |
| Secondary | tired of hello fresh, tired of meal kits |
| Tertiary | cancel hello fresh, cheaper than hellofresh |

**Weekly volume:** 2-3 pins (~7-10% of weekly total)

**Note on volume:** This cluster has lower Pinterest search volume. The conversion intent is high but the addressable audience is smaller. After the first 10-15 unique blog posts are created (Month 1-2), this pillar runs primarily on fresh pin treatments.

---

### Pillar 5: "Your Kitchen, Your Rules" — Personalized Planning

**Strategic purpose:** Long-tail search coverage that demonstrates Slated's combinatorial advantage. While a food blogger can publish "10 gluten-free instant pot dinners," Slated can generate personalized plans that combine multiple constraints. This pillar covers dietary-specific and appliance-specific content, plus grocery integration content that shows the full plan → list → delivery chain.

**Maps to search clusters:** Dietary & Health-Specific Planning (Cluster 7) + Grocery/Shopping Integration (Cluster 6)

**Funnel layer:** Mix of Discovery (dietary/appliance recipes) and Consideration (constraint-combination content, grocery integration)

**Content angle:** Dietary-specific recipes and meal plans (gluten-free, keto, high protein, dairy-free, etc.) and appliance-specific content (air fryer, instant pot, slow cooker). The Slated angle: showing how the app handles families with *multiple simultaneous constraints* — "gluten-free AND kid-friendly AND under 30 minutes" is trivial for Slated but impossible for any single food blog post. Dinner Draft angle: "even with all these constraints, your family still gets a vote."

Also includes grocery integration content: the plan → list → Instacart chain that demonstrates Slated's full value proposition.

**Pin templates used:** Recipe Pin (dietary/appliance recipes), Tip/How-To Pin (constraint-combination content), Listicle Pin

**Blog post types:** Recipe (dietary-specific Schema.org markup), Guide, Listicle

**Target search terms:**

| Priority | Search Terms |
|---|---|
| Primary | gluten free dinner ideas, high protein dinner recipes, air fryer dinner recipes |
| Primary | instant pot dinner ideas, slow cooker family meals |
| Secondary | keto meal plan, low carb meal plan, dairy free dinner ideas |
| Secondary | vegetarian family meals, anti-inflammatory recipes |
| Secondary | meal plan with grocery list, grocery list for the week |
| Tertiary | kid friendly healthy meals, pantry meal ideas, pantry staple recipes |

**Weekly volume:** 4-5 pins (~14-18% of weekly total)
- Rotate through dietary types week-to-week to build coverage across all
- 1-2 appliance-specific pins/week
- 1 grocery integration pin/week

---

### Pillar Mix Summary

| Pillar | Weekly Pins | % of Total | Primary Purpose |
|---|---|---|---|
| 1: Your Whole Week, Planned | 9-10 | 32-36% | Differentiator + volume (plan posts generate multiple pins) |
| 2: Everyone Eats, Nobody Argues | 7-8 | 25-29% | Blue ocean, Dinner Draft, family harmony positioning |
| 3: Dinner, Decided | 5-6 | 18-21% | Recipe volume backbone, search coverage, domain quality |
| 4: Smarter Than a Meal Kit | 2-3 | 7-10% | High-intent behavioral intercept |
| 5: Your Kitchen, Your Rules | 4-5 | 14-18% | Long-tail search coverage, combinatorial advantage |
| **Total** | **28** | **100%** | |

**Key structural point:** Pillars 1 and 2 together represent ~57-65% of weekly pins. This is the differentiated content — plan-level and family-dynamics — that no food blogger competes with. Pillar 3 (standalone recipes) provides the volume sustainability at ~18-21%, which is necessary but not the strategic identity.

This mix is a starting point. The weekly analysis will adjust ratios based on per-pillar performance data. The monthly review is where structural pillar adjustments happen.

### Blog Post Production Model

Pins and blog posts are different units. A single blog post can generate multiple pins (especially plan posts). Here is the weekly blog post production target:

| Blog Post Type | Posts/Week | Pillar | Pins Generated Per Post | Notes |
|---|---|---|---|---|
| Weekly meal plan (5 recipes inside) | 2 | Pillar 1 | 5-6 (1 plan-level + 4-5 recipe pulls) | Highest-value posts. Recipe schema on each embedded recipe enables Rich Pins. |
| Family-friendly / picky eater recipe | 1-2 | Pillar 2 | 1-2 | Kid-approved recipes, hidden veggie, etc. |
| Family dynamics guide | 0.5-1 | Pillar 2 | 1-2 | System-level content, Dinner Draft. Topic space is finite — tapers after Month 2-3. |
| Standalone recipe | 3-4 | Pillar 3 | 1-2 | Volume backbone. Infinite topic space. |
| Meal kit alternative guide | 0.5 | Pillar 4 | 1 | Narrow topic space. Mostly fresh treatments after Month 2. |
| Dietary/appliance recipe or guide | 1-2 | Pillar 5 | 1-2 | Rotate dietary types weekly. |
| **Total new blog posts/week** | **~8-10** | | | |

**Important: these are launch-phase production rates (Month 1-2).** At this volume, most of the 28 weekly pins are Treatment 1 (new blog post pins), leaving limited room for fresh treatments. As the blog library matures, blog post production tapers:

| Phase | New Blog Posts/Week | Treatment 1 Pins | Fresh Treatment Pins | Notes |
|---|---|---|---|---|
| Month 1-2 (Library Build) | 8-10 | ~16-22 | ~6-12 | Priority: populate boards and build search coverage |
| Month 3-4 (Optimization) | 4-6 | ~8-12 | ~16-20 | Blog library is 80-100+ posts; fresh treatments of proven URLs become the majority |
| Month 5+ (Steady State) | 2-4 | ~4-8 | ~20-24 | New content fills gaps identified by performance data; most pins are fresh treatments of compounding assets |

The blog production model above describes the launch phase. The steady-state production rate is determined by the monthly review based on keyword coverage gaps and performance data.

---

## 4. Board Architecture

Boards are classification signals, not just organizational tools. The board where a pin is first saved directly influences how Pinterest categorizes and distributes it (confirmed as a ranking factor in 2025). Board names must be keyword-rich and topically specific.

### Board Structure

| Board Name | Maps to Pillar | Description (keyword-rich, for Pinterest SEO) | Sections |
|---|---|---|---|
| **Weekly Meal Plans & Meal Planning Tips** | 1 | Weekly meal plans, meal planning guides, and tips for planning dinner for the whole week. Stop wondering what to cook — plan your whole week in minutes. | Weekly Meal Plans, Meal Planning for Beginners, Meal Prep Ideas |
| **Quick Weeknight Dinner Recipes** | 1, 3 | Easy weeknight dinner recipes ready in 30 minutes or less. Simple family dinners for busy nights when you need dinner on the table fast. | 30 Minute Dinners, One-Pan Meals, 15 Minute Meals |
| **Easy Dinner Ideas for Families** | 1, 3 | Simple dinner ideas the whole family will love. Easy recipes for family dinners on busy weeknights — no complicated ingredients or techniques. | Chicken Dinners, Pasta Dinners, Comfort Food |
| **Family Dinner Ideas Even Picky Eaters Love** | 2 | Kid-approved dinner recipes and family meal ideas for households with picky eaters. Meals everyone will actually eat — no more dinnertime battles. | Kid-Friendly Dinners, Hidden Veggie Recipes, Feeding Picky Families |
| **Family Meal Planning Strategies** | 2 | How to get your family on board with dinner. Strategies for meal planning with picky eaters, dietary differences, and busy schedules — so everyone agrees before you cook. | Getting Family Buy-In, Picky Eater Strategies, Weeknight Survival |
| **Better Than a Meal Kit** | 4 | Meal kit alternatives and home cooking strategies for families tired of subscription boxes. Better food, more flexibility, less cost than Hello Fresh and Blue Apron. | Meal Kit Alternatives, Why We Quit Meal Kits |
| **Healthy Family Dinner Recipes** | 5 | Healthy dinner recipes for families — high protein, anti-inflammatory, and nutritious meals everyone will eat. Healthy doesn't have to mean complicated. | High Protein Dinners, Anti-Inflammatory Recipes, Healthy Kid-Friendly Meals |
| **Gluten-Free Dinner Ideas** | 5 | Gluten-free dinner recipes and weekly meal plan ideas. Easy gluten-free meals for families managing celiac, intolerance, or gluten-free lifestyles. | Quick Gluten-Free Meals, Gluten-Free Meal Plans |
| **Air Fryer & Instant Pot Dinner Recipes** | 5 | Air fryer dinner recipes and Instant Pot family meals. Quick, easy appliance-based recipes for weeknight dinners. | Air Fryer Dinners, Instant Pot Meals, Slow Cooker Family Dinners |
| **Meal Planning & Grocery Tips** | 1, 5 | Meal planning tips, grocery list organization, and strategies to get dinner on the table with less stress. From plan to plate to groceries — the whole system. | Grocery List Tips, Pantry Meal Ideas, Meal Plan to Grocery List |

**Total: 10 boards** (expandable as content library grows — e.g., add a "Keto & Low Carb Meal Plans" board once enough content exists to populate it with 20+ pins)

### Board Rules

1. **Every new pin is saved to one specific, topically relevant board first.** The first board assignment is the strongest classification signal. Never save a pin to a generic or mismatched board first.
2. **Board names use full keyword phrases, not abbreviations.** "Quick Weeknight Dinner Recipes" not "Weeknight Recipes" or "Dinners."
3. **Board descriptions are 2-3 sentences of natural, keyword-rich language.** Not keyword spam — conversational but SEO-conscious.
4. **Each board should have a minimum of 20 pins before the account is expected to rank for that board's topics.** During launch, prioritize filling the highest-priority boards first (Pillars 1 and 2).
5. **Sections within boards provide additional classification.** Use sections to sub-categorize without creating boards too narrow to populate.

---

## 5. Content Types & Pin Templates

### 5.1 Blog Post Types

Every pin links to a blog post on goslated.com. Blog posts are the conversion surface — they deliver the value promised by the pin and present Slated as the natural next step.

| Blog Post Type | Triggered by `type` field | Schema.org Markup | Avg. Length | Best For |
|---|---|---|---|---|
| **Weekly Plan** | `type: "weekly-plan"` | `@type: Article` + multiple embedded `@type: Recipe` entries (each enables Rich Pins) | 1,200-1,800 words | Pillar 1 plan posts — the primary content format |
| **Recipe** | `type: "recipe"` | `@type: Recipe` (enables Rich Pins — ingredients, cook time, servings display on pin) | 600-800 words | Pillar 2 family recipes, Pillar 3 standalone recipes, Pillar 5 dietary recipes |
| **Guide** | `type: "guide"` | `@type: Article` | 800-1,200 words | Pillar 2 family strategy guides, Pillar 4 meal kit alternative content |
| **Listicle** | `type: "listicle"` | `@type: Article` + optional embedded `@type: Recipe` entries | 800-1,200 words | Roundup content across all pillars (e.g., "7 High-Protein Dinners") |

**Weekly Plan posts are the highest-value format** because they embed multiple recipes with Schema.org markup (multiple Rich Pin opportunities per post) while delivering the plan-level differentiation that no competitor offers.

### 5.2 Pin Image Templates

| Template | Use Case | Image Treatment | Text Overlay | Dimensions |
|---|---|---|---|---|
| **Recipe Pin** | Individual recipe content (all pillars) | Food photo fills top 60-70%, semi-transparent overlay bar bottom 30-40% | Recipe name (6-8 words max) + brief descriptor (e.g., "Ready in 25 Minutes") | 1000x1500px (2:3) |
| **Tip/How-To Pin** | Meal planning tips, weekly plans, guides (Pillars 1, 2, 5) | Lifestyle/background image, heavier text overlay | Tip headline + 2-3 bullet points | 1000x1500px (2:3) |
| **Listicle Pin** | Roundup content (all pillars) | Collage or single image with strong overlay | Number + title, optional list items | 1000x1500px (2:3) |
| **Problem-Solution Pin** | Pain point → solution (Pillars 2, 4) | Split or gradient design | Problem statement top, solution bottom | 1000x1500px (2:3) |
| **Infographic Pin** | Step-by-step guides (Pillars 1, 2) | Minimal/graphic background, brand color palette | Multiple text blocks, numbered steps, icons | 1000x1500px (2:3) |

Each template gets 2-3 visual variants (different color treatments, layout variations) to prevent the same template type from looking identical across pins. The automation system selects variants to maintain visual diversity.

### 5.3 Image Source Assignment

| Content Type | Primary Image Source | Backup Source | Rationale |
|---|---|---|---|
| Recipe pins | Tier 1: Stock photo (Unsplash/Pexels) | Tier 2: AI generation | Food photography is more realistic from stock than AI. Stock is free. |
| Lifestyle/aspirational | Tier 2: AI generation | Tier 1: Stock photo | Custom compositions for scenes stock may not have |
| Tips/How-to | Tier 3: Template-only (brand palette backgrounds) | Tier 1: Stock photo | Value is in the text/information, not photography |
| Listicle | Tier 1: Stock photo OR Tier 3: Template-only | — | Depends on whether the listicle is recipe-focused or tip-focused |
| Problem-solution | Tier 3: Template-only OR Tier 2: AI generation | — | Clean design emphasizes the message |
| Infographic | Tier 3: Template-only | — | Pure information design |

---

## 6. Brand Voice on Pinterest

### 6.1 Voice Principles

Slated's Pinterest voice is the voice of a friend who's already figured out the dinner system — and is happy to share. Not an expert lecturing from above. Not a brand selling. A real person who gets the struggle and has a practical solution.

| Principle | What It Sounds Like | What It Does NOT Sound Like |
|---|---|---|
| **Warm but not saccharine** | "This one's a family favorite for a reason." | "OMG you're going to LOVE this!!" |
| **Practical, not preachy** | "Ready in 25 minutes, one pan, minimal cleanup." | "You SHOULD be meal planning. Here's why." |
| **Confident, not aggressive** | "Your whole week of dinners, planned." | "STOP wasting time! Download NOW!" |
| **Empathetic to the struggle** | "When it's 5 PM and the fridge is a mystery." | "If you don't plan, you'll fail your family." |
| **Solution-oriented** | "Here's your Tuesday dinner. And Wednesday. And Thursday." | "Dinner planning is SO hard, isn't it?" |
| **Never guilt-inducing** | "Takeout happens. Next week doesn't have to be the same." | "Stop feeding your kids junk food." |

### 6.2 Voice by Pin Component

**Pin Title (100 chars max, ~40-50 visible in feed):**
- Lead with the most important keyword phrase
- Use natural language, not keyword chains
- Be specific — "25-Minute Chicken Stir Fry" beats "Easy Dinner Recipe"
- Numbers work: "7 Easy Weeknight Dinners Your Family Will Actually Eat"

**Pin Description (500 chars max, ~50-60 visible in preview):**
- First sentence: primary keyword phrase, naturally written
- Middle: secondary keywords woven into genuinely useful context
- End: what the user gets if they click (the promise)
- Length: 250-500 characters. Always use the space — longer descriptions provide more keyword signals.
- No hashtags (deprecated on Pinterest, waste of space)
- No calls to action in the description (Pinterest penalizes engagement bait)

**Alt Text (500 chars max):**
- Describe what's IN the image + include primary keyword
- Alt text is confirmed to improve impressions by ~25% (Tailwind study). Always fill it in.

**Text Overlay on Pin Images:**
- 6-8 words maximum for headline
- Must be readable at ~300px thumbnail width (mobile feed)
- Reinforces the pin's topic for both human attention and Pinterest's computer vision

---

## 7. Keyword Strategy

### 7.1 Keyword Principles

1. **Keywords early in descriptions carry more weight.** Lead the pin description with the primary keyword phrase.
2. **Natural language over keyword stuffing.** Pinterest's AI detects unnatural cramming. Write for humans first, keywords second.
3. **Pinterest indexes keywords from:** pin titles, pin descriptions, board names/descriptions, image alt text, text overlay in images (via computer vision), and linked web page content. Optimize all six surfaces.
4. **Pinterest autocomplete reveals real search queries.** Use it as a free keyword research tool when updating keyword lists.
5. **97% of Pinterest searches are unbranded.** Never use "Slated" as a target keyword in pin copy — users don't search for us. We want to appear in the searches they already make.

### 7.2 Primary Keyword Map

This map drives keyword assignments in the weekly content plan. Each pin gets 1 primary keyword and 2-3 secondary keywords.

| Pillar | Primary Keywords (use as pin title leads) | Secondary Keywords (weave into descriptions) |
|---|---|---|
| 1: Your Whole Week, Planned | weekly meal plan, meal planning, weekly dinner plan, family meal planning, meal plan for the week, easy dinner ideas, easy weeknight dinners, 30 minute meals | meal planning for beginners, what to cook for dinner, dinner ideas for family, quick weeknight dinners, simple dinner recipes, one pot meals, busy mom weekly meal plan |
| 2: Everyone Eats, Nobody Argues | dinner ideas for picky eaters, kid friendly dinners, family friendly meals, meals for picky families, easy dinners kids will eat | picky eater meal ideas, hidden veggie recipes, toddler dinner ideas, vegetarian family meals, kid friendly healthy meals |
| 3: Dinner, Decided | what to cook for dinner, easy dinner ideas, dinner ideas for family, easy weeknight dinners, quick weeknight dinners, 30 minute meals | simple dinner recipes, weeknight dinner ideas, last minute dinner ideas, one pot meals, one pan dinners, 15 minute meals, what to make for dinner |
| 4: Smarter Than a Meal Kit | hellofresh alternative, better than hello fresh, meal kit alternative | meal kit comparison, tired of meal kits, hello fresh vs home cooking |
| 5: Your Kitchen, Your Rules | gluten free dinner ideas, high protein dinner recipes, air fryer dinner recipes, instant pot dinner ideas, slow cooker family meals | keto meal plan, dairy free dinner ideas, anti-inflammatory recipes, meal plan with grocery list, kid friendly healthy meals |

### 7.3 Negative Keywords (Topics to Avoid)

These search terms attract excluded personas or misaligned audiences. Do NOT create content optimized for these terms:

| Avoid | Reason |
|---|---|
| cheap meals, budget meals, save money on food, frugal meal planning | Attracts Budget Optimizer persona — will not convert |
| gourmet recipes, authentic [cuisine], from scratch, restaurant quality | Attracts Perfectionist persona — will not convert |
| meal plan to lose weight, weight loss meal plan, diet meal plan, calorie counting | Weight loss positioning misaligns with Slated's value prop (cognitive relief, not diet compliance) |
| baby food, baby led weaning, infant feeding | Too young for Slated's family planning use case |

**Caveat:** Some budget-adjacent terms are acceptable when the primary intent is convenience, not savings. "Pantry meal ideas" (use what you have = less shopping = convenience) is fine. "Cheapest meals to feed a family" (cost-primary) is not.

---

## 8. Fresh Pin Strategy

Pinterest algorithmically rewards "fresh pins" — new images, even linking to existing content. Reposting the same image is penalized. Creating multiple visual treatments for the same blog post URL is rewarded.

### 8.1 Fresh Pin Production Model

For each blog post (URL), produce pin treatments over time:

| Treatment | Timing | What Changes | Purpose |
|---|---|---|---|
| **Treatment 1** | Published with blog post | Primary pin — best image, primary keyword lead | Initial distribution test |
| **Treatment 2** | Week 2-3 after publication | Different image (stock or AI), different angle in title (e.g., time-saving → health → kid-friendliness) | Reach different search queries with same content |
| **Treatment 3** | Week 4-6 after publication | Different pin template type (e.g., recipe pin → listicle pin), different keyword lead | Expand to different distribution surfaces |
| **Treatment 4-5** | Month 2-3 or seasonal refresh | Seasonal angle or performance-based re-treatment | Capitalize on seasonal trends, refresh for algorithm |

**Special case — Weekly Plan posts:** These generate multiple Treatment 1 pins simultaneously (1 plan-level pin + individual recipe pulls). Each recipe pull is a distinct image with a distinct keyword lead, so they all count as fresh pins despite linking to the same URL.

### 8.2 Fresh Pin Rules

1. **Every new image counts as a fresh pin.** Different photo, different overlay, different template = fresh.
2. **Same image reposted = not fresh.** Even to a different board. The algorithm detects duplicate images.
3. **Different copy with same image = NOT fresh.** The image is the freshness signal, not the text.
4. **Maximum 5 pin treatments per URL in the first 60 days.** Beyond that, space treatments further apart (one per month). Exception: Weekly Plan posts can have 5-6 Treatment 1 pins at launch (plan pin + recipe pulls) since each is a genuinely different image.
5. **High-performing blog posts get more treatments than low-performing ones.** The weekly analysis identifies top-performing URLs for additional fresh pin creation.

### 8.3 Weekly Fresh Pin Mix

The Treatment 1 / fresh treatment ratio shifts as the blog library matures:

| Phase | Treatment 1 Pins | Treatment 2-5 Pins | Ratio |
|---|---|---|---|
| Month 1-2 (Library Build) | ~16-22 | ~6-12 | Heavy new content — building the library |
| Month 3-4 (Optimization) | ~8-12 | ~16-20 | Balanced — filling gaps + treating proven URLs |
| Month 5+ (Steady State) | ~4-8 | ~20-24 | Mostly compounding — fresh treatments of proven assets |

See the Blog Post Production Model in Section 3 for the corresponding blog post output at each phase.

The content log tracks which URLs have been treated and how many times. The weekly content plan generator checks this log and prioritizes URLs that (a) have strong performance data and (b) haven't been freshly treated recently.

---

## 9. Posting Cadence & Schedule

### 9.1 Daily Volume

**Target: 4 pins per day (28/week)**

This is within the recommended 3-10 fresh pins/day range. Starting at 4 provides a consistent, sustainable base. The monthly review may recommend increasing to 5-6 if the pipeline can produce quality at that volume.

### 9.2 Daily Posting Schedule

| Time Slot | ET Time | Rationale |
|---|---|---|
| Morning | 10:00 AM | Mid-morning browsing, pre-lunch planning |
| Afternoon | 3:00 PM | Afternoon break, pre-dinner thinking |
| Evening (primary) | 8:00 PM | Peak Pinterest usage window (8-11 PM) |
| Evening (secondary) | — | 4th pin added to 8 PM slot or split to 9:30 PM if volume increases |

**Jitter:** Each post time has +/-15 minutes of random jitter to avoid looking automated.

### 9.3 Day-of-Week Patterns

Pinterest engagement is highest Friday through Monday. The posting schedule is uniform (4/day every day), but the content plan should front-load the highest-quality and most conversion-oriented pins to Friday-Monday slots when possible.

### 9.4 Consistency Rule

**Post every single day.** Pinterest's algorithm penalizes accounts that go quiet and then burst. Missing a day is worse than posting slightly weaker content. The automation pipeline's daily cron ensures this, but if the approval gate isn't cleared by Sunday, zero pins post Monday. The strategy depends on timely human approval.

---

## 10. CTA Strategy

### 10.1 CTA Placement Principle

Pins themselves should be genuinely useful content with NO hard sell. The blog post is where the CTA lives. The flow:

```
Pin (useful content, earns save/click)
  → Blog post (delivers promised value)
    → CTA (natural, contextual, after value is delivered)
      → App Store / goslated.com download page
```

### 10.2 Blog Post CTA Framework

Every blog post has two CTA placements:

| Placement | Location | Style | Tone |
|---|---|---|---|
| **Mid-post CTA** | After the 2nd or 3rd section (recipe: after ingredients; guide: after first major section) | Inline text callout — not a banner or popup. Feels like a natural aside. | Contextual to the content. Always includes BOTH a planning angle and a Dinner Draft angle. |
| **End-of-post CTA** | After the final content section, before comments/footer | Dedicated `BlogCTA` component — branded, with App Store badge | Slightly more direct. Includes Slated tagline + key feature mention. |

### 10.3 CTA Copy by Pillar

| Pillar | Mid-Post CTA | End-of-Post CTA |
|---|---|---|
| **1: Your Whole Week, Planned** | "This plan took us 20 minutes to build. Slated does it in 2 — personalized for your family's dietary needs, preferences, and schedule. Your family can even vote on the plan before you buy a single grocery." | "Slated: Your whole week of dinners, planned in minutes. Personalized meal plans, family voting, and one-tap Instacart ordering. [Try it free for 14 days.]" |
| **2: Everyone Eats, Nobody Argues** | "What if your family could vote on the meal plan before you cook? Slated's Dinner Draft generates recipe options based on your family's preferences, sends them to everyone to vote on, and builds the winning plan automatically. No spreadsheet required." | "Your family's input before dinner. Not their complaints after. Slated's Dinner Draft lets everyone vote on the meal plan — then builds your grocery list and sends it to Instacart. [Try it free.]" |
| **3: Dinner, Decided** | "This is one dinner. Want the other four nights handled too? Slated builds a personalized weekly plan around your family's preferences — and everyone gets to vote on it before you buy the groceries." | "Slated: Dinner on Autopilot. A full week of dinners like this one, built for your family. [Try it free for 14 days.]" |
| **4: Smarter Than a Meal Kit** | "Slated builds weekly meal plans around your family's actual preferences — dietary restrictions, picky eaters, cooking time, all of it. Then your family votes on the plan via Dinner Draft. No box decides for you." | "Better than a meal kit. Personalized weekly plans, family voting, and one-tap Instacart grocery ordering. [Try Slated free for 14 days.]" |
| **5: Your Kitchen, Your Rules** | "Slated handles [dietary need] automatically — combined with kid-friendly, time limits, or whatever other constraints your family needs. Your family votes on the plan, and the grocery list goes straight to Instacart." | "16 dietary restrictions. 12 nutritional focus options. Built for your family, voted on by your family. [Try Slated free for 14 days.]" |

### 10.4 UTM Parameters

Every pin's link includes UTM parameters for attribution tracking:

```
goslated.com/blog/[slug]?utm_source=pinterest&utm_medium=organic&utm_campaign=[board_name]&utm_content=[pin_id]
```

This enables tracking which pillars, boards, and individual pins drive traffic in the weekly analysis.

---

## 11. Seasonal Content Calendar

Pinterest users search for seasonal content 60-90 days in advance. Content must be published well ahead of the actual season. The weekly content plan generator checks this calendar and injects seasonal content into the plan at the appropriate times.

### 11.1 Seasonal Overlays

| Season/Moment | Peak Search | Content Publish Window | Relevant Pillars | Content Angle for Slated |
|---|---|---|---|---|
| **New Year / Eat Healthier** | Jan 1-31 | Nov-Dec (prior year) | 1, 5 | "Start the year with dinner on autopilot" — resolution content framed as a system, not willpower. Healthy meal plans, high protein, anti-inflammatory. |
| **Spring / Lighter Meals** | Mar-May | Jan-Mar | 1, 3, 5 | Seasonal recipe refreshes. "Refresh your meal plan for spring." Light, fresh dinner ideas. |
| **Summer / Grilling** | Jun-Aug | Apr-Jun | 1, 3, 5 | "Too hot to think about dinner." Easy summer meals, grilling, no-cook dinners. |
| **Back to School** | Aug-Sep | **Jun-Jul** | **1, 2** | **HIGH VALUE.** Parents re-entering structured schedules need meal plans. "Back to school meal plan" content. This is when Peacekeeper pain intensifies — school schedules compress weeknight windows. |
| **Fall / Comfort Food** | Sep-Nov | Jul-Sep | 1, 3, 5 | Comfort food, crockpot meals, soup season, one-pot meals. Align with seasonal ingredient preferences. |
| **Thanksgiving** | Nov | Sep-Oct | 3 | Massive Pinterest volume but lower relevance for weekly planning. Minimal investment — maybe one "Post-Thanksgiving Meal Plan" piece. |
| **Holiday Season** | Dec | Oct-Nov | 1, 3 | "Survive the holidays with a plan." Holiday meal planning, entertaining without stress. |

### 11.2 Seasonal Content Rules

1. **Publish seasonal content 60-90 days before peak search.** The weekly content plan generator adds seasonal pins starting at the publish window.
2. **Seasonal content is additive, not replacement.** The pillar mix stays the same; seasonal content is layered on top by adjusting the topic selection within pillars.
3. **Back-to-school is the single most important seasonal moment for Slated.** Budget extra content production (6-8 additional pins) for the June-July publish window.
4. **Existing seasonal pins resurface automatically.** Pinterest's algorithm re-distributes seasonal content annually. A "back to school meal plan" pin from 2026 should see renewed distribution in July-August 2027 with no additional effort.

---

## 12. Weekly Content Plan Framework

This section defines the template the AI uses to generate each week's content plan. The weekly plan generator receives this framework plus performance data, seasonal calendar, and content log.

### 12.1 Weekly Plan Output Format — Blog-First Workflow

The weekly content plan is structured blog-first: blog posts are the primary planning unit, and pins are derived from them. This matches both the logical content creation sequence (you need a URL before you can create a pin) and the automation pipeline's workflow.

**Step 1: Define new blog posts for the week (~8-10 posts)**

Each blog post entry includes:

| Field | Description |
|---|---|
| `post_id` | Unique identifier (e.g., `W12-P01`) |
| `pillar` | Which of the 5 pillars (1-5) |
| `content_type` | weekly-plan, recipe, guide, or listicle |
| `topic` | Specific blog post topic (e.g., "Spring Weeknight Meal Plan — 5 Easy Dinners Under 30 Minutes") |
| `primary_keyword` | The keyword phrase the blog post targets |
| `secondary_keywords` | 2-3 additional keywords woven into the post |
| `schema_type` | Recipe, Article, or Article + embedded Recipes |
| `cta_pillar_variant` | Which CTA copy variant to use (from Section 10.3) |
| `seasonal_hook` | Optional — seasonal angle if applicable |

**Step 2: Derive pins from blog posts (28 total pins/week)**

For each blog post (new and existing URLs), define the pins it generates:

| Field | Description |
|---|---|
| `pin_id` | Unique identifier (e.g., `W12-01`) |
| `source_post_id` | The `post_id` this pin is derived from (or `existing_url` for fresh treatments) |
| `pin_type` | primary, recipe-pull, or fresh-treatment |
| `pin_template` | recipe-pin, tip-pin, listicle-pin, problem-solution-pin, infographic-pin |
| `pin_topic` | The specific angle this pin takes from the blog post |
| `primary_keyword` | The keyword phrase to lead the pin title with (may differ from blog post keyword for recipe pulls) |
| `secondary_keywords` | 2-3 additional keywords for pin description |
| `target_board` | Which Pinterest board to save to first |
| `image_source_tier` | Tier 1 (stock), Tier 2 (AI), or Tier 3 (template-only) |
| `treatment_number` | 1 for new pins, 2-5 for fresh treatments of existing URLs |
| `funnel_layer` | Discovery, Consideration, or Conversion |
| `scheduled_date` | Which day of the week to post |
| `scheduled_slot` | morning, afternoon, or evening |

**How blog posts generate pins:**

| Blog Post Type | Pins Generated | Details |
|---|---|---|
| Weekly plan post | 5-6 pins | 1 plan-level pin (tip/listicle template) + 4-5 recipe pull pins (recipe template, each targeting a different recipe keyword) |
| Standalone recipe post | 1-2 pins | 1 primary recipe pin + optional angle variant |
| Guide post | 1-2 pins | 1 primary tip/infographic pin + optional listicle treatment |
| Listicle post | 1-2 pins | 1 primary listicle pin + optional recipe pull if listicle contains recipes |

Remaining pins (~16-20 of the 28 weekly total) are fresh treatments of existing blog post URLs — new images and keyword angles for posts already in the library.

### 12.2 Planning Constraints

The weekly content plan generator must respect these constraints:

1. **Keyword-demand-driven topic selection.** Blog post topics are selected based on Pinterest keyword demand and gaps in existing content coverage — not editorially. The planning logic is: identify high-value keywords with no existing coverage or strong performance data → design blog posts to serve those keywords → derive pins. Exception: weekly plan posts (Pillar 1) are planned as cohesive meal plans first, with recipe pulls targeting keywords secondarily.
2. **Pillar mix:** Follow the percentage ranges in the Pillar Mix Summary table (Section 3). Deviation of +/-1 pin from target range is acceptable.
3. **No topic repetition within 4 weeks.** The content log tracks all previous topics. Do not generate a pin for "Chicken Stir Fry" if a chicken stir fry pin was created in the last 28 days.
4. **Fresh pin URL limits:** No URL gets more than 2 fresh pin treatments in a single week (excludes Treatment 1 recipe pulls from plan posts, which are distinct images). Maximum 5 total treatments per URL in 60 days.
5. **Board distribution:** No board receives more than 5 pins in a single week (to avoid looking spammy on any one board).
6. **Template variety:** No more than 3 consecutive pins using the same pin template.
7. **Scheduling distribution:** Spread pins evenly across Mon-Sun. Each day gets exactly 4 pins (1 per time slot, plus 1 extra in the evening slot or distributed).
8. **Seasonal content injection:** During seasonal windows (per Section 11), add 2-4 seasonal-themed concepts by adjusting topic selection within existing pillar allocations.
9. **Performance-informed adjustments:** The weekly analysis provides pillar-level and keyword-level performance data. The content plan should:
   - Increase fresh pin treatments for top-performing URLs
   - Lean into keywords showing strong save rates
   - Reduce production in content types showing consistently low engagement
   - Test new keyword variations when existing keywords plateau

### 12.3 Content Plan Generation Prompt Context

When generating the weekly content plan, the AI receives:

| Input | Source |
|---|---|
| This strategy document | `strategy/current-strategy.md` |
| Last week's performance analysis | `analysis/weekly/YYYY-wNN-review.md` |
| Seasonal calendar (current window) | Derived from Section 11 of this document |
| Full keyword performance data | `data/performance.db` (aggregated by keyword) |
| Content log (all previous content) | `data/content-log.json` |
| Board-level performance | Aggregated from pin-level data |
| Brand voice guidelines | `strategy/brand-voice.md` (derived from Section 6 of this document) |

---

## 13. Measurement & Optimization Framework

### 13.1 Primary Metrics (What Drives Decisions)

| Metric | What It Measures | Why It Matters | Target (after Month 3) |
|---|---|---|---|
| **Save rate** (saves / impressions) | Content quality — is this worth returning to? | Saves are the #1 algorithm signal. High save rate = more distribution = compounding growth. | >2% (hypothesis — adjust based on observed benchmarks) |
| **Outbound click rate** (outbound clicks / impressions) | Conversion effectiveness — does this drive traffic? | Outbound clicks drive blog visits which drive CTAs which drive app installs. This is the revenue path. | >0.5% |
| **Per-pillar save rate** | Which content pillars resonate most | Informs pillar mix adjustments at monthly review | Track and compare across pillars |
| **Per-keyword save rate** | Which keywords drive the best content | Informs keyword strategy adjustments | Track and compare across keywords |

### 13.2 Secondary Metrics (Context and Diagnostics)

| Metric | Purpose |
|---|---|
| Impressions (per pin, per board, per pillar) | Reach/distribution signal. Low impressions = classification problem or weak keyword optimization. |
| Pin clicks | Interest signal (user expanded the pin). Useful for image quality assessment. |
| Follower growth | Nearly irrelevant to distribution on Pinterest — track but don't optimize for. |
| Domain quality trend | Inferred from new pin initial distribution rates improving over time. |
| Content age vs. performance | Measures the compounding effect — are older pins still generating engagement? |
| Image source performance | Stock vs. AI vs. template-only — which produces higher save rates? |
| Plan-level vs. recipe-level pin performance | Key strategic signal: does the differentiated content outperform the commodity content? |

### 13.3 Metrics to Ignore

| Metric | Why |
|---|---|
| Impressions in isolation | Easy to accumulate, doesn't indicate value. A pin can get 100K impressions and zero clicks. |
| Follower count | Nearly irrelevant to Pinterest distribution. Do not chase followers. |
| Monthly views (profile metric) | Can be misleadingly large. Focus on saves and outbound clicks. |
| Pin clicks in isolation | Includes taps to expand — not as meaningful as outbound clicks. |

### 13.4 Optimization Cadence

| Timeframe | Action | Who |
|---|---|---|
| **Weekly** | Performance analysis generates pillar/keyword/content type rankings. Next week's content plan adjusts tactically (more of what works, less of what doesn't). | AI-generated, human-reviewed |
| **Monthly** | Deep analysis of 30-day trends. Structural recommendations: pillar mix changes, keyword strategy shifts, board architecture updates, template effectiveness. Updates to this strategy document if approved. | AI-generated (Opus), human decides |
| **Quarterly** | Evaluate whether Pillar 4 (Meal Kit) and Pillar 5 (Dietary) are pulling their weight relative to Pillars 1-3. Consider adding/retiring pillars. Assess whether video pins should be introduced (v2). | Human decision |

---

## 14. Launch Phase Plan (Month 1-3)

Pinterest takes 3-6 months to build meaningful traction. The first 90 days are about building the foundation for compounding growth.

### 14.1 Month 1: Library Foundation (Weeks 1-4)

**Goal:** Build the minimum viable content library. Establish posting consistency. Get the algorithm testing and classifying Slated's content.

**Blog posts produced:** ~35-40 total
- 8 weekly plan posts (2/week × 4 weeks, each containing 5 recipes = 40 embedded recipes)
- 12-16 standalone recipe posts (Pillar 3)
- 4-6 family-friendly recipe posts (Pillar 2)
- 4-6 guide posts (Pillar 2 family strategies, Pillar 4 meal kit content)
- 4-6 dietary/appliance recipe posts (Pillar 5)
- 2-4 listicle posts (cross-pillar)

**Pins produced:** ~112 (28/week × 4 weeks)
- Week 1-2: Heavily weighted toward Treatment 1 pins (new blog posts). Goal: populate all 10 boards with at least 8-10 pins each.
- Week 3-4: Begin fresh pin treatments (Treatment 2) for Week 1-2's strongest performers.

**Board setup:**
- All 10 boards created with keyword-rich names and descriptions (per Section 4)
- Board sections created
- Boards ordered by priority on profile (Weekly Meal Plans and Family Dinner Ideas at top)

**Technical prerequisites (before content starts posting):**
- Pinterest Business account created and claimed
- goslated.com domain claimed and verified on Pinterest
- Rich Pins validated (Recipe schema → Rich Pin validator tool)
- Blog infrastructure live on goslated.com (MDX support, weekly-plan template, recipe template, guide template, CTA component)

**Expectations:** Minimal traffic. The algorithm is testing and classifying content. Save rates may be low initially. This is normal.

### 14.2 Month 2: Optimization Begins (Weeks 5-8)

**Goal:** First performance data is available. Begin optimization loop. Start building domain quality.

**Content production:** 28 pins/week continues. Fresh pin ratio increases as the blog post library grows (~50% new content, ~50% fresh treatments).

**Optimization actions:**
- First weekly analyses identify top/bottom performing pins, pillars, keywords
- Content plan adjusts: more content in high-performing areas, test variations in low-performing areas
- Keyword refinement: add keywords showing in Pinterest autocomplete that we missed, deprioritize keywords with consistently low impressions
- Image source evaluation: compare save rates across stock vs. AI vs. template
- Key question to answer: Are plan-level pins (Pillar 1) outperforming standalone recipes (Pillar 3) on save rate?

**Expectations:** Early pins from Month 1 begin gaining traction. Some may hit save rate benchmarks. Others will underperform — this is data, not failure. Domain quality is building but still weak.

### 14.3 Month 3: Traction Signals (Weeks 9-12)

**Goal:** First clear traction signals. Multiple pins driving consistent saves and clicks. Content library is now 150-200+ pins providing broad search coverage.

**Content production:** 28 pins/week. Fresh pin ratio increases further (~35% new, ~65% fresh treatments) as the best-performing URLs get additional visual treatments.

**First monthly strategy review:**
- Full 30-day analysis (Opus)
- Pillar performance ranking — does the planned pillar mix match reality?
- Keyword strategy assessment — any surprises in what's working?
- Board architecture review — any boards consistently underperforming?
- Template effectiveness — which pin templates drive the most saves?
- Plan-level vs. recipe-level performance comparison
- First strategy document updates if warranted

**Expectations:** Some pins are now driving steady traffic to goslated.com/blog. Outbound click rates are measurable. First Pinterest-attributed app installs may appear (via UTM tracking), but this is early. Real conversion volume is months away.

### 14.4 Success Criteria by End of Month 3

| Metric | Target | Purpose |
|---|---|---|
| Total pins in library | 300+ | Sufficient search coverage for primary keyword clusters |
| Blog posts live | 80-100 | Content depth across all pillars |
| Average save rate (top 20% of pins) | >2% | Signal that algorithm is distributing content to receptive audiences |
| Outbound clicks/week (account total) | >100 | Measurable traffic to goslated.com |
| Boards with 20+ pins | All 10 | Minimum board density for topical authority signals |
| Posting consistency | 28/28 days | Zero missed days |
| Pipeline reliability | >90% success rate | System produces and posts content without manual intervention |

---

## 15. What This Strategy Explicitly Defers

| Topic | Why Deferred | When to Revisit |
|---|---|---|
| **Paid Pinterest advertising** | Organic-first strategy. Build the content library and domain quality before amplifying with paid. Paid ads benefit from strong organic signals (quality scores are shared). | Month 4-6, once organic traction is established |
| **Video pins** | Significant production complexity. Static image pins are the proven workhorse for search-based discovery. Pinterest isn't penalizing accounts that don't use video. | Month 3 monthly review — evaluate if video adds meaningful value |
| **Idea Pins / Carousels** | API support uncertain for automation. Standard image pins are the scalable format. | Revisit when Pinterest API adds reliable support |
| **Influencer/creator partnerships** | Premature at launch. Build Slated's own content library first. | Month 6+, if organic traction validates the channel |
| **International targeting** | US-first. Pinterest's international audience composition differs. | After US organic strategy proves out |

---

## Appendix A: Content Examples Reference

Full Pinterest post examples (one per pillar) showing blog post structure, pin copy, fresh pin treatments, and CTA implementation are maintained in a separate document: **`pinterest-content-examples.md`**

These examples demonstrate:
- How a single blog post generates multiple pins (especially weekly plan posts)
- How Dinner Draft threads through every pillar's CTAs
- The blog-first workflow: blog post content is written first, pins are derived from it
- Voice and copy standards for each pin component (title, description, alt text, text overlay)

---

## Appendix B: Keyword Quick-Reference (JSON-Ready)

This appendix provides the keyword data in a structured format suitable for `strategy/keyword-lists.json` in the pipeline repository.

```json
{
  "pillars": {
    "1_your_whole_week_planned": {
      "primary": [
        "weekly meal plan",
        "meal planning",
        "weekly dinner plan",
        "family meal planning",
        "meal plan for the week",
        "easy dinner ideas",
        "easy weeknight dinners",
        "30 minute meals"
      ],
      "secondary": [
        "meal planning for beginners",
        "what to cook for dinner",
        "dinner ideas for family",
        "quick weeknight dinners",
        "simple dinner recipes",
        "one pot meals",
        "busy mom weekly meal plan",
        "meal prep for busy families",
        "meal planning tips",
        "meal planning template"
      ]
    },
    "2_everyone_eats_nobody_argues": {
      "primary": [
        "dinner ideas for picky eaters",
        "kid friendly dinners",
        "family friendly meals",
        "meals for picky families",
        "easy dinners kids will eat"
      ],
      "secondary": [
        "picky eater meal ideas",
        "hidden veggie recipes",
        "toddler dinner ideas",
        "vegetarian family meals",
        "kid friendly healthy meals",
        "food for fussy eaters"
      ]
    },
    "3_dinner_decided": {
      "primary": [
        "what to cook for dinner",
        "easy dinner ideas",
        "dinner ideas for family",
        "easy weeknight dinners",
        "quick weeknight dinners",
        "30 minute meals",
        "dinner ideas",
        "simple dinner recipes"
      ],
      "secondary": [
        "weeknight dinner ideas",
        "last minute dinner ideas",
        "one pot meals",
        "one pan dinners",
        "15 minute meals",
        "what to make for dinner",
        "easy family dinner recipes",
        "quick family meals",
        "what should I make for dinner"
      ]
    },
    "4_smarter_than_meal_kit": {
      "primary": [
        "hellofresh alternative",
        "better than hello fresh",
        "meal kit alternative"
      ],
      "secondary": [
        "meal kit comparison",
        "tired of hello fresh",
        "tired of meal kits",
        "hello fresh vs home cooking"
      ]
    },
    "5_your_kitchen_your_rules": {
      "primary": [
        "gluten free dinner ideas",
        "high protein dinner recipes",
        "air fryer dinner recipes",
        "instant pot dinner ideas",
        "slow cooker family meals"
      ],
      "secondary": [
        "keto meal plan",
        "low carb meal plan",
        "dairy free dinner ideas",
        "anti-inflammatory recipes",
        "meal plan with grocery list",
        "grocery list for the week",
        "pantry meal ideas",
        "vegetarian family meals"
      ]
    }
  },
  "negative_keywords": [
    "cheap meals",
    "budget meals",
    "save money on food",
    "frugal meal planning",
    "gourmet recipes",
    "authentic recipes",
    "from scratch",
    "restaurant quality",
    "weight loss meal plan",
    "diet meal plan",
    "calorie counting",
    "baby food",
    "baby led weaning"
  ]
}
```

---

## Appendix C: Board Architecture (JSON-Ready)

Structured format suitable for `strategy/board-structure.json` in the pipeline repository.

```json
{
  "boards": [
    {
      "name": "Weekly Meal Plans & Meal Planning Tips",
      "pillar": 1,
      "description": "Weekly meal plans, meal planning guides, and tips for planning dinner for the whole week. Stop wondering what to cook — plan your whole week in minutes.",
      "sections": ["Weekly Meal Plans", "Meal Planning for Beginners", "Meal Prep Ideas"],
      "priority": 1
    },
    {
      "name": "Quick Weeknight Dinner Recipes",
      "pillar": [1, 3],
      "description": "Easy weeknight dinner recipes ready in 30 minutes or less. Simple family dinners for busy nights when you need dinner on the table fast.",
      "sections": ["30 Minute Dinners", "One-Pan Meals", "15 Minute Meals"],
      "priority": 2
    },
    {
      "name": "Easy Dinner Ideas for Families",
      "pillar": [1, 3],
      "description": "Simple dinner ideas the whole family will love. Easy recipes for family dinners on busy weeknights — no complicated ingredients or techniques.",
      "sections": ["Chicken Dinners", "Pasta Dinners", "Comfort Food"],
      "priority": 3
    },
    {
      "name": "Family Dinner Ideas Even Picky Eaters Love",
      "pillar": 2,
      "description": "Kid-approved dinner recipes and family meal ideas for households with picky eaters. Meals everyone will actually eat — no more dinnertime battles.",
      "sections": ["Kid-Friendly Dinners", "Hidden Veggie Recipes", "Feeding Picky Families"],
      "priority": 4
    },
    {
      "name": "Family Meal Planning Strategies",
      "pillar": 2,
      "description": "How to get your family on board with dinner. Strategies for meal planning with picky eaters, dietary differences, and busy schedules — so everyone agrees before you cook.",
      "sections": ["Getting Family Buy-In", "Picky Eater Strategies", "Weeknight Survival"],
      "priority": 5
    },
    {
      "name": "Better Than a Meal Kit",
      "pillar": 4,
      "description": "Meal kit alternatives and home cooking strategies for families tired of subscription boxes. Better food, more flexibility, less cost than Hello Fresh and Blue Apron.",
      "sections": ["Meal Kit Alternatives", "Why We Quit Meal Kits"],
      "priority": 6
    },
    {
      "name": "Healthy Family Dinner Recipes",
      "pillar": 5,
      "description": "Healthy dinner recipes for families — high protein, anti-inflammatory, and nutritious meals everyone will eat. Healthy doesn't have to mean complicated.",
      "sections": ["High Protein Dinners", "Anti-Inflammatory Recipes", "Healthy Kid-Friendly Meals"],
      "priority": 7
    },
    {
      "name": "Gluten-Free Dinner Ideas",
      "pillar": 5,
      "description": "Gluten-free dinner recipes and weekly meal plan ideas. Easy gluten-free meals for families managing celiac, intolerance, or gluten-free lifestyles.",
      "sections": ["Quick Gluten-Free Meals", "Gluten-Free Meal Plans"],
      "priority": 8
    },
    {
      "name": "Air Fryer & Instant Pot Dinner Recipes",
      "pillar": 5,
      "description": "Air fryer dinner recipes and Instant Pot family meals. Quick, easy appliance-based recipes for weeknight dinners.",
      "sections": ["Air Fryer Dinners", "Instant Pot Meals", "Slow Cooker Family Dinners"],
      "priority": 9
    },
    {
      "name": "Meal Planning & Grocery Tips",
      "pillar": [1, 5],
      "description": "Meal planning tips, grocery list organization, and strategies to get dinner on the table with less stress. From plan to plate to groceries — the whole system.",
      "sections": ["Grocery List Tips", "Pantry Meal Ideas", "Meal Plan to Grocery List"],
      "priority": 10
    }
  ]
}
```

---

## Document Control

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-02-19 | Initial strategy. |
| 2.0 | 2026-02-19 | Major restructure: Pillars reordered to lead with plan-level content (Pillar 1) and family dynamics (Pillar 2). Standalone recipes reduced from 35-40% to 18-21%. Dinner Draft elevated to strategic theme across all pillars. Blog post production model added. Full post examples added as Appendix A. Board architecture updated (10 boards). |
| 2.1 | 2026-02-19 | Section 12 updated to blog-first workflow: weekly plan output now defines blog posts first, then derives pins from them. Pipeline flow diagram updated. Examples moved to separate document (`pinterest-content-examples.md`). Blog Post Production Model and Fresh Pin Mix (Section 8.3) reconciled with phased tapering table (Month 1-2 launch → Month 3-4 optimization → Month 5+ steady state). Fixed posting cadence inconsistency (3x → 4x/day). |

**Next review:** After first monthly analysis (approximately end of Month 1 of active posting).

**Update process:** Monthly review generates strategy update recommendations. Approved changes are committed to this document. The weekly content plan generator always reads the latest version.
