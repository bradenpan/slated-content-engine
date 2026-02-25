# AI Image Generation API -- Raw Research Findings

Date: 2026-02-24

---

## 1. OpenAI Image Generation API

**Models Available:** GPT Image 1.5 (latest flagship), GPT Image 1, GPT Image 1 Mini, DALL-E 3 (previous gen), DALL-E 2 (legacy)

**GPT Image 1 Pricing (per image, 1024x1024 square):**
- Low quality: ~$0.02
- Medium quality: ~$0.07
- High quality: ~$0.19
- Resolutions: square (1024x1024), portrait (1024x1536), landscape (1536x1024)
- Full range: $0.011-$0.25 per image depending on quality + resolution

**GPT Image 1.5 Pricing:**
- Range: $0.009-$0.20 per image
- Cheaper than GPT Image 1, same quality tiers (low/medium/high) and resolutions

**GPT Image 1 Mini Pricing (per image, 1024x1024 square):**
- Low quality: $0.005
- Medium quality: $0.011
- High quality: $0.036
- Full range: $0.005-$0.052 per image
- 54-70% cheaper than full GPT Image 1

**DALL-E 3 Pricing:**
- Standard 1024x1024: $0.040 | Standard 1792x1024: $0.080
- HD 1024x1024: $0.080 | HD 1792x1024: $0.120

**DALL-E 2 Pricing (legacy):** 1024x1024: $0.020, 512x512: $0.018, 256x256: $0.016

**API Availability:** Public, fully available. Priced per token. Only charged for successful generations.

**Sources:**
- https://openai.com/api/pricing/
- https://platform.openai.com/docs/pricing
- https://costgoat.com/pricing/openai-images
- https://www.eesel.ai/blog/gpt-image-1-mini-pricing

---

## 2. Google Gemini 2.0 Flash Image Generation

- Image output: $30 per 1M output tokens
- Each output image (up to 1024x1024): 1290 tokens -> ~$0.039 per image
- Batch API: 50% discount -> $0.0195 per image
- Max resolution: 1024x1024
- Public via Gemini API, Google AI Studio, Vertex AI

**Sources:** https://ai.google.dev/gemini-api/docs/pricing

---

## 3. Google Gemini 2.5 Flash Image Generation

- Same pricing: $30 per 1M output tokens -> ~$0.039 per image (Batch: $0.0195)
- Native image gen model, character consistency, NL image editing, SynthID watermark
- Available via Gemini API, Google AI Studio, Vertex AI

**Sources:** https://developers.googleblog.com/en/introducing-gemini-2-5-flash-image/

---

## 4. Google Imagen (Vertex AI)

- Imagen 4 Fast: $0.02/image (cheapest Google option)
- Imagen 4 standard: $0.04/image
- Imagen 4 Ultra: $0.06/image
- Upscaling: $0.06/image
- Public via Vertex AI and Google AI Studio. Free tier with limitations.

**Sources:** https://cloud.google.com/vertex-ai/generative-ai/pricing

---

## 5. Flux on Replicate

- FLUX.1 schnell: $0.003/image
- FLUX.1 dev: $0.030/image
- FLUX.1 pro: $0.055/image

**Sources:** https://replicate.com/collections/flux, https://pricepertoken.com/image

---

## 6. Black Forest Labs Direct API

- 1 credit = $0.01 USD
- FLUX 1.1 Pro: $0.04/image (flat)
- FLUX 1.0 Pro: $0.05/image (flat)
- FLUX.2 Pro: ~$0.03 for first MP output, $0.015 each additional MP (1024x1024 = ~$0.03; 1920x1080 = ~$0.045)
- FLUX.2 Flex: $0.06 per MP (input + output)
- **Food photography:** FLUX 2 Max = "most convincing product photography." FLUX 2 Pro = "often indistinguishable from professional photography." Best for photorealism, lighting, textures.

**Sources:** https://bfl.ai/pricing, https://docs.bfl.ml/quick_start/pricing

---

## 7. Stability AI

- Stable Image Core: $0.03/image (3 credits)
- SD 3.5 Medium: $0.035/image (3.5 credits)
- SD 3.5 Large: $0.065/image (6.5 credits)
- Stable Image Ultra: $0.08/image (8 credits)
- $0.01/credit. Community license free for <$1M revenue. Enterprise license required above.
- Some older endpoints deprecated. Price increase Aug 2025.

**Sources:** https://platform.stability.ai/pricing, https://stability.ai/api-pricing-update-25

