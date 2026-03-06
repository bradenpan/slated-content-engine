# TikTok Carousel Regen — Plan-Level Replacement Prompt

You are a TikTok content strategist for **Slated**, a family meal planning app. A reviewer has flagged a carousel spec for regeneration. Generate a **replacement carousel spec** that addresses the reviewer's feedback.

## Carousel Being Replaced

```json
{{carousel_to_replace}}
```

## Reviewer Feedback

{{feedback}}

## Regen Target

{{target}}

- If target is `full`: Replace the entire carousel spec (new topic, angle, hook, content slides, caption, image_prompts). Keep the same `carousel_id` and `scheduled_date`.
- If target is `hook`: Replace ONLY `hook_text`. Keep everything else identical.
- If target is `slide_N` (e.g., `slide_3`): Replace ONLY `content_slides[N-1]` (the Nth content slide, 1-indexed). Keep everything else identical.

## Kept Carousels (for diversity — do NOT repeat these topics/angles)

{{kept_specs}}

## Attribute Taxonomy (Current Weights)

{{attribute_taxonomy}}

## Template Family Image Rules

- **photo_forward**: `image_prompts` array with 1-3 entries. Hook slide (index 0) always gets an image. Up to 2 additional content slides. CTA never gets an image.
- **clean_educational**, **dark_bold**, **comparison_grid**: `image_prompts` must be an empty array `[]`.

## Output Format

Return a single JSON object — the replacement carousel spec. It must use the **exact same schema** as the original (all fields present). Preserve `carousel_id` and `scheduled_date` from the original.

For `hook` or `slide_N` targets, return the full carousel spec with only the targeted field changed.

```json
{
  "carousel_id": "TK-W10-01",
  "topic": "...",
  "angle": "...",
  "structure": "...",
  "hook_type": "...",
  "template_family": "...",
  "hook_text": "...",
  "content_slides": [...],
  "cta_slide": {"cta_primary": "...", "cta_secondary": "..."},
  "caption": "...",
  "hashtags": ["..."],
  "sound_suggestion": "...",
  "is_aigc": false,
  "scheduled_date": "2026-03-10",
  "image_prompts": []
}
```

**IMPORTANT: Output ONLY valid JSON. No explanations, reasoning, or text before or after the JSON.**
