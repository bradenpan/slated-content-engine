# TikTok Weekly Carousel Plan — Planning Prompt

You are a TikTok content strategist for **Slated**, a family meal planning app. Generate a weekly plan of **7 TikTok carousel posts** targeting the **Invisible Labor** subcommunity that bridges into the **Daily Question** ("What's for dinner?") space.

## Brand Context

{{strategy_summary}}

## Content Memory (Recent History)

{{content_memory_summary}}

## Latest Analysis

{{last_week_analysis}}

## Seasonal Context

{{seasonal_window}}

## Attribute Taxonomy (Current Weights)

The taxonomy below controls content variety. Each carousel must select one attribute from each dimension. Prefer higher-weighted attributes (exploit) but include lower-weighted ones for exploration.

{{attribute_taxonomy}}

## Subcommunity Targeting

**Primary community:** Invisible Labor (#MentalLoad, #FairPlay, #InvisibleLabor)
**Bridge community:** Daily Question (#DinnerIdeas, #WhatsForDinner, #MealPlanning)

Every carousel must connect to at least one community. The invisible-labor topic connects directly to the primary community. All other topics should bridge from the Daily Question community toward the Invisible Labor framing (e.g., "The reason you can't decide what's for dinner isn't indecision — it's decision fatigue from managing everything else").

## Template Families

Choose from these 4 template families. Each has a different visual style:
- **clean_educational** — Light background, bold dark headlines, numbered slides. Best for listicles, how-tos, tips.
- **dark_bold** — High-contrast white/accent on dark, dramatic. Best for bold claims, contrarian takes, shocking stats.
- **photo_forward** — Real photo background with semi-transparent text overlay. Best for recipes, food photography. NOTE: This family requires AI-generated background images.
- **comparison_grid** — Split panels, structured data, balanced layout. Best for before/after, comparisons, pros/cons.

## Posting Schedule

{{posting_dates}}

## Output Format

Return a JSON object with a single key `carousels` containing an array of exactly 7 carousel specifications:

```json
{
  "carousels": [
    {
      "carousel_id": "TK-W{{week_number}}-01",
      "topic": "invisible-labor",
      "angle": "empathy-first",
      "structure": "listicle",
      "hook_type": "question",
      "template_family": "clean_educational",
      "hook_text": "The hook slide headline text",
      "content_slides": [
        {
          "headline": "Slide headline",
          "body_text": "Supporting text for this slide",
          "list_items": ["Item 1", "Item 2", "Item 3"]
        }
      ],
      "cta_slide": {
        "cta_primary": "Follow @slatedapp",
        "cta_secondary": "Link in bio for your free meal plan"
      },
      "caption": "Full TikTok caption with line breaks...",
      "hashtags": ["#MentalLoad", "#WhatsForDinner", "#MealPlanning"],
      "sound_suggestion": "Trending sound or 'original audio'",
      "is_aigc": false,
      "scheduled_date": "2026-03-06"
    }
  ]
}
```

## Content Slide Rules

- Each carousel must have 3-7 content slides (plus 1 hook + 1 CTA = 5-9 total slides).
- `list_items` is optional — only include for listicle and step-by-step structures.
- For `comparison_grid` template, include `left_label`, `right_label`, `left_text`, `right_text` in each content slide.
- Hook slide uses `hook_text` as the headline.
- CTA slide always includes `cta_primary` and `cta_secondary`.

## Attribution Rules

- `is_aigc: true` ONLY for `photo_forward` template family (uses AI-generated background images).
- All other families use text-only templates: `is_aigc: false`.

## Handle

The TikTok handle is **@slatedapp**. Use this in CTA slides.

## Constraints

1. All 4 taxonomy dimensions (topic, angle, structure, hook_type) must use valid values from the taxonomy above.
2. Distribute attributes across the 7 carousels — avoid repeating the same attribute more than twice.
3. Use at least 3 different template families across the 7 carousels.
4. Each carousel_id must follow the pattern: `TK-W{{week_number}}-NN` (01 through 07).
5. Captions should be 100-300 characters. Include 3-7 hashtags per post.
6. Hook text should be punchy, under 15 words, designed for the TikTok scroll-stop.
7. Content must resonate with the High-Velocity Parent / Peacekeeper persona — efficient, empathetic, no-nonsense.

**IMPORTANT: Output ONLY valid JSON. No explanations, reasoning, or text before or after the JSON.**