---

## 8. Adobe Firefly

- Firefly Services API: ~$0.02/image (pay-as-you-go), range $0.04-$0.12 depending on resolution
- Subscription: Standard $9.99/mo (2K credits), Pro $19.99/mo (4K), Premium $199.99/mo (50K)
- Enterprise licensing: $5K-$100K+/year
- Public via developer.adobe.com/firefly-services
- "Strong alternative" for artistic food imagery

**Sources:** https://developer.adobe.com/firefly-services/docs/firefly-api/, https://saascrmreview.com/adobe-firefly-pricing/

---

## 9. Midjourney

- **NO official API as of Feb 2026.** No REST endpoint, SDK, webhook, or API key system.
- Unofficial third-party APIs exist (ImagineAPI, APIFRAME, PiAPI) but violate TOS, risk account ban.
- Subscription only: Basic $10/mo, Standard $30/mo, Pro $60/mo, Mega $120/mo
- Best for stylized/"expensive-looking" food imagery, not literal photorealism

**Sources:** https://www.myarchitectai.com/blog/midjourney-apis, https://docs.midjourney.com/hc/en-us

---

## 10. Ideogram

- Ideogram V3 Turbo: $0.03/image
- Ideogram 3.0 standard: ~$0.06/image
- Ideogram V2: $0.08/image (Replicate/fal.ai)
- Character reference images billed at higher rates
- Character consistency (3.0), strong text rendering
- Public API with credit balance + auto-top-up

**Sources:** https://ideogram.ai/features/api-pricing, https://docs.ideogram.ai/plans-and-pricing/ideogram-api

---

## 11. Recraft AI

- Recraft V4 raster: $0.04/image (1024x1024, ~10 sec)
- Recraft V4 Pro raster: $0.08/image (2048x2048, ~30 sec)
- Recraft V4 vector: $0.04/image (~15 sec)
- Recraft V4 Pro vector: $0.25/image (~45 sec)
- Additional: vectorization, background removal, upscaling. Strong text rendering.
- Public at recraft.ai/api, also on Replicate

**Sources:** https://www.recraft.ai/pricing?tab=api, https://www.recraft.ai/blog/introducing-recraft-v4-design-taste-meets-image-generation

---

## 12. Leonardo AI

- Token/credit-based (not flat per-image). Each gen = 5-8 tokens.
- API Basic: $9/mo for 3,500 credits, up to 10 concurrent gens
- Manual top-ups: 5K credits = $15 (Basic), $11 (Standard), $8 (Pro)
- Estimated per-image: ~$0.026 at Basic tier. Varies by model/quality/resolution.
- Models: Phoenix 1.0/0.9, Alchemy, PhotoReal. Free tier: 150 tokens/day.
- Public at leonardo.ai/api

**Sources:** https://leonardo.ai/pricing, https://docs.leonardo.ai/docs/plan-with-the-pricing-calculator

---

## 13. Best AI for Food Photography (2026 Comparisons)

- **FLUX 2 Max/Pro:** "Most convincing product photography." Indistinguishable from real photos. Best photorealism.
- **Imagen 4:** Strong alternative, comparable photorealism, lower cost
- **Midjourney:** Best for stylized/"expensive-looking" food (but no API)
- **GPT Image 1/1.5:** Best instruction-following and text in images, decent photorealism
- **Realistic Vision V5.1** (SD fine-tune): "Excels at lifestyle photography... understands food photography conventions"
- **SideChef Studio:** Only tool specifically for food photography + recipe content
- **MenuPhotoAI:** Enhances real photos, not generation ($29 vs $600+ traditional)
- For pure photorealism: FLUX 2 Pro/Max or Imagen 4
- For budget: Imagen 4 Fast ($0.02) or FLUX.1 schnell ($0.003)

**Sources:** https://www.sidechef.com/business/recipe-ai/comparison-of-ai-tools-for-food-photography, https://www.menuphotoai.com/guides/best-ai-food-photography-tools-2026, https://wavespeed.ai/blog/posts/best-ai-image-generators-2026/

---

## 14. AI Overhead/Flat Lay Food Photography

- Limited AI-specific comparisons for overhead/flat lay specifically
- Overhead emphasizes shape, flattens depth -- not all food subjects work
- Key prompting: "overhead shot," "flat lay," "top-down view"
- Be specific: cuisine type, ingredients, plating, cooking method, lighting angle
- Prompt engineering is the biggest quality lever

