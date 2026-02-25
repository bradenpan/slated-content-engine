# Prompts Report — Pinterest Automation Pipeline

**Date:** 2026-02-20
**Author:** Claude (Opus 4.6)
**Status:** All 10 prompt templates written and placed in `prompts/`

---

## 1. What Was Written

### 1.1 weekly_plan.md — Weekly Content Plan Generator

**Design rationale:** This is the most complex prompt and the most important. It must encode the entire planning logic: pillar allocation, content funnel distribution, blog-first workflow, constraint validation, and seasonal awareness. Rather than embedding all the raw strategy text, the prompt is structured as a step-by-step planning process (Analyze Inputs, Calculate Allocation, Plan Blog Posts, Derive Pins, Validate Constraints) that guides the model through the correct reasoning sequence.

**Key strategy elements encoded:**
- Pillar mix targets (P1: 32-36%, P2: 25-29%, P3: 18-21%, P4: 7-10%, P5: 14-18%)
- Content funnel distribution (Discovery 55-65%, Consideration 20-30%, Conversion 10-15%)
- Blog-first workflow (define blog posts first, derive pins)
- All Section 12.2 constraints (no topic repetition within 4 weeks, max 5 pins per board, max 2 fresh treatments per URL per week, template variety, scheduling distribution)
- Full negative keyword list with explanations
- Board architecture with pillar mappings
- Image source tier assignment logic
- CTA variant assignment rules
- Seasonal content injection
- 28 pins total with exact daily scheduling (4 per day, 1+1+2 slot distribution)

**Variables:** `{{strategy_summary}}`, `{{last_week_analysis}}`, `{{content_memory_summary}}`, `{{seasonal_window}}`, `{{keyword_performance}}`, `{{current_date}}`, `{{week_number}}`

**Few-shot examples:** 5 examples covering blog post entries (weekly plan and standalone recipe), pin entries (plan-level, recipe-pull, fresh treatment). Includes exact JSON output format with all fields.

### 1.2 pin_copy.md — Pin Copy Generator

**Design rationale:** Structured as a comprehensive copy guide rather than a simple "generate copy" instruction. Includes the complete brand voice table, every Pinterest SEO rule from the strategy, character limits for every component, and both good and bad few-shot examples. The bad examples are critical — they teach the model what to avoid (keyword stuffing, engagement bait, short descriptions).

