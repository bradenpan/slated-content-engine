# Pinterest Pin Design Research Report — Slated Template Redesign

**Date:** 2026-02-26
**Purpose:** Inform the redesign of Slated's programmatic pin templates (HTML/CSS rendered to PNG via Puppeteer)
**Scope:** Food/recipe blog pins for organic Pinterest performance

---

## Table of Contents

1. [Pin Dimensions & Technical Specs](#1-pin-dimensions--technical-specs)
2. [Typography & Readability](#2-typography--readability)
3. [Color & Contrast](#3-color--contrast)
4. [Text Overlay Best Practices](#4-text-overlay-best-practices)
5. [Branding & Logo Placement](#5-branding--logo-placement)
6. [CTA Best Practices](#6-cta-best-practices)
7. [Pinterest Algorithm Considerations (2025-2026)](#7-pinterest-algorithm-considerations-2025-2026)
8. [High-Performing Food Pin Formats](#8-high-performing-food-pin-formats)
9. [Design Trends (2025-2026)](#9-design-trends-2025-2026)
10. [Competitive Landscape](#10-competitive-landscape)
11. [Template-Specific Recommendations](#11-template-specific-recommendations)
12. [Audit of Current Slated Templates](#12-audit-of-current-slated-templates)
13. [Sources](#13-sources)

---

## 1. Pin Dimensions & Technical Specs

### Optimal Dimensions
| Metric | Recommendation |
|---|---|
| **Standard Pin** | 1000 x 1500 px (2:3 aspect ratio) |
| **Idea Pins** | 1080 x 1920 px (9:16 aspect ratio) |
| **Maximum ratio** | 1:2.1 — but Pinterest is increasingly suppressing longer pins |
| **Minimum width** | 600 px (for acceptable quality) |
| **File format** | PNG for sharp text/graphics; JPG for photography-heavy |
| **File size** | Under 20 MB (recommended: 2-5 MB for fast loading) |

### Key Findings
- **2:3 ratio pins get 67% more engagement** than square pins.
- Vertical pins with 2:3 ratio earn **28-32% more saves** than square pins because they occupy more feed real estate.
- Pinterest feeds render thumbnails at approximately **236 px wide** on mobile (though this varies by device). Content must be legible at this scale.
- At ~300 px thumbnail width, the pin is scaled to roughly 0.3x. A 48 px headline at full size renders as ~14.4 px at thumbnail size — the minimum for legibility.

### Slated Current State: ALIGNED
The current templates use 1000 x 1500 px at 2:3, which matches best practices. No change needed on dimensions.

---

## 2. Typography & Readability

### Font Size Guidelines
| Element | Minimum (at 1000px canvas) | Recommended | At 300px thumbnail |
|---|---|---|---|
| **Main headline** | 48 px | 56-72 px | ~14-22 px |
| **Subheadline** | 30 px | 36 px | ~9-11 px |
| **Body / bullet text** | 24 px | 28-30 px | ~7-9 px |
| **Caption / fine print** | 20 px | 22-24 px | ~6-7 px |

### Font Selection
- **Sans-serif fonts dominate** on Pinterest. Bold, clean sans-serif fonts are the default recommendation for headlines because they read clearly on mobile.
- **Serif + sans-serif pairing** works well when contrast is needed. Use sans-serif for headlines (impact) and a serif for subtitles (elegance), or vice versa.
- **Avoid**: Script/cursive fonts for body text — they are difficult to read on mobile. Thin/light font weights under 36 px are also problematic.
- **Recommended families**: Poppins, Montserrat, Manrope (headline); Inter, DM Sans (body). The Slated choice of Manrope (headline) + Inter (body) is strong.
- **2026 trend**: Bold serif fonts are gaining traction in food/lifestyle niches for a "quiet luxury" aesthetic. A serif like Playfair Display or Libre Baskerville could work for an upscale food brand, but readability at thumbnail size must be tested.

### Readability Rules
- **Maximum 6-8 words per headline** — the current Slated guideline is correct.
- Test readability by scaling the pin to 30% (simulating mobile thumbnail). If you cannot read the headline, the font is too small or too thin.
- **High contrast between text and background is non-negotiable.** Pinterest users scroll fast; if text doesn't pop immediately, the pin is skipped.
- Headline text should convey the core value proposition of the pin in isolation — it is the user's primary decision point for whether to stop scrolling.

### Slated Current State: GOOD, minor adjustments possible
- Headline at 56 px (text-headline) is solid. Display at 72 px is excellent for impact.
- Body text at 30 px is at the lower boundary for thumbnail readability — acceptable for pins where the bullet content is supplementary to the headline, but may need bumping to 32 px.
- Caption at 24 px is fine for non-essential elements (logo text, attribution) but should not carry critical information.

---

## 3. Color & Contrast

### Pinterest Color Performance Data
- **Red and pink tones outperform blue by 2x** on food pins.
- **Warm colors** (reds, oranges, yellows) drive higher engagement in the food niche — they stimulate appetite and create a sense of warmth.
- **Pinterest 2025 trending colors**: Cherry Red, Butter Yellow, Aura Indigo, Dill Green, Alpine Oat.
- A MadPin Media case study found that **bright overlay colors can increase clicks by 37%** compared to muted overlays, specifically for pins that rank well in search.

### Color Psychology for Food
| Color | Association | Use Case |
|---|---|---|
| **Warm amber/orange** | Appetite, warmth, home cooking | Primary brand color — strong choice |
| **Red** | Urgency, appetite | Accent for CTAs, seasonal pins |
| **Green** | Fresh, healthy, natural | Health-focused recipes, ingredient pins |
| **Cream/off-white** | Clean, approachable, premium | Text panel backgrounds |
| **Dark charcoal** | Sophistication, contrast | Text backgrounds, overlays |

### Contrast Guidelines
- Text must have a **contrast ratio of at least 4.5:1** against its background for readability.
- On image-heavy pins, use solid or semi-transparent overlays (not just text shadows) to guarantee readability.
- Dark overlays at **60-75% opacity** provide reliable text readability over varied food photography.
- Gradient overlays work well when the gradient transitions from transparent (over the food) to opaque (behind text).

### Slated Current State: STRONG
- Amber (#D97706) is a warm food-aligned color. It performs well in the food niche.
- Emerald accent (#059669) provides good contrast and works for healthy/fresh content.
- Overlay opacities (60-75%) in the current CSS are well-calibrated.
- The warm cream surface color (#FAFAF9 / #FFFBEB) is clean and premium.

---

## 4. Text Overlay Best Practices

### Coverage & Density
- **Limit text overlay to approximately 20-30% of pin area.** The image guideline of "under 10% text" likely refers to Facebook's old rule; on Pinterest, text overlays are expected and beneficial, but should not overwhelm the visual.
- **One clear, benefit-driven headline is more effective** than multiple competing text elements.
- The text overlay should answer "What's in it for me?" instantly.
- Avoid cluttering the image — the pin's job in the feed is to be an **eye-catching hook**, not to deliver the full content.

### What Text to Include on the Pin
| Element | Include? | Purpose |
|---|---|---|
| **Headline** | ALWAYS | Stop-scroll hook; primary keyword |
| **Subtitle/tagline** | OFTEN | Context, timing, or promise ("Ready in 25 Min") |
| **Bullet points** | SOMETIMES | Only for tip/listicle formats; 2-3 max on image |
| **CTA** | SOMETIMES | When it adds value (not just "Click here") |
| **Brand/logo** | ALWAYS | Recognition, but should be quiet (not dominant) |
| **URL** | RARELY | Pinterest already shows the link domain |

### Mobile-First Design
- **Over 80% of Pinterest users browse on mobile.** This is the primary viewport.
- Text must be readable on a phone screen without zooming.
- Numbers in headlines ("7 Ways to...", "3 Simple Steps...") perform well because they create instant scannable structure.
- The headline is the "elevator pitch, headline, and call-to-action combined" — it determines whether someone engages or keeps scrolling.

### Slated Current State: MOSTLY ALIGNED
- Recipe-pin correctly prioritizes headline + subtitle (minimal text).
- Tip-pin has 3 bullet points which approaches the upper limit — consider whether all 3 are necessary on the pin image.
- Listicle-pin shows list items directly on the pin; at 5-7 items this may be too much text. Consider showing only the number + headline, with the full list on the landing page.

---

## 5. Branding & Logo Placement

### Best Practices
- Include branding on every pin for **recognition and authority** — consistent branding helps users identify your pins in their feed.
- Use **2-3 consistent fonts** across all pin templates to build visual brand identity.
- Logo should be **present but not dominant** — it is the quietest element on the pin.
- Typical placement: bottom-center or bottom-right.
- Logo size: small enough not to compete with the headline, large enough to be identifiable.
- Brand colors should be consistent across all pins to build recognition.

### Font Consistency
- Stick to the same font pair across all pin types. Users should be able to identify a Slated pin without seeing the logo.
- The Manrope + Inter combination is a strong, unique-enough pairing to serve as brand DNA.

### Slated Current State: GOOD
- Brand logo (cloche icon + "Slated." wordmark) appears on all templates at appropriate scale.
- Logo is correctly positioned as the quietest element (low opacity, small size).
- One minor concern: logo opacity varies across templates (0.45-0.7). Standardizing to a consistent opacity (e.g., 0.6) would improve brand consistency.

---

## 6. CTA Best Practices

### On-Pin CTAs
- **Pins with CTAs receive 80% more interactions** than those without.
- CTAs should be **2-4 words, 20-30 characters maximum**.
- Start with an action verb: "Get the Recipe", "Save This Plan", "Try This Tonight".
- Use bold, contrasting colors that stand out without overpowering the design.
- **Placement**: often as a small button or text element near the bottom of the pin, above the logo.

### CTA Wording for Food Blog
Good examples:
- "Get the Recipe" (direct, clear)
- "Save for Later" (encourages saves, which Pinterest rewards)
- "Try This Tonight" (urgency + actionable)
- "Your Week, Planned" (benefit-driven, brand-aligned)
- "See All 7 Recipes" (curiosity for listicles)

### Important: Description CTAs
Per the Slated brand-voice guide, Pinterest penalizes engagement bait in descriptions. CTAs should live primarily in the pin image, not the description text.

### Slated Current State: GAP IDENTIFIED
The current templates do NOT include an on-pin CTA element. Given that CTAs increase interactions by 80%, adding a small, optional CTA element to templates would be a significant improvement. This should be a subtle, brand-colored element — not an aggressive "CLICK NOW" button.

---

## 7. Pinterest Algorithm Considerations (2025-2026)

### Core Ranking Signals (2026)
Pinterest weighs four main signals:
1. **Quality** — High-resolution images, proper aspect ratio, non-spammy design
2. **Engagement** — Saves, clicks, close-ups
3. **Relevance** — Keyword alignment between pin content, description, alt text, and board topic
4. **Freshness** — New creative content is prioritized in distribution

### Fresh Content Guidelines
- **A fresh URL + fresh image = strongest fresh signal.** Even if the URL is the same, a new creative (different image/design) counts as a fresh pin.
- **3-7 new pins per week per topic cluster** is the recommended posting cadence for 2026.
- Pinterest uses AI-driven intent prediction and semantic indexing — it understands topics similarly to how Google understands web pages.
- Boards function like "subdomains" — organize them by clear topical authority, not random collections.

### What This Means for Slated's Templates
- Having **3 variants (A, B, C) per template type** is excellent for creating fresh visual content for the same blog post URL.
- Regularly cycling between variants for the same content type ensures the algorithm sees fresh creative.
- Alt text on pins earns **25% more impressions, 123% more outbound clicks, and 56% more profile visits** — the pipeline's alt text generation is critical.

### Image Quality
- Pinterest favors high-resolution, well-composed images.
- 89% of the most viral pins are image pins (not video).
- Pins with bold colors, simple text, and high-quality pictures get more distribution.
- Blurry, low-contrast, or overly busy images are suppressed.

---

## 8. High-Performing Food Pin Formats

### Recipe Pins
**What works:**
- **Hero food photography** is the primary draw — the image sells the recipe.
- Title should be specific: "25-Minute Chicken Stir Fry" outperforms "Easy Dinner Recipe".
- Include a timing/effort qualifier: "One Pan", "25 Minutes", "5 Ingredients".
- Rich Pins automatically add ingredients, prep time, ratings — so the pin image should NOT duplicate this data.
- **Best layout**: Large food image (60-70% of pin), clear title overlay, subtle subtitle with timing/effort.

**Layout recommendation:**
```
+---------------------------+
|                           |
|     HERO FOOD IMAGE       |
|       (60-70%)            |
|                           |
+---------------------------+
|  [accent bar]             |
|  Recipe Title             |
|  "Ready in 25 min"       |
|  [logo]                  |
+---------------------------+
```

### List/Tip Pins
**What works:**
- Numbers in the headline are critical: "7 Easy Weeknight Dinners"
- **3-5 items is the sweet spot** for on-pin list content. More than 5 becomes hard to read at thumbnail size.
- For longer lists (7+), show just the headline and number on the pin; let the landing page deliver the full list.
- Bullet formatting should be clean and scannable — number + short phrase, not full sentences.
- Each bullet/item should be 4-8 words maximum.

**Layout recommendation:**
```
+---------------------------+
|     [category label]      |
|     BIG NUMBER            |
|     List Headline         |
|  ________________________ |
|  1. Item one              |
|  2. Item two              |
|  3. Item three            |
|  4. Item four             |
|  5. Item five             |
|     [logo]                |
+---------------------------+
```

### Step-by-Step / Tutorial Pins
**What works:**
- Step-by-step guides perform "exceptionally well" on Pinterest — the DIY/how-to mindset is core to the platform.
- 3-5 steps is optimal for a single-image pin. More steps should use Idea Pins (multi-page format).
- Each step should have a number indicator and a concise label (not a paragraph).
- A flowchart or timeline visual connector between steps adds visual interest.
- **"Instructographics"** (infographic-style how-tos) are one of the top-performing content types on Pinterest.

### Problem-Solution Pins
**What works:**
- The visual split (dark problem area / warm solution area) creates tension that draws attention.
- The problem should be relatable and emotional: "When it's 5 PM and the fridge is a mystery."
- The solution should be confident and specific: "Your whole week of dinners, planned."
- This format works best when the problem resonates deeply with the target audience's daily frustration.
- The contrast between sections (color, tone, typography weight) should be dramatic.

**Layout recommendation:**
```
+---------------------------+
|   [dark background]       |
|   "The Problem"           |
|   Relatable pain point    |
|                           |
+===========================+
|   [warm background]       |
|   "The Answer"            |
|   Confident solution      |
|   [CTA] [logo]           |
+---------------------------+
```

### Infographic Pins
**What works:**
- Best used for **educational content**: meal prep guides, kitchen tips, substitution charts.
- Well-designed data visualizations perform exceptionally well in 2025-2026.
- Text density is higher than other formats, but each text block should be concise.
- Visual hierarchy through numbered steps, icons, or color-coded sections.
- Can accommodate more information than other formats because the user expectation is "this is a reference pin."

**When to use:**
- Kitchen tip compilations ("How to Store Every Vegetable")
- Substitution guides ("Dairy-Free Swaps for Every Recipe")
- Meal prep workflows ("Sunday Prep: 5 Dinners in 90 Minutes")

---

## 9. Design Trends (2025-2026)

### Current Trends
1. **Bold minimalism**: Clean structure with bold typography and strong color, not cluttered maximalism.
2. **Type as hero**: Oversized typography as the primary visual element (especially for non-photo pins).
3. **Texture and depth**: Subtle paper textures, grain overlays, and shadow effects for organic warmth.
4. **Serif revival**: Elegant serif fonts for food/lifestyle content ("quiet luxury" aesthetic).
5. **"Refined Grit"**: Subtle texture backgrounds, bold recipe names, hand-written elements for a personal touch.
6. **Neo Deco**: Clean geometric layouts with confident typography — a modern take on Art Deco.
7. **Playful color**: Moving beyond muted palettes toward more vibrant, confident color choices.

### What's Declining
- Overly decorated, template-heavy designs (Canva "default" look).
- Heavy use of script fonts.
- Busy collage layouts with many small images.
- Pins that look like generic Canva templates (users have template fatigue).

### Recommended Mix for Food Blog
- **40% educational** (how-tos, tutorials, step-by-step guides)
- **30% inspirational** (beautiful food photography, recipe showcases)
- **20% product/service** (brand-specific value propositions)
- **10% personal/behind-the-scenes** (brand personality)

---

## 10. Competitive Landscape

### What Top Food Bloggers Do
Based on analysis of popular food Pinterest accounts and template providers:

1. **Photography-forward recipe pins** dominate the food niche — the food image is always the hero.
2. **Consistent brand colors** across all pins (users can spot a specific blogger's pins at a glance).
3. **Bold, sans-serif headlines** with high contrast against the image.
4. **Clean, warm backgrounds** (cream, off-white) for text-heavy pins.
5. **Minimal text on recipe pins** — just the recipe name and a timing/difficulty qualifier.
6. **More text on educational/tip pins** — but still structured with clear visual hierarchy.
7. **Consistent template system** — most successful food pinners use 3-5 template variants and rotate them.

### Differentiation Opportunities for Slated
- Most food bloggers' pins look similar (Canva templates). Slated's programmatic templates can be more polished and unique.
- The amber/emerald color palette is distinctive — few food blogs use this combination.
- The cloche brand mark is unique and recognizable.
- **Opportunity**: Add a CTA element tied to the product (e.g., "Plan Your Week" rather than generic "Get the Recipe").

---

## 11. Template-Specific Recommendations

### recipe-pin

**Current state**: 3 variants (bottom bar, side panel, full bleed). Photography-forward with headline + subtitle.

**Recommendations:**
| Area | Current | Recommended | Rationale |
|---|---|---|---|
| Layout | 3 variants | Keep 3 variants; they provide fresh content rotation | Algorithm favors fresh creative |
| Hero image area | 65-68% (Variant A) | 60-70% is ideal; current is right | Food photo must dominate |
| Text elements | Headline + subtitle | Add optional CTA element ("Get the Recipe") | +80% interaction with CTA |
| Headline size | 56px | Keep at 56px or test at 60px | Good legibility at thumbnail |
| Subtitle | 36px, full sentence | Shorten to 3-5 words: "One Pan / 25 Min" | Mobile readability |
| Variant B panel width | 45% | Consider 40% panel / 60% image | More photo real estate |
| Variant C gradient | 55% height, 0.88 max opacity | Good as-is | Reliable text readability |

**Template variable additions:**
- `{{cta_text}}` — Optional CTA text (default: "Get the Recipe")
- `{{time_badge}}` — Optional timing badge ("25 min")

### tip-pin

**Current state**: 3 variants. Text-heavy with 2-3 bullet points.

**Recommendations:**
| Area | Current | Recommended | Rationale |
|---|---|---|---|
| Bullet count | 2-3 (3rd optional) | Keep 2-3; 3 is the max for mobile readability | Research confirms 3-5 optimal |
| Bullet text | Full sentences possible | Limit to 8-10 words per bullet | Thumbnail readability |
| Category label | Fixed ("Tips & Advice" / "Meal Planning Tips") | Make dynamic: `{{category_label}}` | Keyword targeting |
| CTA | None | Add optional CTA ("Save These Tips") | +80% interaction |
| Variant C cards | Translucent bg with accent border | Good pattern; keep it | Creates visual structure |

### listicle-pin

**Current state**: 3 variants. Large number, list items displayed on pin.

**Recommendations:**
| Area | Current | Recommended | Rationale |
|---|---|---|---|
| List items shown | All items on pin | **Show max 5 items on pin**; for lists of 7+, show 5 and add "...and more" | Readability at thumbnail |
| Item text size | 26px | Bump to 28px for better mobile legibility | Currently at lower bound |
| Number prominence | 140-160px | Keep large; numbers are the #1 scroll-stopper | Data supports this |
| Variant B | Image top + list below | Good structure; keep | Combines visual appeal with info |
| CTA | None | Add "See All [N] Recipes" for long lists | Drives curiosity clicks |

### problem-solution-pin

**Current state**: 3 variants. Split design with color contrast.

**Recommendations:**
| Area | Current | Recommended | Rationale |
|---|---|---|---|
| Problem tone | Dark, muted | Good — maintain tension contrast | Emotional resonance |
| Solution tone | Warm, confident | Good — the "relief" moment | Aligns with brand voice |
| CTA | None | Add to solution section ("Here's How") | Directs to action |
| Variant A split | 45% problem / 55% solution | Consider 40/60 — solution should be dominant | Solution = value |
| Arrow/separator | Variant B has arrow; C has dot line | Both good; ensure arrow is prominent enough at thumbnail | Visual flow matters |
| Problem text | Same font weight as solution | Consider lighter weight for problem, bolder for solution | Visual hierarchy reinforcement |

### infographic-pin

**Current state**: 3 variants. Numbered steps, grid, timeline.

**Recommendations:**
| Area | Current | Recommended | Rationale |
|---|---|---|---|
| Step count | No explicit limit | Limit to 4-5 steps per pin | Readability at thumbnail |
| Step text size | 28px (A), 24px (B), 26px (C) | Standardize at 26-28px minimum | Mobile readability consistency |
| When to use | Step-by-step guides | Also use for: substitution charts, storage guides, prep timelines | High-value evergreen content |
| Footer text | Optional caption | Use for CTA: "Save This Guide" | Encourages saves |
| Variant B grid | 2-column | Good for 4-6 items; awkward for odd numbers | Consider 3-column for 6 items |

---

## 12. Audit of Current Slated Templates

### What's Working Well
1. **Dimensions**: 1000x1500 px (2:3) matches best practices exactly.
2. **Safe zone**: 100px margins (10%) protect content from edge cropping.
3. **Font pairing**: Manrope + Inter is clean, distinctive, and highly readable.
4. **Color palette**: Warm amber is ideal for food. Emerald accent provides differentiation.
5. **Variant system**: 3 variants per type enables fresh content rotation (algorithm-aligned).
6. **Typography scale**: Well-structured from 72px display to 22px labels.
7. **Overlay system**: Dark/gradient overlays at appropriate opacities for text readability.
8. **Brand consistency**: Logo + wordmark appears on all templates.

### Gaps to Address
1. **No CTA element** on any template — this is the single highest-impact improvement available (+80% interactions).
2. **Logo opacity inconsistency** — ranges from 0.45 to 0.7 across templates. Should standardize.
3. **No time/difficulty badge** on recipe pins — a common and effective element in food pin design.
4. **Listicle item text** at 26px is at the lower readability bound for mobile thumbnails.
5. **Category labels are hardcoded** ("Tips & Advice", "Meal Planning Tips", "Step by Step") — should be template variables for keyword targeting.
6. **No CTA in infographic footer** — "Save This Guide" would encourage saves, which Pinterest rewards.

### Priority Improvements (Ranked by Impact)
1. **Add CTA element across all templates** — optional, small, brand-colored button or text line
2. **Make category/section labels dynamic** — enables better keyword targeting per pin
3. **Add time/difficulty badge to recipe-pin** — common and expected in food niche
4. **Standardize logo opacity** — brand consistency
5. **Bump listicle item text from 26px to 28px** — mobile readability
6. **Add "...and more" truncation logic to listicle items** — prevent overcrowding on long lists

---

## 13. Sources

### Pin Dimensions & Technical Specs
- [Pinterest Pin Size 2026: Complete Guide — SocialRails](https://socialrails.com/blog/pinterest-pin-size-dimensions-guide)
- [Pinterest Pin Dimensions 2026 — RecurPost](https://recurpost.com/blog/pinterest-pin-dimensions/)
- [Pinterest Pin Size 2026 — SocialChamp](https://www.socialchamp.com/blog/pinterest-pin-size/)
- [Pinterest Size Guide: Standard vs Long Pins — MadPin Media](https://madpinmedia.com/pinterest-size-guide/)
- [Pinterest Image Size Guide 2026 — Outfy](https://www.outfy.com/blog/pinterest-image-size-guide/)
- [Pinterest Image Sizes 2026 — ImageForPost](https://imageforpost.com/guides/pinterest-image-sizes-dimensions-guide-2026)
- [Pinterest Post Dimensions 2025 — UseVisuals](https://usevisuals.com/blog/pinterest-post-dimensions-and-specifications)

### Typography & Text Overlays
- [Text Overlays for Pinterest Pin Designs — AJ Graphics](https://aj-graphics.org/2025/02/26/how-to-use-text-overlays-for-pinterest-pin-designs/)
- [Designing Pins: Text Overlays Dos & Don'ts — Pinterest Business Community](https://community.pinterest.biz/t/designing-pins-text-overlays-dos-donts/661)
- [Adding Text to Pinterest Pins — Tailwind](https://www.tailwindapp.com/blog/adding-text-to-pinterest-pins)
- [Perfect Font Pairs for Pinterest — Tailwind](https://www.tailwindapp.com/blog/font-pairs-on-pinterest-pins)
- [Pinterest Fonts: Best Pairings — Petite Capsule](https://petitecapsule.com/pinterest-fonts-best-font-pairings-for-pinterest-pins/)
- [50+ Canva Font Pairings for Pinterest — Made by Melody](https://madebymelody.co/canva-font-pairings-for-pinterest-pins/)

### Color & Design
- [2025 Pinterest Trending Colors — Haute Stock](https://hautestock.co/2025-pinterest-trending-colors-to-boost-pin-reach/)
- [Pinterest Palette: 5 Trending Colors 2025 — Pinterest Business](https://business.pinterest.com/blog/2025-pinterest-palette-this-years-trending-colors/)
- [Ranking Colors on Pinterest — MadPin Media](https://madpinmedia.com/what-are-ranking-colors-on-pinterest-and-how-to-use-them/)
- [Overlay Color +37% Clicks Case Study — MadPin Media](https://madpinmedia.com/pinterest-overlay-colors-case-study/)
- [Pin Layout +45% Clicks Case Study — MadPin Media](https://madpinmedia.com/pin-layout-case-study/)
- [Font Type Clicks Case Study — MadPin Media](https://madpinmedia.com/which-font-type-gets-the-most-clicks-on-pinterest-case-study/)
- [How to Choose Colors for Pinterest — Brilliant Marketing](https://brilliantmarketing.info/how-to-choose-colours/)

### Algorithm & SEO
- [Pinterest Algorithm 2026 — Outfy](https://www.outfy.com/blog/pinterest-algorithm/)
- [Pinterest Algorithm 2026 — Sprout Social](https://sproutsocial.com/insights/pinterest-algorithm/)
- [Pinterest Algorithm Ranking Factors 2026 — RecurPost](https://recurpost.com/blog/pinterest-algorithm/)
- [Pinterest Algorithm Updates 2026 — Anita Dykstra](https://anitadykstra.com/how-does-the-pinterest-algorithm-work/)
- [Pinterest Algorithm Changes 2025 — MadPin Media](https://madpinmedia.com/what-changed-in-pinterest-algorithm/)
- [Pinterest SEO 2025 — Tailwind](https://www.tailwindapp.com/blog/pinterest-seo-in-2025)
- [Pinterest Alt Text Best Practices 2025 — My Pin Saver](https://mypinsaver.com/pinterest-alt-text-best-practices-2025/)
- [Pinterest Alt Text for Accessibility & SEO — Tailwind](https://www.tailwindapp.com/blog/pinterest-alt-text-for-better-accessibility-and-seo)
- [Creator's Guide to SEO — Pinterest Create](https://create.pinterest.com/blog/seo-best-practices/)

### CTAs
- [Pinterest CTA Options — Jana O. Media](https://janaomedia.com/pinterest-calls-to-action-ideas/)
- [Pinterest Calls to Action — Sarah Burk](https://sarahburk.com/pinterest-calls-to-action/)
- [CTA on Pinterest — The Pinnergrammer](https://thepinnergrammer.com/how-to-do-a-call-to-action-on-pinterest/)
- [CTAs — Pinterest Business Help](https://help.pinterest.com/en/business/article/calls-to-action-ctas)
- [CTAs for Pinterest Pins — Emilee Vales](https://emileevales.com/the-best-call-to-action-ctas-for-your-pinterest-pins/)

### Food Pin Design & Templates
- [Pinterest for Food Bloggers — Feast Design Co](https://feastdesignco.com/how-to/pinterest-for-food-bloggers/)
- [How to Create Recipe Pins — Katie Grazer](https://whatskatieupto.com/how-to-create-recipe-pins-easy-4-step-tutorial/)
- [Creating Pinterest Images for Food Blog — Tastemaker Conference](https://tastemakerconference.com/how-to-create-pinterest-images-for-your-food-blog/)
- [Pinterest Images for Food Blog — Food Bloggers of Canada](https://www.foodbloggersofcanada.com/creating-pinterest-images-for-your-food-blog/)
- [Pinterest Pin Design Do's & Don'ts — Tailwind](https://www.tailwindapp.com/blog/dos-and-donts-of-pinterest-pin-design)
- [Should You Brand Your Pinterest Pins — Kristin Rappaport](https://kristinrappaport.com/branding-pinterest-pins/)
- [Pinterest Pin Design for Blog Traffic — Margaret Bourne](https://www.margaretbourne.com/create-pinterest-pins/)
- [Rich Pins — Pinterest Business Help](https://help.pinterest.com/en/business/article/rich-pins)

### Trends (2025-2026)
- [Trending Design Styles for Pinterest 2026 — MadPin Media](https://madpinmedia.com/trending-design-styles-for-pinterest-pins/)
- [Pinterest Pin Design Trends 2025 — Post2Pin](https://post2pin.com/blog/posts/pinterest-pin-design-trends)
- [5 Pinterest Trends 2026 — Creative Bloq](https://www.creativebloq.com/design/the-5-pinterest-trends-worth-following-in-2026)
- [Graphic Design Trends 2026 — Kittl](https://www.kittl.com/blogs/graphic-design-trends-2026/)
- [Pinterest Scroll-Stopping Pin Design — Jenna Kutcher](https://jennakutcherblog.com/pinterest-pin-design-tips/)
- [Mobile Pin Optimisation — MadPin Media](https://madpinmedia.com/pin-mobile-optimisation-basics/)
- [Most Popular Pinterest Pins 2025 — WebFX](https://www.webfx.com/blog/social-media/most-popular-pinterest-pins/)

### Strategy & Analytics
- [Pinterest Growth Strategy 2026 — Medium](https://medium.com/@carolinaminor/pinterest-growth-strategy-2026-the-new-algorithm-override-system-steal-the-framework-power-users-acc27f947bf4)
- [Pinterest Engagement Rate — Sprout Social](https://sproutsocial.com/insights/pinterest-engagement-rate/)
- [Pinterest Engagement 2026 — Metricool](https://metricool.com/pinterest-engagement/)
- [Pinterest Marketing Benchmark Report 2025 — Tailwind](https://www.tailwindapp.com/pinterest-marketing/research/2025-benchmark-study-part-2)
- [Pin Descriptions & Titles Optimization 2025 — Tailwind](https://www.tailwindapp.com/blog/optimize-pinterest-pin-descriptions-titles-in-2025-a-practical-testable-framework)