**Sources:** https://www.productai.photo/blog/flat-lay-photography-complete-guide-to-creating-perfect-overhead-shots, https://www.a3logics.com/blog/ai-food-image-generator-tools/

---

## 15. Top-Down Food Photo AI Quality

- Overlaps with #13/#14. SideChef Studio top pick for recipe content.
- DALL-E 3: good control, no food-specific features
- Midjourney: artistic quality, not food-specialized
- SD: open-source, large training set including food
- Best results from highly specific/descriptive prompts

**Sources:** https://www.sidechef.com/business/recipe-ai/comparison-of-ai-tools-for-food-photography, https://minimaxir.com/2022/07/food-photography-ai/

---

## 16. Unsplash API

- **Completely FREE** -- no paid tiers
- Demo: 50 req/hr. Production (after approval): 5,000 req/hr
- Only JSON requests count; image file requests do not
- Can request higher limits. Must attribute photographers.

**Sources:** https://unsplash.com/documentation, https://unsplash.com/developers

---

## 17. Pexels API

- **Completely FREE** -- no paid tiers
- Default: 200 req/hr, 20,000 req/month
- Unlimited requests available free if eligible (email api@pexels.com)
- Must include Pexels attribution

**Sources:** https://www.pexels.com/api/documentation/, https://help.pexels.com/hc/en-us/articles/900005852323-How-do-I-get-unlimited-requests

---

## Quick-Reference Price Comparison (per image at ~1024x1024)

| Provider | Model | Price/Image | Notes |
|---|---|---|---|
| OpenAI | GPT Image 1 Mini (low) | $0.005 | Cheapest OpenAI |
| OpenAI | GPT Image 1 Mini (med) | $0.011 | |
| OpenAI | GPT Image 1 Mini (high) | $0.036 | |
| OpenAI | GPT Image 1.5 (low) | ~$0.009 | Latest flagship |
| OpenAI | GPT Image 1.5 (med) | ~$0.04 | |
| OpenAI | GPT Image 1.5 (high) | ~$0.20 | |
| OpenAI | GPT Image 1 (low) | ~$0.02 | |
| OpenAI | GPT Image 1 (med) | ~$0.07 | |
| OpenAI | GPT Image 1 (high) | ~$0.19 | |
| OpenAI | DALL-E 3 (standard) | $0.040 | Previous gen |
| OpenAI | DALL-E 3 (HD) | $0.080 | |
| Google | Gemini 2.5 Flash Image | $0.039 | Batch: $0.0195 |
| Google | Imagen 4 Fast | $0.020 | Cheapest Google |
| Google | Imagen 4 | $0.040 | |
| Google | Imagen 4 Ultra | $0.060 | |
| BFL | FLUX.1 schnell | $0.003 | Replicate, fast/low quality |
| BFL | FLUX.1 dev | $0.030 | Replicate |
| BFL | FLUX 1.1 Pro | $0.040 | Direct API |
| BFL | FLUX 2 Pro (1MP) | $0.030 | MP-based pricing |
| Stability | Stable Image Core | $0.030 | |
| Stability | SD 3.5 Large | $0.065 | |
| Stability | Stable Image Ultra | $0.080 | |
| Adobe | Firefly API | ~$0.02 | Pay-as-you-go |
| Midjourney | N/A | N/A | NO API available |
| Ideogram | V3 Turbo | $0.030 | |
| Ideogram | 3.0 standard | ~$0.060 | |
| Recraft | V4 raster | $0.040 | |
| Recraft | V4 Pro (2048) | $0.080 | |
| Leonardo | Phoenix (est.) | ~$0.026 | Credit-based, varies |
| Unsplash | Stock photos | FREE | 5,000 req/hr (prod) |
| Pexels | Stock photos | FREE | 200 req/hr default |

## Additional Context

### Gemini Subscription Coverage (from separate research)
- The $20/mo Google AI Pro subscription does NOT cover API image generation
- API usage is completely separate billing (pay-as-you-go)
- Free tier API: 2 images/minute, labeled "testing only"
- Vertex AI: Separate Google Cloud billing, $0.134/image (1K/2K) or $0.24/image (4K)
- AI Studio free tier daily quotas were slashed 50-80% in December 2025

### Resolution Limitation Note
- Gemini 2.0/2.5 Flash: Max 1024x1024 (does NOT support our 1024x1536 portrait format natively)
- OpenAI GPT Image models: Support 1024x1536 portrait natively
- Most other providers: Support custom resolutions up to ~2048x2048
