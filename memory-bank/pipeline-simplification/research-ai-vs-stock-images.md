# Research: AI Image Generation vs Stock Image APIs

**Date:** 2026-02-24
**Context:** Slated Pinterest Pipeline — top-down overhead food photography for meal planning/family lifestyle content
**Volume:** ~150 images/month (28 pins/week + ~33% regen rate)
**Target format:** 1024x1536 portrait (Pinterest optimal)
**Data source:** Web research (all pricing verified from official documentation, February 2026)

---

## Table of Contents

1. [Current Implementation Summary](#1-current-implementation-summary)
2. [AI Image Generation Options](#2-ai-image-generation-options)
3. [Stock Image API Options](#3-stock-image-api-options)
4. [Cost Modeling](#4-cost-modeling)
5. [Quality Assessment for Overhead Food Photography](#5-quality-assessment-for-overhead-food-photography)
6. [Resolution Compatibility](#6-resolution-compatibility)
7. [Gemini Free Tier Feasibility](#7-gemini-free-tier-feasibility)
8. [Licensing and IP Considerations](#8-licensing-and-ip-considerations)
9. [Recommendations](#9-recommendations)

---

## 1. Current Implementation Summary

The pipeline uses a tiered image sourcing strategy:

| Tier | Source | Cost | How It Works |
|------|--------|------|--------------|
| **Tier 1 (Stock)** | Unsplash + Pexels | Free | Search both APIs, Claude ranks thumbnails via vision. If best score < 6.5, retry with broader query. If retry < 5, fall back to Tier 2. |
| **Tier 2 (AI)** | OpenAI gpt-image-1 or Flux Pro (Replicate) | $0.05-$0.25/image | Generate from Claude-crafted prompt. Claude vision validates result. One retry with feedback if score < 6.5. |
| **Tier 3 (Template-only)** | None | Free | No image needed; text-only pin templates. |

**Current provider details:**
- `image_stock.py`: Unsplash (50 req/hr free, 5K/hr at Production) + Pexels (200 req/hr, 20K/month free)
- `image_gen.py`: OpenAI gpt-image-1 at 1024x1536 high quality ($0.25/image) or Flux Pro via Replicate ($0.05)
- Default provider: OpenAI (configurable via `IMAGE_GEN_PROVIDER` env var)

> **IMPORTANT cost correction:** The code requests gpt-image-1 at 1024x1536 with `quality="high"`. Per OpenAI's current pricing, this costs **$0.25/image** (not $0.08 as previously estimated). The $0.08 price only applies to 1024x1024 at high quality. See Section 2.1 for full pricing breakdown.

---

## 2. AI Image Generation Options

### Quick-Reference Price Comparison (per image at ~1024x1024)

| Provider | Model | Price/Image | Notes |
|---|---|---|---|
| OpenAI | GPT Image 1 Mini (low) | $0.005 | Cheapest OpenAI |
| OpenAI | GPT Image 1 Mini (med) | $0.011 | |
| OpenAI | GPT Image 1 Mini (high) | $0.036 | |
| OpenAI | GPT Image 1.5 (low) | ~$0.009 | Latest flagship |
| OpenAI | GPT Image 1.5 (med) | ~$0.04 | |
| OpenAI | GPT Image 1.5 (high) | ~$0.20 | |
| OpenAI | GPT Image 1 (low) | ~$0.02 | Current model |
| OpenAI | GPT Image 1 (med) | ~$0.07 | |
| OpenAI | GPT Image 1 (high) | ~$0.19 | |
| OpenAI | DALL-E 3 (standard) | $0.040 | Previous gen |
| OpenAI | DALL-E 3 (HD) | $0.080 | |
| Google | Gemini 2.5 Flash Image | $0.039 | Batch: $0.0195; **free tier available** |
| Google | Gemini 2.0 Flash Image | $0.039 | Batch: $0.0195; **deprecating March 3, 2026** |
| Google | Imagen 4 Fast | $0.020 | Cheapest Google paid |
| Google | Imagen 4 | $0.040 | |
| Google | Imagen 4 Ultra | $0.060 | |
| BFL | FLUX.1 schnell (Replicate) | $0.003 | Fast/low quality |
| BFL | FLUX.1 dev (Replicate) | $0.030 | |
| BFL | FLUX 1.1 Pro (direct) | $0.040 | |
| BFL | FLUX 2 Pro (1MP) | $0.030 | Best food photorealism |
| Stability | Stable Image Core | $0.030 | |
| Stability | SD 3.5 Large | $0.065 | |
| Stability | Stable Image Ultra | $0.080 | |
| Adobe | Firefly API | ~$0.02 | IP-safe; pay-as-you-go |
| Ideogram | V3 Turbo | $0.030 | Best text rendering |
| Ideogram | 3.0 standard | ~$0.060 | |
| Recraft | V4 raster | $0.040 | |
| Leonardo | Phoenix (est.) | ~$0.026 | Credit-based |
| Unsplash | Stock photos | **FREE** | 5,000 req/hr (prod) |
| Pexels | Stock photos | **FREE** | 200 req/hr default |

*Sources: [OpenAI Pricing](https://openai.com/api/pricing/), [Gemini Pricing](https://ai.google.dev/gemini-api/docs/pricing), [Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing), [BFL Pricing](https://bfl.ai/pricing), [Stability Pricing](https://platform.stability.ai/pricing), [Replicate Flux](https://replicate.com/collections/flux)*

---

### 2.1 OpenAI GPT Image 1 (Current)

| Attribute | Detail |
|-----------|--------|
| **Model** | gpt-image-1 |
| **Cost (1024x1536, high)** | **$0.25/image** |
| **Cost (1024x1536, medium)** | ~$0.07/image |
| **Cost (1024x1536, low)** | ~$0.02/image |
| **Cost (1024x1024, high)** | ~$0.19/image |
| **API** | REST, well-documented, already integrated |
| **Portrait support** | Native 1024x1536 support |
| **Food quality** | Good for overhead/flat-lay. Occasional artifacts on utensils and hands. |
| **Strengths** | Easy integration (already in pipeline), reliable API, decent photorealism |
| **Weaknesses** | Expensive at high quality + portrait; newer models surpass it in photorealism |

*Sources: [OpenAI API Pricing](https://openai.com/api/pricing/), [costgoat.com](https://costgoat.com/pricing/openai-images)*

### 2.2 OpenAI GPT Image 1.5 (Upgrade Path)

| Attribute | Detail |
|-----------|--------|
| **Model** | gpt-image-1.5 |
| **Cost (1024x1536, high)** | ~$0.20/image |
| **Cost (1024x1536, medium)** | ~$0.05/image |
| **Cost (1024x1536, low)** | ~$0.013/image |
| **API** | Same OpenAI API, drop-in model name change |
| **Portrait support** | Native 1024x1536 support |
| **Food quality** | Significantly improved over gpt-image-1. Best text rendering of any model. |
| **Strengths** | Highest LM Arena score (1264); excellent text rendering; trivial migration from current setup |
| **Weaknesses** | High quality tier still expensive; medium tier is the sweet spot |

*Sources: [OpenAI API Pricing](https://openai.com/api/pricing/), [eesel.ai](https://www.eesel.ai/blog/gpt-image-1-mini-pricing)*

### 2.3 OpenAI GPT Image 1 Mini (Budget Option)

| Attribute | Detail |
|-----------|--------|
| **Model** | gpt-image-1-mini |
| **Cost (1024x1024, low)** | $0.005/image |
| **Cost (1024x1024, medium)** | $0.011/image |
| **Cost (1024x1024, high)** | $0.036/image |
| **Full range** | $0.005-$0.052/image |
| **API** | Same OpenAI API |
| **Food quality** | Acceptable for thumbnails; not ideal for hero images |
| **Strengths** | 54-70% cheaper than full GPT Image 1; same API integration |
| **Weaknesses** | Lower quality output; may not meet quality bar for Pinterest hero images |

*Sources: [OpenAI API Pricing](https://platform.openai.com/docs/pricing), [eesel.ai](https://www.eesel.ai/blog/gpt-image-1-mini-pricing)*

### 2.4 OpenAI DALL-E 3 (Previous Generation)

| Attribute | Detail |
|-----------|--------|
| **Model** | dall-e-3 |
| **Cost (1024x1024, standard)** | $0.040/image |
| **Cost (1024x1024, HD)** | $0.080/image |
| **Cost (1792x1024, standard)** | $0.080/image |
| **Cost (1792x1024, HD)** | $0.120/image |
| **API** | Same OpenAI API; separate endpoint from GPT Image models |
| **Portrait support** | 1024x1792 supported natively |
| **Food quality** | Moderate. Good for stylized images, less photorealistic than newer models. |
| **Strengths** | Well-tested, stable, good prompt following |
| **Weaknesses** | Superseded by GPT Image 1/1.5 in quality and cost-efficiency; more "illustration-like" than photorealistic |
| **Verdict** | **Not recommended** — GPT Image 1.5 medium is better quality at similar or lower price |

*Sources: [OpenAI API Pricing](https://openai.com/api/pricing/)*

### 2.5 OpenAI DALL-E 2 (Legacy)

| Attribute | Detail |
|-----------|--------|
| **Cost (1024x1024)** | $0.020/image |
| **Cost (512x512)** | $0.018/image |
| **Verdict** | **Not recommended** — oldest model, lowest quality. Only mentioned for completeness. |

### 2.6 Google Gemini 2.5 Flash Image

| Attribute | Detail |
|-----------|--------|
| **Model** | gemini-2.5-flash-image-preview |
| **Cost** | $0.039/image (1290 output tokens at $30/1M tokens) |
| **Batch API** | $0.0195/image (50% discount, 24-hour processing) |
| **Max resolution** | 1024x1024 |
| **Free tier** | Conflicting info — third-party sources report 500 RPD free; official docs unclear. See [Gemini Free Tier Analysis](research-gemini-free-tier-analysis.md) |
| **IPM (Free)** | ~2 images/minute |
| **IPM (Tier 1)** | 10 images/minute |
| **API** | Google AI Studio / Vertex AI |
| **Food quality** | Strong composition through advanced reasoning; 2-3x faster than 2.0 Flash; enhanced character consistency |
| **Strengths** | Cheap (especially batch); free tier potentially viable; native text+image multimodal |
| **Weaknesses** | Max 1024x1024 — **cannot produce our 1024x1536 portrait format natively**; free tier stability uncertain; new model with limited food-specific benchmarks |

*Sources: [Gemini Pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini 2.5 Flash Image Blog](https://developers.googleblog.com/en/introducing-gemini-2-5-flash-image/)*

### 2.7 Google Gemini 2.0 Flash Image

| Attribute | Detail |
|-----------|--------|
| **Model** | gemini-2.0-flash-preview-image-generation |
| **Status** | **DEPRECATED — retiring March 3, 2026** |
| **Cost** | $0.039/image (identical to 2.5 Flash) |
| **Batch API** | $0.0195/image |
| **Max resolution** | 1024x1024 |
| **Free tier** | Available; 1,500 free images/day reported; ~2 IPM rate limit |
| **Food quality** | Strong text rendering, advanced reasoning for realistic imagery |
| **Strengths** | Confirmed free tier; strong reasoning capability |
| **Weaknesses** | **Retiring in days**; same 1024x1024 limitation; 2.5 Flash is strictly better |

*Sources: [Gemini Pricing](https://ai.google.dev/gemini-api/docs/pricing), [Google Developers Blog](https://developers.googleblog.com/en/experiment-with-gemini-20-flash-native-image-generation/)*

### 2.8 Google Imagen 4 (Vertex AI)

| Attribute | Detail |
|-----------|--------|
| **Models** | imagen-4.0-fast, imagen-4.0-generate-001, imagen-4.0-ultra |
| **Cost** | Fast: $0.02/image, Standard: $0.04/image, Ultra: $0.06/image |
| **Upscaling** | $0.06/image (to 2K/4K) |
| **API** | Vertex AI (requires GCP project + billing) |
| **Free tier** | No free tier for API usage |
| **Food quality** | Fast rated ~5/10 for food; Ultra rated ~8/10 |
| **Strengths** | Competitive pricing (Fast is cheapest Google option); good GCP integration |
| **Weaknesses** | Requires GCP setup; no free tier; Fast quality insufficient for hero images |

*Sources: [Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)*

### 2.9 FLUX (Black Forest Labs) — Current Alternative

| Attribute | Detail |
|-----------|--------|
| **Models** | FLUX.1 schnell ($0.003), FLUX.1 dev ($0.030), FLUX 1.1 Pro ($0.040), FLUX 2 Pro (~$0.030/MP), FLUX 2 Max |
| **BFL Direct API** | 1 credit = $0.01 USD |
| **Replicate** | Already partially integrated in pipeline |
| **Food quality** | **Best-in-class photorealism.** FLUX 2 Max: "most convincing product photography." FLUX 2 Pro: "often indistinguishable from professional photography." Excels at lighting, textures, material physics. |
| **For overhead food** | Excellent. Best at capturing natural lighting, food textures, table surfaces, and realistic plating. |
| **Strengths** | Top photorealism; competitive pricing; Replicate integration already exists |
| **Weaknesses** | Replicate adds polling latency; BFL direct API would need new integration; MP-based pricing can vary |

*Sources: [BFL Pricing](https://bfl.ai/pricing), [BFL Docs](https://docs.bfl.ml/quick_start/pricing), [Replicate Flux](https://replicate.com/collections/flux)*

### 2.10 Stability AI

| Attribute | Detail |
|-----------|--------|
| **Models** | Stable Image Core ($0.03), SD 3.5 Medium ($0.035), SD 3.5 Large ($0.065), Stable Image Ultra ($0.08) |
| **Pricing** | $0.01/credit; prices increased August 2025 |
| **License** | Community license free for <$1M revenue |
| **Food quality** | Decent but not top-tier for food photography specifically |
| **Strengths** | Moderate pricing; open-weight model options for self-hosting |
| **Weaknesses** | Not food-specialized; Stability AI has had financial instability concerns; some older endpoints deprecated |

*Sources: [Stability Pricing](https://platform.stability.ai/pricing), [Stability API Update](https://stability.ai/api-pricing-update-25)*

### 2.11 Midjourney

| Attribute | Detail |
|-----------|--------|
| **API** | **No official API as of Feb 2026.** No REST endpoint, SDK, webhook, or API key system. |
| **Workarounds** | Unofficial third-party APIs (ImagineAPI, APIFRAME, PiAPI) violate TOS, risk account ban |
| **Subscription** | Basic $10/mo, Standard $30/mo, Pro $60/mo, Mega $120/mo |
| **Food quality** | Excellent — best for stylized/"expensive-looking" food imagery, not literal photorealism |
| **Verdict** | **Not viable** for automated pipelines due to API unavailability |

*Sources: [Midjourney Docs](https://docs.midjourney.com/hc/en-us), [myarchitectai.com](https://www.myarchitectai.com/blog/midjourney-apis)*

### 2.12 Adobe Firefly

| Attribute | Detail |
|-----------|--------|
| **Cost** | ~$0.02/image (pay-as-you-go); range $0.04-$0.12 depending on resolution |
| **Subscription** | Standard $9.99/mo (2K credits), Pro $19.99/mo (4K credits) |
| **API** | Firefly Services API (REST) |
| **Food quality** | Good for commercial work; consistent and "safe" outputs. "Strong alternative" for artistic food imagery. |
| **Strengths** | IP-safe training (Adobe Stock + public domain only); commercial indemnification; competitive pay-as-you-go pricing |
| **Weaknesses** | Not as photorealistic as FLUX 2 or GPT-Image-1.5; enterprise-focused API may require sales contact |

*Sources: [Adobe Firefly API](https://developer.adobe.com/firefly-services/docs/firefly-api/), [saascrmreview.com](https://saascrmreview.com/adobe-firefly-pricing/)*

### 2.13 Ideogram

| Attribute | Detail |
|-----------|--------|
| **Models** | V3 Turbo ($0.03), 3.0 standard (~$0.06), V2 ($0.08 on Replicate) |
| **API** | REST API with credit balance + auto-top-up |
| **Food quality** | Decent but not food-specialized |
| **Strengths** | Best-in-class text rendering (~90% accuracy). Character consistency (3.0). Relevant for Pinterest pins with text overlays. |
| **Weaknesses** | Not top-tier for photorealism |

*Sources: [Ideogram API Pricing](https://ideogram.ai/features/api-pricing), [Ideogram Docs](https://docs.ideogram.ai/plans-and-pricing/ideogram-api)*

### 2.14 Recraft V4

| Attribute | Detail |
|-----------|--------|
| **Cost** | V4 raster: $0.04/image (1024x1024, ~10 sec); V4 Pro raster: $0.08/image (2048x2048); V4 vector: $0.04; V4 Pro vector: $0.25 |
| **Food quality** | Better suited for design/branding than photorealistic food |
| **Strengths** | Good for design-oriented pins; vector support; strong text rendering |
| **Weaknesses** | Not optimized for photorealistic food photography |

*Sources: [Recraft Pricing](https://www.recraft.ai/pricing?tab=api), [Recraft V4 Blog](https://www.recraft.ai/blog/introducing-recraft-v4-design-taste-meets-image-generation)*

### 2.15 Leonardo AI

| Attribute | Detail |
|-----------|--------|
| **Cost** | Token/credit-based. API Basic: $9/mo (3,500 credits); ~$0.026/image estimated at Basic tier |
| **Models** | Phoenix 1.0/0.9, Alchemy, PhotoReal |
| **Free tier** | 150 tokens/day |
| **Food quality** | Good general quality; not food-specialized |
| **Weaknesses** | Complex credit system; recent price increases; less documentation on per-image costs |

*Sources: [Leonardo Pricing](https://leonardo.ai/pricing), [Leonardo Docs](https://docs.leonardo.ai/docs/plan-with-the-pricing-calculator)*

---

## 3. Stock Image API Options

### 3.1 Unsplash (Current)

| Attribute | Detail |
|-----------|--------|
| **Cost** | **Free** — no paid tiers |
| **Rate Limits** | Demo: 50 req/hr; Production (free with approval): 5,000 req/hr |
| **License** | Irrevocable, nonexclusive, worldwide. Free for commercial use. Attribution encouraged but not required. |
| **Food selection** | Good variety. Community-contributed, quality varies. |
| **Note** | Only JSON API requests count toward limits; image file requests do not |

*Sources: [Unsplash API Docs](https://unsplash.com/documentation), [Unsplash Developers](https://unsplash.com/developers)*

### 3.2 Pexels (Current)

| Attribute | Detail |
|-----------|--------|
| **Cost** | **Free** — no paid tiers |
| **Rate Limits** | 200 req/hr, 20,000/month; unlimited available free if eligible (email api@pexels.com) |
| **License** | Free for personal and commercial use. No attribution required. Cannot sell unmodified copies. |
| **Food selection** | Similar to Unsplash; good general food photography |

*Sources: [Pexels API Docs](https://www.pexels.com/api/documentation/), [Pexels Unlimited Requests](https://help.pexels.com/hc/en-us/articles/900005852323)*

### 3.3 Shutterstock API

| Attribute | Detail |
|-----------|--------|
| **Cost** | Free tier: watermarked previews only. Production: custom pricing via sales. On-demand: $29+/image. |
| **Food selection** | Excellent. Massive library with professional food photography. |
| **Verdict** | Not practical at our volume without enterprise deal. |

### 3.4 Getty Images / Adobe Stock

| Attribute | Detail |
|-----------|--------|
| **Cost** | Getty: $100+/download. Adobe Stock: Enterprise API only, consumer plans from $29.99/mo. |
| **Verdict** | Premium quality but orders of magnitude more expensive than needed. |

### 3.5 Foodiesfeed (Food-Specific)

| Attribute | Detail |
|-----------|--------|
| **Cost** | Free (CC0); Premium: $49 lifetime |
| **API** | **No public API** |
| **Food selection** | Excellent — exclusively food photography |
| **Verdict** | Great for manual supplementation / local library, but not automatable. |

---

## 4. Cost Modeling

### Monthly Volume Assumptions
- 150 images/month total
- Current split: ~80% stock (120 images), ~20% AI fallback (30 images)
- Target resolution: 1024x1536 (portrait for Pinterest)

### Scenario A: Current Approach (CORRECTED Costs)

| Component | Volume | Unit Cost | Monthly Cost |
|-----------|--------|-----------|--------------|
| Unsplash + Pexels searches | ~600 | Free | $0 |
| Claude vision ranking | ~150 | ~$0.005 | ~$0.75 |
| gpt-image-1 (1024x1536, high) | ~30 | **$0.25** | **~$7.50** |
| gpt-image-1 retry (validation fail) | ~8 | **$0.25** | **~$2.00** |
| **Total** | | | **~$10.25/month** |

> The previous estimate of ~$3.79/month was based on $0.08/image. The actual cost at 1024x1536 + high quality is $0.25/image, making the AI fallback 3x more expensive than estimated.

### Scenario B: Optimized AI Providers

| Provider | Quality Tier | Unit Cost (1024x1536) | 30 images | Notes |
|----------|-------------|-----------|------------|-------|
| gpt-image-1 (current, high) | High | $0.25 | $7.50 | Overpaying |
| gpt-image-1 (medium) | Medium | ~$0.07 | $2.10 | Same model, lower quality setting |
| gpt-image-1.5 (medium) | Medium | ~$0.05 | $1.50 | Better quality than current at 1/5 the cost |
| gpt-image-1.5 (low) | Low | ~$0.013 | $0.39 | Cheapest decent OpenAI option |
| FLUX 2 Pro (Replicate) | Standard | ~$0.045 | $1.35 | Best photorealism; 1920x1080 ~$0.045 |
| Gemini 2.5 Flash (paid) | Standard | $0.039 | $1.17 | Cheap but max 1024x1024 |
| Gemini 2.5 Flash (batch) | Standard | $0.0195 | $0.59 | Cheapest AI option; 24hr delay; 1024x1024 max |
| Gemini 2.5 Flash (**free tier**) | Standard | **$0.00** | **$0.00** | If free tier works; see Section 7 |
| Imagen 4 Fast | Fast | $0.02 | $0.60 | Cheapest Google paid; quality may be low |
| Adobe Firefly | Standard | ~$0.02 | $0.60 | IP-safe |

### Scenario C: Recommended Hybrid (Upgraded)

| Component | Volume | Unit Cost | Monthly Cost |
|-----------|--------|-----------|--------------|
| Unsplash + Pexels (stock first) | ~120 | Free | $0 |
| Claude vision ranking | ~150 | ~$0.005 | ~$0.75 |
| FLUX 2 Pro fallback (primary AI) | ~25 | ~$0.045 | ~$1.13 |
| gpt-image-1.5 medium (secondary AI) | ~5 | ~$0.05 | ~$0.25 |
| AI regen (validation fail) | ~8 | ~$0.045 | ~$0.36 |
| **Total** | | | **~$2.49/month** |

**Savings vs current: ~$7.76/month (76% reduction) with better image quality.**

### Scenario D: Maximum Savings with Gemini Free Tier

| Component | Volume | Unit Cost | Monthly Cost |
|-----------|--------|-----------|--------------|
| Unsplash + Pexels (stock first) | ~120 | Free | $0 |
| Claude vision ranking | ~150 | ~$0.005 | ~$0.75 |
| Gemini 2.5 Flash (free tier, primary AI) | ~25 | $0.00 | $0.00 |
| gpt-image-1.5 medium (portrait fallback) | ~5 | ~$0.05 | ~$0.25 |
| AI regen | ~8 | $0.00 | $0.00 |
| **Total** | | | **~$1.00/month** |

**Requires:** Free tier to be available and stable for Gemini 2.5 Flash Image. See Section 7 for feasibility analysis. Portrait pins would need either upscaling from 1024x1024 or fallback to an OpenAI model that supports 1024x1536.

---

## 5. Quality Assessment for Overhead Food Photography

### Rankings for Top-Down/Overhead Food Imagery

Based on 2026 comparisons, food photography reviews, and benchmark data:

| Rank | Model | Food Quality | Overhead Food Notes |
|------|-------|-------------|---------------------|
| 1 | **FLUX 2 Max** | Excellent | "Most convincing product photography." Best material physics, lighting, textures. Excels at capturing food surfaces, garnishes, sauce drizzles from overhead angle. |
| 2 | **FLUX 2 Pro** | Excellent | "Often indistinguishable from professional photography." Sweet spot of quality + price for food pipelines. Overhead compositions look natural. |
| 3 | **GPT-Image-1.5 (high)** | Excellent | Best overall quality + text rendering. Very good at following "overhead shot" instructions. |
| 4 | **Midjourney** | Excellent | Best aesthetic quality for stylized food, but **no API = not viable.** |
| 5 | **Imagen 4 Ultra** | Very Good | 8/10 on food tests. Strong lighting and composition. |
| 6 | **GPT-Image-1.5 (medium)** | Good+ | Good balance of cost and quality for food content. |
| 7 | **Gemini 2.5 Flash** | Good | Strong reasoning produces coherent food scenes. Limited data on food-specific quality. Max 1024x1024. |
| 8 | **gpt-image-1 (current)** | Good | Decent but aging. Occasional artifacts on utensils/hands/garnishes. |
| 9 | **Adobe Firefly** | Good | Consistent but not as photorealistic. IP-safe advantage. |
| 10 | **Stable Image Ultra** | Moderate | Acceptable but not food-specialized. |

*Sources: [SideChef Comparison](https://www.sidechef.com/business/recipe-ai/comparison-of-ai-tools-for-food-photography), [MenuPhotoAI Guide](https://www.menuphotoai.com/guides/best-ai-food-photography-tools-2026), [WaveSpeed AI](https://wavespeed.ai/blog/posts/best-ai-image-generators-2026/)*

### Overhead/Flat-Lay Specific Considerations

Overhead food photography emphasizes shape over depth and flattens the 3D scene. This is actually **favorable for AI generation** because:
- No complex perspective/depth-of-field challenges
- No hands/utensils in frame (major failure mode avoided)
- Focus on color, texture, and arrangement (AI strengths)
- Consistent top-down lighting is easier to generate than complex angle-dependent lighting

**Key prompting for overhead food:**
- Include: "overhead shot," "flat lay," "top-down view," "bird's eye view"
- Be specific: cuisine type, specific ingredients visible, plating style, cooking vessel, surface material
- Specify lighting: "natural window light from the left," "soft diffused overhead"
- Mention surface: "rustic wood table," "marble countertop," "white linen"

### Common AI Food Photography Failure Modes
- **Hands and utensils:** Extra/missing fingers, impossible grips (mitigated by overhead angle)
- **Impossible food arrangements:** Items floating, physically impossible stacking
- **Uncanny textures:** "Plastic" looking food, overly smooth sauce surfaces
- **Lighting inconsistency:** Mixed shadow directions (worse at angles, less issue for overhead)
- **Wrong food identification:** AI generates wrong dish (especially with vague prompts)

---

## 6. Resolution Compatibility

Our pipeline needs 1024x1536 portrait images for Pinterest pins. Not all providers support this:

| Provider | Max Resolution | 1024x1536 Support | Workaround |
|----------|---------------|-------------------|------------|
| OpenAI GPT Image 1/1.5 | 1024x1536 | **Native** | N/A |
| OpenAI DALL-E 3 | 1024x1792 | **Native** (1024x1792) | N/A |
| Gemini 2.0/2.5 Flash | **1024x1024** | **No** | Would need upscaling or cropping from square |
| Imagen 4 | Varies by tier | Likely yes (Fast up to 2K) | Check API for aspect ratio support |
| FLUX 2 Pro | MP-based, flexible | **Yes** (custom aspect ratios) | Specify in request |
| Stability AI | Varies | Likely yes | Check model-specific limits |
| Adobe Firefly | Varies | Likely yes | Check API |

**Key finding:** Gemini Flash models are limited to 1024x1024 and **cannot natively produce our portrait format.** This is a significant limitation for our Pinterest use case. Using Gemini would require either:
1. Generating at 1024x1024 and upscaling/extending to 1024x1536 (adds complexity + potential quality loss)
2. Using Gemini only for square images (blog thumbnails, etc.) and a different provider for portrait pins
3. Accepting cropped/letterboxed output

---

## 7. Gemini Free Tier Feasibility

> **Full analysis:** See [research-gemini-free-tier-analysis.md](research-gemini-free-tier-analysis.md) for the complete deep-dive.

### Summary

The Gemini API free tier **can likely handle our workload** of ~5-7 images/day and batch runs of ~37 images/week. Key findings:

| Aspect | Finding |
|--------|---------|
| **Daily capacity** | 100-500+ RPD (our need: 5-37/day) — **well within limits** |
| **Rate limit** | ~2 IPM on free tier — batch of 37 takes ~19 min with spacing |
| **Production use** | **Allowed by TOS** — no "testing only" restriction |
| **Quality** | Identical to paid tier (same model, same weights) |
| **Cost** | $0.00 on free tier; $5.85/month on paid Tier 1 |
| **Data privacy** | Google trains on your prompts and images (free tier) |
| **SLA** | None on free tier |

### Critical Risks
1. **Model deprecation (IMMINENT):** Gemini 2.0 Flash retires March 3, 2026. If 2.5 Flash Image free tier isn't stable, free path may break.
2. **Quota cuts without notice:** Google cut free tier quotas 50-80% in December 2025.
3. **1024x1024 max resolution:** Cannot produce our 1024x1536 portrait format.

### Gemini Subscription ($19.99/month)
The Google AI Pro subscription does **NOT** directly cover API image generation. However, it includes $10/month in Google Cloud credits, which at $0.039/image covers ~256 images/month — more than our ~150/month need. This requires enabling Cloud Billing (Tier 1). See [research-gemini-subscription-coverage.md](research-gemini-subscription-coverage.md) for details.

### Recommendation
**Test the free tier now.** If `gemini-2.5-flash-image-preview` works without billing: use it for square images with retry logic. Budget for paid Tier 1 ($5.85/month) as fallback. Either way, build the pipeline to handle 429 errors gracefully so it works on both free and paid tiers without code changes.

---

## 8. Licensing and IP Considerations

### Free Stock (Unsplash + Pexels) — Low Risk
- Both provide irrevocable, worldwide, free commercial licenses
- No attribution legally required (Pexels) / encouraged but not required (Unsplash)
- Images are non-exclusive (available to everyone)

### AI-Generated Images — Moderate Risk
- **U.S. Copyright Office (2025):** Purely AI-generated images are not copyrightable
- **Commercial use:** Permitted by all major AI providers
- **No exclusivity:** Anyone can generate similar images
- **Adobe Firefly advantage:** Trained on licensed content only; commercial indemnification available
- **Pinterest policy:** No current restrictions against AI-generated content (subject to change)

### Gemini Free Tier — Data Training Consideration
When using Gemini's free tier, Google uses your prompts AND generated outputs for model training. Human reviewers may read your inputs and outputs. This means your brand strategy, prompt templates, and generated images are visible to Google. On paid Tier 1, Google does NOT train on your data.

### Recommendation
For our food photography use case, IP risk is low (food photos are generic/functional). If IP protection becomes a concern, prioritize Adobe Firefly (IP-safe training + indemnification) or switch to Gemini paid tier (no data training).

---

## 9. Recommendations

### Immediate Actions (Low Effort, High Impact)

1. **Fix the cost bug: Switch from `quality="high"` to `quality="medium"` for gpt-image-1.**
   - Effort: One-line change in `image_gen.py`
   - Cost impact: Drops from $0.25 to ~$0.07/image (**72% savings**)
   - Quality impact: Modest reduction; medium is still good for food photos
   - This alone saves ~$5.70/month at current volume

2. **Test Gemini 2.5 Flash Image on the free tier.**
   - Effort: Generate API key, make test requests
   - Cost: Free
   - Purpose: Determine if the free tier works and if 1024x1024 quality is acceptable
   - Limitation: Max 1024x1024 — only suitable for square images

3. **Apply for Unsplash Production rate limit (5,000 req/hr).**
   - Effort: Fill out application form
   - Cost: Free

### Medium-Term Actions (Moderate Effort)

4. **Add FLUX 2 Pro as the primary AI provider for food images.**
   - Effort: Update Replicate model ID (integration already exists)
   - Cost: ~$0.045/image at 1920x1080 (82% cheaper than current $0.25)
   - Quality: **Best photorealism for overhead food** — superior to gpt-image-1

5. **Upgrade OpenAI model to gpt-image-1.5 as secondary AI provider.**
   - Effort: Change model name string in `image_gen.py`
   - Cost: ~$0.05/image at medium quality + portrait (80% cheaper than current)
   - Quality: Significant improvement; best text rendering

6. **Add Gemini 2.5 Flash as a budget AI option (for square images/thumbnails).**
   - Effort: New API integration
   - Cost: $0.039/image (paid) or free
   - Use case: Blog thumbnails, square format pins, any image that doesn't need portrait aspect ratio

### Not Recommended

- **Midjourney:** No official API. Third-party wrappers violate ToS.
- **Shutterstock/Getty/Adobe Stock APIs:** $1-100+ per image. Not cost-effective.
- **Leonardo AI:** Complex credit system, no clear advantage.
- **Going AI-only:** Eliminating stock search would increase costs and lose the benefit of real photos.
- **DALL-E 3:** Superseded by GPT Image 1.5 in both quality and cost.

### Optimal Architecture

```
Stock Search Phase:
  Unsplash + Pexels (free) --> Claude vision ranks top 5 thumbnails

Quality Gate:
  Score >= 6.5 --> Use stock photo (free)
  Score < 6.5  --> Retry with broader query
  Retry < 5.0  --> Fall back to AI generation

AI Generation (Tier 2):
  Portrait pins (1024x1536):
    Primary:   FLUX 2 Pro via Replicate (~$0.045/image) -- best food photorealism
    Secondary: gpt-image-1.5 medium ($0.05/image) -- best text rendering

  Square images (1024x1024, blog thumbnails):
    Budget:    Gemini 2.5 Flash (free tier or $0.039/image)
    Fallback:  FLUX 2 Pro ($0.03/image at 1MP)

  Claude vision validates AI output:
    Score >= 6.5 --> Accept
    Score < 6.5  --> Regenerate with feedback (1 retry)
    Still < 6.5  --> Accept with low_confidence flag

Tier 3: Template-only (no image needed)
```

### Summary Table

| Approach | Monthly Cost | Image Quality | Integration Effort | Recommendation |
|----------|-------------|---------------|-------------------|----------------|
| Current (gpt-image-1 high, 1024x1536) | ~$10.25 | Good | Already done | **Overpaying** |
| Quick fix (gpt-image-1 medium) | ~$4.50 | Good | Trivial | Immediate win |
| Upgraded (FLUX 2 Pro + gpt-image-1.5) | ~$2.49 | Very Good | Low | **Recommended** |
| With Gemini free tier (square only) | ~$1.00 | Good-Very Good | Moderate | Best value if free tier holds |
| AI-only (gpt-image-1.5 medium) | ~$7.50 | Good+ | Minimal | Viable but unnecessary |
| Premium stock (Shutterstock) | $150-$450 | Excellent | Moderate | Not cost-effective |

---

*Research compiled from web sources including official pricing documentation from OpenAI, Google AI, Google Cloud Vertex AI, Black Forest Labs, Stability AI, Adobe, Ideogram, Recraft, Leonardo AI, Unsplash, and Pexels. All prices verified February 2026. See individual source links throughout and supplementary research files: [research-raw-findings.md](research-raw-findings.md), [research-gemini-free-tier-analysis.md](research-gemini-free-tier-analysis.md), [research-gemini-subscription-coverage.md](research-gemini-subscription-coverage.md).*