**Key strategy elements encoded:**
- Brand voice (all 6 principles with do/don't examples)
- Pinterest SEO rules (keywords early, natural language, no hashtags, no CTAs)
- Character limits: title 100 chars, description 250-500 chars, alt text 500 chars, overlay 6-8 words
- No brand mentions in pin copy (Slated only in blog CTAs)
- Excluded personas (Budget Optimizer, Perfectionist)

**Variables:** `{{pin_specs}}`, `{{blog_post_content}}`, `{{pillar}}`, `{{funnel_layer}}`

**Few-shot examples:** 3 good examples (recipe pin, plan-level pin, problem-solution pin) + 3 bad examples (keyword stuffing, engagement bait, wasted space). Each example includes analysis of why it works or fails.

### 1.3 blog_post_recipe.md — Recipe Blog Post Generator

**Design rationale:** Provides the exact MDX frontmatter schema (including all Schema.org Recipe fields), the body structure template, and a complete 650-word few-shot example that demonstrates the correct tone, length, and structure. Emphasizes Slated's recipe differentiators: short intros, realistic times, practical substitutions, family-tested framing.

**Key strategy elements encoded:**
- Complete frontmatter schema with all Recipe schema fields (prepTime, cookTime, totalTime, recipeYield, recipeIngredient, recipeInstructions)
- 600-800 word target
- Short intro rule (no 800-word preambles)
- "This could be your Tuesday" positioning
- Pillar-specific CTA placement (mid-post + end-of-post)
- Dinner Draft angle in CTAs
- Excluded language list

**Variables:** `{{topic}}`, `{{primary_keyword}}`, `{{secondary_keywords}}`, `{{pillar}}`, `{{mid_post_cta}}`, `{{end_post_cta}}`, `{{current_date}}`

**Few-shot example:** Full 25-Minute Chicken Stir Fry recipe post from the blog template examples, demonstrating exact frontmatter format and body structure.

### 1.4 blog_post_weekly_plan.md — Weekly Plan Blog Post Generator

**Design rationale:** This is the highest-value post type. The prompt is heavily prescriptive about plan cohesion (protein variety, cooking method variety, time variety, cuisine variety, weekday realism) because bad plans would undermine the core strategic differentiator. Includes an abbreviated but substantive few-shot example showing the overview table, recipe format, mid-post CTA placement, and grocery list structure.

**Key strategy elements encoded:**
- 5 embedded recipes with individual Schema.org Recipe markup in frontmatter
- 1,200-1,800 word target
- Plan cohesion rules (3+ proteins, method variety, time variety, cuisine variety)
- Combined grocery list organized by store section
- Plan-level framing ("your whole week, planned")
- Dinner Draft CTA angle ("This plan took us 20 minutes to build. Slated does it in 2.")
- Weekly plan posts generate 5-6 pins each

**Variables:** `{{plan_theme}}`, `{{primary_keyword}}`, `{{secondary_keywords}}`, `{{recipes}}`, `{{pillar}}`, `{{mid_post_cta}}`, `{{end_post_cta}}`, `{{current_date}}`

### 1.5 blog_post_guide.md — Guide Blog Post Generator

**Design rationale:** Guides serve different strategic purposes across pillars (family dynamics for P2, meal kit alternatives for P4, constraint-combination for P5). The prompt includes pillar-specific framing guidance so the same template produces contextually appropriate content regardless of which pillar it serves. Emphasizes systems thinking over one-off tips.

**Key strategy elements encoded:**
- 800-1,200 word target, 3-5 structured sections
- Pillar-specific framing for P1, P2, P4, P5
- Dinner Draft integration varies by pillar
- Empathetic tone (acknowledge the struggle before presenting the solution)
- Actionable, systems-level content
- Article schema

**Variables:** `{{topic}}`, `{{primary_keyword}}`, `{{secondary_keywords}}`, `{{pillar}}`, `{{mid_post_cta}}`, `{{end_post_cta}}`, `{{current_date}}`

### 1.6 blog_post_listicle.md — Listicle Blog Post Generator

**Design rationale:** Listicles operate in two modes (recipe listicles with Schema.org vs. non-recipe listicles), controlled by the `include_recipes` boolean. The prompt provides distinct body structures for each mode and makes the Schema.org recipe array conditional in frontmatter. Emphasizes that numbers in titles drive saves on Pinterest.

**Key strategy elements encoded:**
- 800-1,200 word target, 5-10 entries (7 optimal)
- Conditional recipes array in frontmatter for Schema.org
- Number-in-title rule
- Substantive entries (not one-liners)
- Pillar-specific listicle framing
- Wrap-up section ties back to meal planning

**Variables:** `{{topic}}`, `{{primary_keyword}}`, `{{secondary_keywords}}`, `{{pillar}}`, `{{include_recipes}}`, `{{mid_post_cta}}`, `{{end_post_cta}}`, `{{current_date}}`

### 1.7 image_prompt.md — AI Image Generation Prompt Generator

**Design rationale:** Structured around consistent style anchors that ensure visual coherence across all AI-generated images. The most important section is the Critical Avoidance List — AI food photography has known failure modes (hands, utensils, text) that must be explicitly excluded. Includes composition guidance per pin template type and a prompt construction template with example output.

**Key strategy elements encoded:**
- Style anchors: bright/natural lighting, overhead/flat-lay preferred, light surfaces, warm color temperature
- Avoidance list: hands, utensils in use, faces, text, watermarks, unnatural textures
- Composition by pin template (recipe, tip, listicle, problem-solution)
- 1024x1536 portrait dimensions (resized to 1000x1500)
- Bottom 30-40% kept simple for text overlay
- Negative prompt guidance for common AI artifacts

**Variables:** `{{pin_topic}}`, `{{pin_template}}`, `{{content_type}}`, `{{pillar}}`

### 1.8 image_search.md — Stock Photo Search Query Generator

**Design rationale:** Stock photo search is fundamentally different from web search (shorter, more visual, descriptive). The prompt teaches this distinction explicitly and provides a broad-to-specific query strategy. Includes API-specific guidance for Unsplash vs. Pexels, orientation preferences, and examples for different content types.

**Key strategy elements encoded:**
- 3-5 queries per pin, broad to specific
- Unsplash vs. Pexels API differences
- Portrait orientation always (2:3 ratio)
- Warm color mood always
- Composition preferences by content type
- Subject description for quality evaluation

**Variables:** `{{pin_topic}}`, `{{content_type}}`, `{{primary_keyword}}`

### 1.9 weekly_analysis.md — Weekly Performance Analysis

**Design rationale:** Structured as a 6-step analysis process (calculate metrics, identify performers, aggregate by dimension, compare to targets, identify trends, generate recommendations) that forces the model to do analysis before drawing conclusions. Includes all the target metrics from the strategy and explicit guidance on handling small sample sizes in early months.

**Key strategy elements encoded:**
- Target metrics: save rate >2%, outbound click rate >0.5%
- Pillar mix targets for comparison
- Content funnel distribution targets
- Dimension analysis: pillar, content type, board, funnel layer, image source, pin type
- Plan-level vs. recipe-level comparison (the key strategic question)
- Sample size caveats for Month 1-2
- Specific, data-backed recommendations (not vague suggestions)

**Variables:** `{{this_week_data}}`, `{{last_week_analysis}}`, `{{content_plan_vs_actual}}`, `{{per_pillar_metrics}}`, `{{per_keyword_metrics}}`, `{{per_board_metrics}}`, `{{per_funnel_layer_metrics}}`, `{{account_trends}}`

### 1.10 monthly_review.md — Monthly Strategy Review (Opus)

**Design rationale:** This is the only prompt that runs on Opus and explicitly calls for deeper reasoning. It uses a 4-level analysis framework (What Happened, Why, What It Means, What To Do) that pushes beyond surface metrics into strategic implications. Includes the quarterly pillar architecture question, content compounding assessment, and a format for specific strategy update recommendations with success criteria.

**Key strategy elements encoded:**
- All target metrics and pillar targets
- The plan-level vs. recipe-level strategic question (dedicated deep-dive section)
- Content compounding thesis (are older pins still generating engagement?)
- Quarterly question on pillar additions/retirements
- Board architecture assessment
- Image source ROI analysis
- Seasonal outlook (60-90 day forward-looking)
- Concrete recommendation format: change + data + expected impact + success criteria

**Variables:** `{{monthly_data}}`, `{{all_weekly_analyses}}`, `{{current_strategy_summary}}`, `{{pillar_performance}}`, `{{keyword_performance}}`, `{{board_performance}}`, `{{content_type_performance}}`, `{{image_source_performance}}`, `{{seasonal_context}}`

---

## 2. Key Strategy Elements Encoded Across Prompts

| Strategy Element | Encoded In |
|-----------------|-----------|
| Pillar mix targets (P1: 32-36%, P2: 25-29%, etc.) | weekly_plan, weekly_analysis, monthly_review |
| Content funnel distribution (Discovery/Consideration/Conversion) | weekly_plan, weekly_analysis, monthly_review |
| Blog-first workflow | weekly_plan, all blog_post_* prompts |
| Brand voice (6 principles) | pin_copy, all blog_post_* prompts |
| Pinterest SEO rules (keywords early, no hashtags, no CTAs) | pin_copy |
| Negative keywords / excluded personas | weekly_plan, pin_copy, all blog_post_* prompts |
| Dinner Draft theme (in CTAs, not pins) | weekly_plan, all blog_post_* prompts |
| Board architecture (10 boards, max 5/board/week) | weekly_plan, weekly_analysis, monthly_review |
| Fresh pin strategy (max 2 treatments/week, max 5/60 days) | weekly_plan |
| Seasonal calendar (60-90 day lead times) | weekly_plan, monthly_review |
| Image source tiers (stock > AI > template) | weekly_plan, image_prompt, image_search |
| Schema.org Recipe markup (Rich Pins) | blog_post_recipe, blog_post_weekly_plan, blog_post_listicle |
| CTA pillar variants | weekly_plan, all blog_post_* prompts |
| Plan-level vs. recipe-level strategic question | weekly_analysis, monthly_review |
| Posting schedule (4/day, 1+1+2 across 3 windows) | weekly_plan |
| Content compounding thesis | monthly_review |

---

## 3. Variable Placeholders Summary

### weekly_plan.md
| Variable | Source | Notes |
|----------|--------|-------|
| `{{strategy_summary}}` | `strategy/current-strategy.md` (condensed) | Full strategy or a condensed version |
| `{{last_week_analysis}}` | `analysis/weekly/YYYY-wNN-review.md` | Most recent weekly analysis |
| `{{content_memory_summary}}` | `data/content-memory-summary.md` | Python-generated, not LLM |
| `{{seasonal_window}}` | `strategy/seasonal-calendar.json` | Current active windows |
| `{{keyword_performance}}` | `data/performance.db` aggregated | Per-keyword metrics |
| `{{current_date}}` | System date | YYYY-MM-DD |
| `{{week_number}}` | Calculated from date | Integer |

### pin_copy.md
| Variable | Source |
|----------|--------|
| `{{pin_specs}}` | JSON array of pin specifications from the weekly plan |
| `{{blog_post_content}}` | Excerpt or summary of the parent blog post |
| `{{pillar}}` | Integer 1-5 |
| `{{funnel_layer}}` | "discovery" / "consideration" / "conversion" |

### blog_post_recipe.md
| Variable | Source |
|----------|--------|
| `{{topic}}` | From weekly plan blog post entry |
| `{{primary_keyword}}` | From weekly plan |
| `{{secondary_keywords}}` | From weekly plan |
| `{{pillar}}` | Integer 1-5 |
| `{{mid_post_cta}}` | From `strategy/cta-variants.json` |
| `{{end_post_cta}}` | From `strategy/cta-variants.json` |
| `{{current_date}}` | System date |

### blog_post_weekly_plan.md
| Variable | Source |
|----------|--------|
| `{{plan_theme}}` | From weekly plan blog post entry |
| `{{primary_keyword}}` | From weekly plan |
| `{{secondary_keywords}}` | From weekly plan |
| `{{recipes}}` | List of 5 recipe concepts from weekly plan |
| `{{pillar}}` | Always 1 for weekly plans |
| `{{mid_post_cta}}` | From `strategy/cta-variants.json` (Pillar 1) |
| `{{end_post_cta}}` | From `strategy/cta-variants.json` (Pillar 1) |
| `{{current_date}}` | System date |

### blog_post_guide.md
| Variable | Source |
|----------|--------|
| `{{topic}}` | From weekly plan |
| `{{primary_keyword}}` | From weekly plan |
| `{{secondary_keywords}}` | From weekly plan |
| `{{pillar}}` | Integer 1-5 |
| `{{mid_post_cta}}` | From `strategy/cta-variants.json` |
| `{{end_post_cta}}` | From `strategy/cta-variants.json` |
| `{{current_date}}` | System date |

### blog_post_listicle.md
| Variable | Source |
|----------|--------|
| `{{topic}}` | From weekly plan |
| `{{primary_keyword}}` | From weekly plan |
| `{{secondary_keywords}}` | From weekly plan |
| `{{pillar}}` | Integer 1-5 |
| `{{include_recipes}}` | Boolean from weekly plan |
| `{{mid_post_cta}}` | From `strategy/cta-variants.json` |
| `{{end_post_cta}}` | From `strategy/cta-variants.json` |
| `{{current_date}}` | System date |

### image_prompt.md
| Variable | Source |
|----------|--------|
| `{{pin_topic}}` | From pin spec |
| `{{pin_template}}` | From pin spec |
| `{{content_type}}` | From pin spec |
| `{{pillar}}` | Integer 1-5 |

### image_search.md
| Variable | Source |
|----------|--------|
| `{{pin_topic}}` | From pin spec |
| `{{content_type}}` | From pin spec |
| `{{primary_keyword}}` | From pin spec |

### weekly_analysis.md
| Variable | Source |
|----------|--------|
| `{{this_week_data}}` | Pinterest Analytics API |
| `{{last_week_analysis}}` | Previous `analysis/weekly/*.md` |
| `{{content_plan_vs_actual}}` | Google Sheet comparison |
| `{{per_pillar_metrics}}` | Aggregated from pin data |
| `{{per_keyword_metrics}}` | Aggregated from pin data |
| `{{per_board_metrics}}` | Aggregated from pin data |
| `{{per_funnel_layer_metrics}}` | Aggregated from pin data |
| `{{account_trends}}` | Pinterest account analytics |

### monthly_review.md
| Variable | Source |
|----------|--------|
| `{{monthly_data}}` | 30 days of Pinterest analytics |
| `{{all_weekly_analyses}}` | All weekly `.md` files from month |
| `{{current_strategy_summary}}` | `strategy/current-strategy.md` (condensed) |
| `{{pillar_performance}}` | 30-day aggregate by pillar |
| `{{keyword_performance}}` | 30-day aggregate by keyword |
| `{{board_performance}}` | 30-day aggregate by board |
| `{{content_type_performance}}` | 30-day aggregate by content type |
| `{{image_source_performance}}` | 30-day aggregate by image source |
| `{{seasonal_context}}` | Current and upcoming seasonal windows |

---

## 4. Concerns About Prompt Length / Token Usage

### Token Estimates

| Prompt | Estimated Tokens | Concern Level |
|--------|-----------------|---------------|
| weekly_plan.md | ~3,500 | **Medium.** This is the longest prompt. When combined with `{{strategy_summary}}` (potentially 3,000+ tokens), `{{content_memory_summary}}` (up to 3,000 tokens), and `{{last_week_analysis}}` (1,000-2,000 tokens), the full input could reach 10,000-15,000 tokens. Well within Sonnet's context window, but output (the 28-pin plan) will also be substantial (~4,000-6,000 tokens). Total round-trip: ~15,000-20,000 tokens. **Cost: ~$0.05-0.08 per plan.** |
| blog_post_weekly_plan.md | ~2,500 | **Medium.** The output (1,200-1,800 word blog post with 5 recipes) is the largest single generation at ~3,000-4,000 output tokens. The few-shot example adds to input length. **Total per post: ~7,000-10,000 tokens. At 2 posts/week: $0.03-0.06.** |
| blog_post_recipe.md | ~2,200 | **Low.** Output is 600-800 words (~1,000-1,200 tokens). Efficient. |
| pin_copy.md | ~2,800 | **Low.** Batch processing (5-7 pins per call) amortizes the prompt across multiple outputs. |
| monthly_review.md | ~3,000 | **Low concern, higher cost.** Runs on Opus (1x/month). The `{{all_weekly_analyses}}` context could be substantial (4,000-8,000 tokens for 4-5 weekly analyses). But monthly frequency keeps total cost low (~$0.50-1.00 per review). |
| weekly_analysis.md | ~2,500 | **Low.** Runs weekly. Input data volume is the main variable. |
| image_prompt.md | ~2,000 | **Low.** Short output (one image prompt per call). |
| image_search.md | ~1,800 | **Low.** Short output. |
| blog_post_guide.md | ~1,500 | **Low.** |
| blog_post_listicle.md | ~1,800 | **Low.** |

### Estimated Weekly LLM Cost

| Component | Calls/Week | Est. Tokens/Call | Model | Weekly Cost |
|-----------|-----------|-----------------|-------|-------------|
| Weekly plan generation | 1 | 15,000-20,000 | Sonnet | $0.05-0.08 |
| Blog post generation (all types) | 8-10 | 5,000-10,000 each | Sonnet | $0.15-0.40 |
| Pin copy generation | 4-5 batches | 4,000-6,000 each | Sonnet | $0.06-0.12 |
| Image prompt generation | 10-15 | 3,000-4,000 each | Sonnet | $0.05-0.10 |
| Image search queries | 15-20 | 2,500-3,000 each | Sonnet | $0.04-0.08 |
| Weekly analysis | 1 | 8,000-12,000 | Sonnet | $0.03-0.05 |
| **Weekly total** | | | | **$0.38-0.83** |
| Monthly review | 1/month | 15,000-25,000 | Opus | $0.50-1.00 |
| **Monthly total** | | | | **$2.00-4.50** |

These estimates are well within the $6-12/month LLM budget from the automation plan.

### Potential Optimization

If prompt length becomes an issue (unlikely with current models):
1. **Condense the strategy summary.** The `{{strategy_summary}}` variable could be a shorter digest rather than the full document.
2. **Remove few-shot examples after calibration.** Once the model consistently produces correct output format, the examples can be trimmed to reduce tokens.
3. **Batch more aggressively.** Pin copy and image prompts can be batched at 7-10 per call instead of 5-7.

---

## 5. Recommendations for Prompt Tuning After First Week

### Week 1 Tuning Priorities

1. **Weekly plan validation.** The weekly_plan.md prompt is the hardest to get right. After the first generated plan, verify:
   - Does the pillar mix actually hit the targets? If the model consistently over- or under-allocates a pillar, add stronger enforcement language or a worked example for that pillar.
   - Does the scheduling constraint hold? (4 pins per day, distributed across slots.) If not, add a more explicit slot-assignment algorithm.
   - Does the model avoid repeated topics correctly? The content memory summary may need more explicit formatting for the model to parse it reliably.

2. **Recipe quality check.** The blog_post_recipe.md prompt must produce recipes that are:
   - Actually cookable (correct ingredient quantities, realistic times, logical instruction order)
   - Correctly formatted for Schema.org (every ingredient in the frontmatter array matches the body list)
   - Within word count (600-800 words)
   - Run the first 3-4 generated recipes through a manual "could I actually cook this?" review. If quantities are wrong or instructions are vague, add more explicit recipe-writing guidance.

3. **Pin copy length.** Verify descriptions are consistently 250-500 characters. Models sometimes default to shorter descriptions despite instructions. If this happens, add a more forceful minimum length requirement or a character count enforcement note.

4. **Image prompt effectiveness.** Generate 5-10 AI images from the image_prompt.md outputs and evaluate quality. Key questions:
   - Are the style anchors producing visual consistency?
   - Is the negative prompt actually preventing hands/text/artifacts?
   - Does the bottom-third-clear composition guidance work for text overlay?
   - If quality is inconsistent, add more specific negative prompt items or adjust the composition guidance.

5. **Blog post frontmatter parsing.** Verify that the generated MDX files parse correctly in the goslated.com blog infrastructure. The YAML frontmatter (especially the nested `recipes` array in weekly plan posts) must be syntactically valid. If the model produces malformed YAML, add more explicit formatting rules or a validation step in the Python script.

### Ongoing Tuning (Week 2-4)

6. **Tone calibration.** Read 10+ generated pin descriptions and blog post intros. Are they hitting the brand voice consistently? Look for:
   - Creeping saccharine ("You're going to LOVE this!!")
   - Creeping preachy ("You should be meal planning...")
   - Keyword stuffing in descriptions
   - If any pattern emerges, add a targeted "DO NOT" example to the relevant prompt.

7. **Content diversity.** After 2 weeks, review the generated topics. Is the model falling into a rut (always suggesting chicken, always doing the same vegetables, always the same recipe structures)? If so, add explicit variety requirements to weekly_plan.md ("no more than 2 chicken recipes per week," "include at least 1 vegetarian option per week").

8. **CTA consistency.** Verify that CTAs in blog posts are using the exact copy from cta-variants.json and not paraphrasing. If the model is drifting, add "Use the EXACT CTA copy provided. Do not paraphrase or modify it."

9. **Weekly analysis actionability.** After the first real weekly analysis runs, verify that the recommendations are specific enough to be fed back into the next weekly plan. If they are too vague, strengthen the "be specific" requirements in weekly_analysis.md.

10. **Batch size tuning.** If pin_copy.md produces lower quality at 7 pins per batch, reduce to 5. If quality holds at 7, consider increasing to 10 for efficiency.
