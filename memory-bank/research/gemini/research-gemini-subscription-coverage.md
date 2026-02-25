# Gemini Pro Subscription API Coverage — Research Findings

## Key Finding: Subscription Does NOT Cover API Image Generation

The $20/mo Google AI Pro subscription provides access to generative AI features within Google's consumer apps only (Gemini chat, Gmail, etc.). API image generation is completely separate billing on a pay-as-you-go basis.

### Details

**1. Does a $20/mo Gemini Pro subscription include API image generation?**
- **No.** The subscription covers consumer app usage only
- API image generation is completely separate billing (pay-as-you-go)
- The subscription does not cover or reduce API costs

**2. Google AI Studio free tier vs paid subscription for image gen?**
- **Free Tier API:** 2 images/minute maximum, testing only
- **Paid Subscription:** Includes 1,000 images/day within Gemini chat, but this is consumer app usage only — not API coverage

**3. Is Vertex AI image generation separate billing?**
- **Yes, absolutely separate.** Vertex AI requires Google Cloud billing and has no connection to the consumer subscription
- Pricing is identical to Gemini API ($0.039-$0.24 per image)

**4. Rate limits on image generation**
- **Free tier API:** 2 images/minute maximum
- **Tier 1 (billing enabled):** 150-300 RPM
- **Tier 2 ($250+ cumulative spend):** 1,000+ RPM

### Cost for our volume (~150 images/month)
- Gemini API: $0.039/image = ~$5.85/month (NOT covered by subscription)
- The free tier (2 images/min) is technically usable for our volume but is labeled "testing only"

### Sources
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Rate limits | Gemini API](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Use Google AI Pro benefits](https://support.google.com/googleone/answer/14534406?hl=en)
- [Google AI Studio Free Plans, Trials, and Subscriptions](https://www.datastudios.org/post/google-ai-studio-free-plans-trials-and-subscriptions-access-tiers-limits-and-upgrade-paths)
- [What Gemini features you get with Google AI Plus, Pro, & Ultra](https://9to5google.com/2026/02/21/google-ai-pro-ultra-features/)
