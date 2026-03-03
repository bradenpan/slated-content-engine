# 06 - Fully Automated Content Creation Pipeline: The Zero-Human-Filming Playbook

> **Date:** February 22, 2026
> **Purpose:** Design a FULLY AUTOMATED TikTok content creation pipeline -- zero human filming, zero manual editing, zero manual design. All content created programmatically.
> **Context:** Extends existing Pinterest pipeline (Claude AI + stock photos + DALL-E/Flux + Puppeteer). Product: Slated, family meal planning app.
> **Stance:** We WILL automate this. Full stop.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Faceless TikTok Playbook](#2-the-faceless-tiktok-playbook)
3. [Fully Automated Video Creation Pipeline](#3-fully-automated-video-creation-pipeline)
4. [Fully Automated Carousel Creation Pipeline](#4-fully-automated-carousel-creation-pipeline)
5. [Fully Automated Stitch/Duet Pipeline](#5-fully-automated-stitchduet-pipeline)
6. [Content Variety & Anti-Repetition System](#6-content-variety--anti-repetition-system)
7. [Recommended Full-Auto Architecture](#7-recommended-full-auto-architecture)
8. [Cost Model](#8-cost-model)
9. [Sources](#9-sources)

---

## 1. Executive Summary

The previous research (Reports 00-04) recommended a "hybrid" approach with human filming for some content. **This report overrides that recommendation.** The client wants full automation, and full automation is achievable.

**The key insight:** The previous team was right that AI-generated video (Sora, Runway) carries detection risk. But that is not the only path to zero-human-filming video. Thousands of successful faceless TikTok accounts prove that compelling content can be made from:

- Stock footage (hands chopping vegetables, top-down cooking shots, grocery aisles)
- Kinetic typography (animated text as the primary visual)
- Screen recordings (automated app demos)
- Photo slideshows with motion effects (Ken Burns, zoom, pan)
- Data visualizations and infographics
- AI voiceover narrating over all of the above

None of these require a human on camera. None trigger TikTok's AI content detection (they use real footage and template-based assembly). The Pinterest pipeline already proves that programmatic content creation works at scale for static images. Extending it to video is an engineering problem, not a creative impossibility.

**What this pipeline produces:**
- 3-4 fully automated videos per week (15-60 seconds each)
- 2-3 fully automated carousels per week (5-10 slides each)
- 1 automated "reaction-style" video per week (the Stitch/Duet alternative)
- Total: 6-8 pieces of content per week, zero human filming

**Estimated cost per piece:** $1.50-4.00 (automated production only)
**Estimated monthly production cost:** $40-130/month (excluding fixed subscriptions)

---

## 2. The Faceless TikTok Playbook

### 2.1 Why Faceless Works

The previous research team flagged that "accounts with a consistent human face dramatically outperform faceless accounts." This is true on average, but misleading for our context. Faceless accounts are thriving in specific niches -- and food/cooking is one of the strongest.

**Key data points:**
- Faceless YouTube channels and TikTok accounts now make up 38% of new creator monetization ventures in 2025
- Faceless content represented over 30% of viral videos across major platforms
- Demonstration videos showing just hands using products convert at 1.8x the rate of traditional face-based reviews
- Faceless videos reduce production costs by an average of 40% while delivering comparable engagement

### 2.2 Faceless Visual Styles That Work in Food/Cooking

| Style | Description | Automatable? | TikTok Performance | Example Use for Slated |
|-------|-------------|-------------|-------------------|----------------------|
| **Overhead hands-only** | Top-down camera angle showing hands preparing food | YES (stock footage) | Very High -- the dominant faceless food format | "5-minute dinner prep" using stock cooking footage |
| **Kinetic typography** | Animated text as primary visual, bold fonts, motion effects | YES (Remotion) | High -- extremely popular for tips/hacks content | "7 meals under $50 this week" with animated text |
| **Stock footage montage** | B-roll clips edited together with voiceover | YES (Pexels/Storyblocks + Remotion) | High -- indistinguishable from human-edited videos | "Grocery shopping hacks" over grocery store footage |
| **Screen recording + narration** | App demo with AI voiceover | YES (Playwright + ElevenLabs) | Medium-High -- works for tutorial/demo content | "How I plan my entire week in 2 minutes" |
| **Photo slideshow with motion** | Static images with Ken Burns effect, zoom, pan | YES (Remotion) | Medium -- good for recipe content | "This week's meal plan" with food photos |
| **Split-screen comparison** | Two things side by side (before/after, this vs that) | YES (Remotion) | High -- naturally drives comments and shares | "What I planned vs what I actually cooked" |
| **Data/infographic animation** | Charts, stats, numbers animating on screen | YES (Remotion) | Medium-High -- great for "did you know" content | "Average family wastes $1,500/year on food" |
| **Text-on-background** | Simple text slides with colored backgrounds | YES (Remotion) | Medium -- low effort, moderate performance | Quick tips, one-liners, quotes |
| **ASMR-style close-ups** | Extreme close-ups of food prep with enhanced audio | YES (stock footage + audio design) | High -- satisfying/loop-worthy | Chopping, sizzling, plating sounds |

### 2.3 Successful Faceless Food Account Patterns

**Pattern 1: "Recipe Card" Style**
- Hook text on screen (first 2 seconds)
- Overhead stock footage of food being prepared
- Ingredient list overlay
- Step-by-step text overlays synced with footage
- AI voiceover narrating steps
- Total duration: 30-45 seconds
- **Automation: 100%.** Claude writes script, Pexels provides footage, Remotion assembles, ElevenLabs voices.

**Pattern 2: "Tips & Hacks" Style**
- Bold hook text ("Stop wasting money on groceries")
- Kinetic typography with each tip animating on screen
- Stock footage B-roll playing behind text
- Fast pace, 3-5 tips in 15-30 seconds
- Background music, optional voiceover
- **Automation: 100%.** This is essentially the Pinterest template approach, but animated.

**Pattern 3: "Week in Review" Style**
- "What I cooked this week" format
- Photo slideshow with motion effects
- Each slide shows a different meal
- Text overlay with meal name and prep time
- AI voiceover: "Monday was chicken stir fry, only took 15 minutes..."
- **Automation: 100%.** Use actual Slated app data to generate content.

**Pattern 4: "Myth Busting / Did You Know" Style**
- Controversial or surprising claim as hook
- Data/stats animations proving the point
- Stock footage illustrating concepts
- Strong CTA ("Save this for your next grocery trip")
- **Automation: 100%.** Claude generates claims + data, Remotion animates.

**Pattern 5: "App Demo" Style**
- Problem statement hook ("Tired of 'what's for dinner?' every night?")
- Screen recording of app solving the problem
- AI voiceover walking through the flow
- End card with soft CTA
- **Automation: 100%.** Playwright records app demo, ElevenLabs narrates.

### 2.4 How Faceless Accounts Maintain Engagement

Faceless accounts compensate for the absence of a human face through:

1. **Distinctive voiceover**: A consistent AI voice becomes the "face" of the brand. Viewers recognize the voice, not a face.
2. **Strong visual branding**: Consistent color palette, font choices, text overlay style across all videos. Template-based production naturally creates this consistency.
3. **Value density**: Every second delivers information. No filler, no "hey guys," no setup. Pure value.
4. **Pattern hooks**: The first frame always has bold, attention-grabbing text. The viewer knows what they will get.
5. **Community engagement**: Active comment replies (this is the one human element we maintain).

---

## 3. Fully Automated Video Creation Pipeline

### 3.1 Architecture Overview

```
===========================================================================
                    FULLY AUTOMATED VIDEO PIPELINE
===========================================================================

                    +-------------------+
                    |   CONTENT PLAN    |
                    |   (from weekly    |
                    |    planning)      |
                    +--------+----------+
                             |
                    Content brief: topic, format,
                    target keyword, hook direction,
                    video style (from 9 styles above)
                             |
                    +--------v----------+
                    |   SCRIPT ENGINE   |
                    |   Claude API      |
                    +--------+----------+
                             |
                    Complete script with:
                    - Hook text (first 1-3s)
                    - Voiceover text (per-shot)
                    - Shot descriptions (for footage search)
                    - Text overlay cues
                    - SEO keyword placement
                    - CTA text
                             |
              +--------------+---------------+------------------+
              |              |               |                  |
     +--------v---+  +------v------+  +-----v--------+  +-----v--------+
     | VISUAL     |  | AUDIO       |  | TEXT/CAPTION  |  | MUSIC        |
     | ASSET      |  | ENGINE      |  | ENGINE        |  | ENGINE       |
     | ENGINE     |  |             |  |               |  |              |
     | (parallel) |  | (parallel)  |  | (parallel)    |  | (parallel)   |
     +--------+---+  +------+------+  +-----+---------+  +-----+--------+
              |              |               |                  |
              |         VO audio +      Caption data       Music track
              |         timestamps      (word-level)       (selected)
              |              |               |                  |
              +--------------+---------------+------------------+
                             |
                    +--------v-----------+
                    |    REMOTION        |
                    |    COMPOSITION     |
                    |                    |
                    |  React components: |
                    |  - Video layers    |
                    |  - Text overlays   |
                    |  - Animated caps   |
                    |  - Audio tracks    |
                    |  - Transitions     |
                    +--------+-----------+
                             |
                    +--------v-----------+
                    |   REMOTION LAMBDA  |
                    |   RENDER           |
                    |   -> MP4 (1080x1920)|
                    +--------+-----------+
                             |
                    +--------v-----------+
                    |   COVER FRAME      |
                    |   GENERATION       |
                    |   (Puppeteer)      |
                    +--------+-----------+
                             |
                    +--------v-----------+
                    |   METADATA         |
                    |   GENERATION       |
                    |   - Caption text   |
                    |   - Hashtags       |
                    |   - Cover image    |
                    +--------+-----------+
                             |
                    +--------v-----------+
                    |   HUMAN REVIEW     |
                    |   QUEUE            |
                    |   (Google Sheets)  |
                    +--------+-----------+
                             |
                    +--------v-----------+
                    |   POST TO TIKTOK   |
                    |   (Content Posting |
                    |    API)            |
                    +--------------------+

===========================================================================
```

### 3.2 Script Engine (Claude API)

**Input:** Content brief from weekly planning (topic, format style, target keyword, hook direction)

**Output:** Structured JSON script with shot-by-shot direction

**Script structure:**

```json
{
  "video_id": "v-2026-02-22-001",
  "style": "stock_footage_montage",
  "duration_target_seconds": 30,
  "hook": {
    "text_overlay": "Stop throwing away $1,500 a year",
    "voiceover": "The average American family throws away fifteen hundred dollars worth of food every single year.",
    "visual_direction": "Close-up of food being thrown in trash, then grocery store aisle",
    "duration_seconds": 4
  },
  "shots": [
    {
      "shot_number": 1,
      "duration_seconds": 5,
      "voiceover": "But here's the thing -- it's not because you buy too much.",
      "text_overlay": "It's not what you think",
      "visual_search_query": "person looking confused at refrigerator",
      "visual_style": "stock_footage"
    },
    {
      "shot_number": 2,
      "duration_seconds": 6,
      "voiceover": "It's because you don't have a plan. When you plan your meals for the week, you buy exactly what you need.",
      "text_overlay": "The fix: meal planning",
      "visual_search_query": "meal prep containers organized colorful food",
      "visual_style": "stock_footage"
    },
    {
      "shot_number": 3,
      "duration_seconds": 8,
      "voiceover": "I use Slated to plan all my family's meals in about two minutes. It even generates my grocery list automatically.",
      "text_overlay": null,
      "visual_search_query": null,
      "visual_style": "app_screen_recording",
      "screen_recording_flow": "open_app -> weekly_planner -> tap_generate -> show_grocery_list"
    },
    {
      "shot_number": 4,
      "duration_seconds": 5,
      "voiceover": "This week alone I saved over forty dollars just by knowing exactly what I needed.",
      "text_overlay": "Saved $40+ this week",
      "visual_search_query": "receipt savings grocery store happy family kitchen",
      "visual_style": "stock_footage"
    }
  ],
  "cta": {
    "text_overlay": "Link in bio for free trial",
    "voiceover": "Try it free. Link in my bio.",
    "duration_seconds": 3
  },
  "metadata": {
    "caption": "Stop wasting money on groceries you'll never use. Meal planning changed everything for our family. #mealplanning #savemoney #familymeals #groceryhacks #dinnerideas",
    "hashtags": ["mealplanning", "savemoney", "familymeals", "groceryhacks", "dinnerideas"],
    "target_keyword": "meal planning save money",
    "seo_keyword_spoken_in_first_5_seconds": true
  }
}
```

**Hook generation system:**

Claude generates hooks using a prompt template that includes:
- Hook formula library (10+ formulas: contrarian claim, question hook, surprise reveal, etc.)
- Previously used hooks (to avoid repetition)
- This week's target keywords
- Performance data from prior hooks (which formulas got highest completion rates)

The prompt rotates through hook formulas and ensures no formula is used more than twice per week.

**SEO keyword integration:**
- Target keyword spoken in voiceover within first 5 seconds (highest-impact SEO action per research)
- Target keyword in text overlay of first shot
- Target keyword in caption text
- 3-5 niche-relevant hashtags (not #fyp or #viral)

**CTA strategy:**
- Maximum 1 direct CTA ("link in bio") per 5 videos
- Other videos use soft CTAs: "Save this for later," "Follow for more meal prep tips," "Comment your favorite dinner idea"
- CTA placement: always final 2-3 seconds (never opens a video)

### 3.3 Visual Asset Engine

The visual asset engine operates in parallel based on the shot list from the script.

**Source 1: Stock Footage (Pexels Video API + Storyblocks API)**

```
Script shot: "Close-up of food being thrown in trash"
     |
     v
Search query generation (Claude extracts search terms)
     |
     v
Pexels Video API: GET /videos/search?query=food+waste+trash&orientation=portrait
     |
     v
Filter results:
  - Prefer vertical (9:16) or square (crop-friendly)
  - Minimum 720p resolution
  - Duration >= shot duration requirement
  - License: Creative Commons (Pexels) or Royalty-Free (Storyblocks)
     |
     v
Select best match (by relevance score)
     |
     v
Download video clip
     |
     v
FFmpeg: Trim to shot duration, crop to 1080x1920 if needed
     |
     v
Store in /assets/video/[video_id]/shot_[n].mp4
```

**Pexels Video API details:**
- Free API, no attribution required
- ~10,000+ food stock videos available
- API supports `orientation=portrait` parameter for vertical video
- Rate limit: 200 requests/hour (expandable for free if meeting API terms)
- Food-related queries return quality results: "meal prep," "chopping vegetables," "grocery store," "family dinner table," "kitchen cooking hands"

**Storyblocks API (fallback for premium footage):**
- Subscription: $20-65/month for API access
- Millions of clips including vertical video
- Food/cooking is a well-stocked category
- $100K indemnification on Business plan
- Use when Pexels quality is insufficient or clips feel repetitive

**Stock footage curation strategy:**
- Build a local library of 200-300 pre-vetted food/cooking clips
- Tag clips by theme: "cooking process," "ingredients," "grocery store," "family meal," "kitchen," "food waste," "meal prep containers"
- Script engine references tags, not raw search queries, for frequently-used shots
- Refresh library monthly with 50 new clips to prevent repetition

**Source 2: Automated Screen Recordings (Playwright)**

For app demo shots, Playwright automates the screen recording:

```
Script shot: "screen_recording_flow": "open_app -> weekly_planner -> tap_generate -> show_grocery_list"
     |
     v
Playwright script executes pre-written flow:
  - Launch browser at app URL
  - Set viewport to 390x844 (iPhone 14 dimensions)
  - Begin screen recording
  - Execute scripted user interactions:
    - page.click('#weekly-planner')
    - page.waitForSelector('.planner-view')
    - page.click('#generate-plan')
    - page.waitForSelector('.grocery-list')
    - page.scroll('.grocery-list', { distance: 300 })
  - End recording
     |
     v
Output: Raw WebM screen capture
     |
     v
FFmpeg post-processing:
  - Add device frame overlay (iPhone mockup)
  - Scale to fit within 1080x1920 safe zone
  - Convert WebM to MP4 (H.264)
  - Apply slight zoom-in animation for dynamism
     |
     v
Store in /assets/video/[video_id]/shot_[n]_screenrec.mp4
```

**Pre-built Playwright flows:**
- `weekly_planner_generation`: Open app -> Create weekly plan -> Show results
- `grocery_list_demo`: Open plan -> View grocery list -> Check off items
- `quick_dinner_search`: Open app -> Search recipes -> Filter by time -> Show results
- `family_preferences`: Open settings -> Set dietary preferences -> Show customized results
- `add_recipe`: Browse recipes -> Add to plan -> Show updated week
- `budget_tracker`: Open budget view -> Show weekly spending -> Compare to target

Each flow has 3-5 variations (different meals, different interactions) to prevent repetition. New flows are added as the app adds features.

**Source 3: AI-Generated Images (for specific shots)**

When neither stock footage nor screen recordings fit:
- DALL-E or Flux Pro generates specific images (infographics, custom illustrations)
- These images get Ken Burns effect (zoom/pan) in Remotion for motion
- **IMPORTANT:** If the AI-generated image looks photorealistic, it MUST be labeled as AI content. Prefer illustrated/stylized output to avoid the labeling requirement.
- Use sparingly (1-2 images per week maximum)

### 3.4 Audio Engine

**Voiceover generation (ElevenLabs API):**

```
Script voiceover text: "The average American family throws away fifteen hundred dollars worth of food every single year."
     |
     v
ElevenLabs API: POST /v1/text-to-speech/{voice_id}/with-timestamps
  Body: {
    "text": "The average American family throws away...",
    "model_id": "eleven_flash_v2_5",
    "voice_settings": {
      "stability": 0.65,
      "similarity_boost": 0.75,
      "style": 0.3,
      "use_speaker_boost": true
    }
  }
     |
     v
Response: {
  "audio_base64": "...",        // MP3 audio
  "alignment": {
    "characters": [...],
    "character_start_times_seconds": [...],
    "character_end_times_seconds": [...]
  },
  "normalized_alignment": {
    "chars": [...],
    "charStartTimesMs": [...],
    "charDurationsMs": [...]
  }
}
     |
     v
Parse word-level timestamps from character data
     |
     v
Store: /assets/audio/[video_id]/shot_[n]_vo.mp3
Store: /assets/audio/[video_id]/shot_[n]_timestamps.json
```

**Voice selection strategy:**
- Select 1 primary voice from ElevenLabs' stock voices (NOT a clone)
- The voice becomes the brand's audio identity
- Recommended: A warm, conversational female voice (matches the busy parent audience)
- Using stock voices (not clones) avoids the "AI-generated person" labeling requirement
- Test 3-5 voices with sample scripts before committing

**Voice consistency settings:**
- Lock `stability`, `similarity_boost`, and `style` parameters
- Use the same `voice_id` across all videos
- Store voice settings in config so they never drift

**Music selection and mixing:**

```
Video style + mood tag from script
     |
     v
Music library lookup:
  Pre-curated library of 30+ background tracks, tagged by:
  - Mood: upbeat, calm, inspiring, playful, serious
  - Tempo: slow, medium, fast
  - Style: acoustic, electronic, ambient, pop
     |
     v
Select track matching script mood
  (Rotate through tracks -- never use same track twice in one week)
     |
     v
FFmpeg audio mixing:
  ffmpeg -i voiceover.mp3 -i music.mp3 \
    -filter_complex "[1:a]volume=0.15[music];[0:a][music]amix=inputs=2:duration=first" \
    -ac 2 output_mixed.mp3
     |
     v
Result: Voiceover at 100% volume, music at 15% volume
Store: /assets/audio/[video_id]/mixed_audio.mp3
```

**Music sourcing options:**

| Source | Cost | API? | Quality | License Safety |
|--------|------|------|---------|----------------|
| Epidemic Sound | $19/mo commercial | No public API (download manually to library) | High | Very High -- official TikTok Sound Partner |
| Suno AI (generated) | ~$10-24/mo | Yes (REST API) | Good for background | High -- original generations are commercially licensed |
| Uppbeat | Free tier / $8.25/mo | Limited | Good | Medium -- requires attribution on free tier |
| Pixabay Music | Free | Via Pixabay API | Moderate | High -- free commercial use |

**Recommended approach:** Build a local music library of 30-50 tracks from Epidemic Sound (curated manually once per quarter). For variety, supplement with Suno-generated custom tracks via API (generate 5-10 new background tracks monthly from mood/style prompts). This gives us hundreds of unique audio combinations.

**Suno API integration for custom music:**

```
POST /api/v1/generate
{
  "prompt": "upbeat acoustic background music for cooking video, family friendly, 30 seconds",
  "model": "v5",
  "duration": 30,
  "instrumental": true
}
     |
     v
Response: { "audio_url": "https://...", "duration": 30 }
     |
     v
Download to /assets/music/suno_[hash].mp3
Tag with mood/style metadata for library
```

**Can trending TikTok sounds be programmatically identified and used?**

**Identification:** Partially yes.
- TikTok Creative Center shows trending sounds (no API, but can be manually reviewed weekly)
- Third-party APIs exist: Apify's TikTok Music Trend API, Soundcharts API for TikTok endpoints
- The unofficial `davidteather/TikTok-Api` Python package can access sound data
- RapidAPI offers TikTok Trending Data endpoints

**Usage:** Mostly no, for our pipeline.
- Trending sounds from the general library are off-limits for Business accounts (restricted to Commercial Music Library)
- Even on Creator accounts, trending sounds cannot be embedded via the Content Posting API -- they must be added in-app
- The Content Posting API requires audio to be embedded in the uploaded video file. TikTok's sound library is only accessible through the native editor
- **Verdict:** For a fully automated pipeline posting via API, we MUST use externally licensed music (Epidemic Sound, Suno, etc.) embedded in the MP4. Trending TikTok sounds are not compatible with API-based posting.

### 3.5 Caption/Subtitle Engine

**Word-level timestamps from ElevenLabs -> Remotion animated captions:**

```
ElevenLabs timestamps JSON (per shot)
     |
     v
Parse into word objects: [
  { word: "The", start: 0.0, end: 0.12 },
  { word: "average", start: 0.15, end: 0.48 },
  { word: "American", start: 0.51, end: 0.89 },
  ...
]
     |
     v
Feed into Remotion's createTikTokStyleCaptions():
  - combineTokensWithinMilliseconds: 800 (groups ~3-4 words per "page")
  - Font: Bold, white, with black outline/shadow
  - Highlight color: Brand accent (e.g., coral/orange for Slated)
  - Position: Lower third (above TikTok UI safe zone)
  - Animation: Word-by-word highlight as spoken
     |
     v
Remotion renders captions as React components, burned into video frames
```

**Caption styling options (rotate for variety):**

| Style | Description | Best For |
|-------|-------------|----------|
| **Classic CapCut** | White bold text, black outline, word-by-word highlight in yellow | Standard videos |
| **Minimal** | Small white text, lower third, no highlight | Aesthetic/food footage videos |
| **Bold Center** | Large centered text, 2-3 words at a time, fill animation | Kinetic typography videos |
| **Karaoke** | Word-by-word color change with bounce effect | Energetic/fast-paced videos |
| **Typewriter** | Letters appear one by one | Story/narrative videos |

### 3.6 Remotion Composition Engine

Remotion is the orchestration layer that assembles all assets into a final video.

**How it works:**

Each video style maps to a Remotion composition (React component):

```typescript
// Example: StockFootageMontage composition
export const StockFootageMontage: React.FC<{
  script: VideoScript;
  assets: AssetManifest;
}> = ({ script, assets }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      {/* Layer 1: Video clips (stock footage / screen recordings) */}
      {script.shots.map((shot, i) => (
        <Sequence
          key={i}
          from={shot.startFrame}
          durationInFrames={shot.durationFrames}
        >
          <VideoClip
            src={assets.videoClips[i]}
            style="cover"
            animation={shot.animation || 'kenBurns'}
          />

          {/* Layer 2: Text overlays */}
          {shot.textOverlay && (
            <AnimatedTextOverlay
              text={shot.textOverlay}
              position="center"
              animation="slideUp"
              style={script.textStyle}
            />
          )}
        </Sequence>
      ))}

      {/* Layer 3: TikTok-style animated captions */}
      <TikTokCaptions
        timestamps={assets.timestamps}
        style={script.captionStyle}
      />

      {/* Layer 4: Audio (voiceover + music mix) */}
      <Audio src={assets.mixedAudio} />

      {/* Layer 5: Cover frame CTA (last 3 seconds) */}
      <Sequence from={script.ctaStartFrame}>
        <CTAEndCard text={script.cta.textOverlay} />
      </Sequence>
    </AbsoluteFill>
  );
};
```

**Core Remotion compositions (templates):**

| Composition | Visual Style | Primary Use | Complexity |
|-------------|-------------|-------------|------------|
| `StockFootageMontage` | Stock clips with text overlays + VO | Tips, hacks, educational | Medium |
| `KineticTypography` | Animated text as primary visual, background video/color | Lists, quick tips, stats | Medium |
| `AppDemoNarrated` | Screen recording + device frame + VO | Product demos, tutorials | Low |
| `PhotoSlideshow` | Photos with Ken Burns + text overlays + VO | Weekly plans, recipe roundups | Low |
| `SplitScreenCompare` | Side-by-side comparison with text | Before/after, this vs that | Medium |
| `DataVisualization` | Animated charts/numbers + VO | Stats, savings, "did you know" | Medium |
| `RecipeCard` | Overhead food footage + ingredient overlay + step text | Recipes, meal prep | Medium |
| `QuickTipStack` | Rapid-fire text cards with transitions | 5-second tips, "3 things" | Low |
| `TextOnBackground` | Simple text on gradient/image background | Quick thoughts, hot takes | Very Low |

**Remotion Lambda rendering:**

```
Remotion composition + assets
     |
     v
remotion lambda render:
  - Region: us-east-1
  - RAM: 2048 MB
  - Timeout: 120 seconds
  - Output: MP4, H.264, 1080x1920, 30fps
  - Cost: ~$0.02-0.05 per render
     |
     v
Output: Final MP4 video
Store: /output/[video_id]/final.mp4
```

### 3.7 Cover Frame / Thumbnail Generation

TikTok uses the cover frame for the profile grid. A compelling cover frame drives profile visits -> follows.

```
Script hook text + brand template
     |
     v
Puppeteer (reuse Pinterest pipeline):
  - HTML/CSS template: 1080x1920
  - Bold hook text centered
  - Brand colors + logo watermark (subtle)
  - Food imagery background (from stock or AI)
     |
     v
Render to PNG
Store: /output/[video_id]/cover.png
```

This uses the exact same Puppeteer rendering pipeline from Pinterest, just with TikTok-optimized templates.

### 3.8 Caption Text & Metadata Generation

Claude generates the post caption alongside the script:

```
{
  "caption": "Stop wasting money on groceries you'll never use. Meal planning changed everything for our family. #mealplanning #savemoney #familymeals #groceryhacks #dinnerideas",
  "hashtags": ["mealplanning", "savemoney", "familymeals", "groceryhacks", "dinnerideas"],
  "target_keyword": "meal planning save money"
}
```

**Caption rules (enforced in Claude prompt):**
- Include target SEO keyword naturally in first sentence
- 3-5 niche-relevant hashtags (never #fyp, #viral, #foryou)
- Conversational tone, not corporate
- Include a "comment bait" question in 50% of captions ("What's your go-to weeknight dinner?")
- Max 1 direct CTA per 5 posts
- Total length: 100-300 characters (TikTok truncates after ~150, but full text is indexed for search)

### 3.9 Complete Video Pipeline Data Flow

**End-to-end for a single video:**

```
Step 1: Weekly planner outputs content brief (JSON)           ~$0.05-0.15 (Claude)
Step 2: Script engine generates full script (JSON)            ~$0.10-0.20 (Claude)
Step 3: Visual asset engine sources clips (parallel)          ~$0.00 (Pexels) or ~$0.50-1.50 (Storyblocks amortized)
Step 4: ElevenLabs generates VO + timestamps                  ~$0.02-0.05
Step 5: Music track selected from library                     ~$0.15-0.30 (amortized)
Step 6: FFmpeg mixes VO + music                               ~$0.00 (compute)
Step 7: Remotion composes all layers                          ~$0.00 (local compute)
Step 8: Remotion Lambda renders MP4                            ~$0.02-0.05
Step 9: Puppeteer generates cover frame                        ~$0.00 (compute)
Step 10: Claude generates caption + hashtags                   ~$0.02-0.05 (included in Step 2)
Step 11: Package uploaded to review queue                      ~$0.00
Step 12: Human reviews in Google Sheets (5-10 min)            ~$2.50-5.00 (human time)
Step 13: Post to TikTok via Content Posting API               ~$0.00

TOTAL AUTOMATED COST PER VIDEO: $0.36 - $2.50
TOTAL WITH HUMAN REVIEW: $2.86 - $7.50
```

---

## 4. Fully Automated Carousel Creation Pipeline

### 4.1 Architecture Overview

This is the simplest adaptation from the existing Pinterest pipeline. The core rendering engine (Puppeteer) is identical.

```
===========================================================================
                 FULLY AUTOMATED CAROUSEL PIPELINE
===========================================================================

                    +-------------------+
                    |   CONTENT PLAN    |
                    +--------+----------+
                             |
                    Content brief: topic, target keyword,
                    slide count (5-10), carousel style
                             |
                    +--------v----------+
                    |   SLIDE CONTENT   |
                    |   GENERATOR       |
                    |   (Claude API)    |
                    +--------+----------+
                             |
                    JSON: [
                      { slide: 1, type: "hook", headline: "...", subtext: "..." },
                      { slide: 2, type: "content", headline: "...", body: "...", image_query: "..." },
                      ...
                      { slide: N, type: "cta", headline: "...", cta_text: "..." }
                    ]
                             |
              +--------------+---------------+
              |              |               |
     +--------v---+  +------v------+  +-----v--------+
     | STOCK      |  | AI IMAGE    |  | APP          |
     | PHOTOS     |  | GEN         |  | SCREENSHOTS  |
     | (Pexels/   |  | (DALL-E/    |  | (Playwright) |
     | Unsplash)  |  | Flux Pro)   |  |              |
     +--------+---+  +------+------+  +-----+--------+
              |              |               |
              +--------------+---------------+
                             |
                    +--------v-----------+
                    |   PUPPETEER        |
                    |   SLIDE RENDERER   |
                    |                    |
                    |   HTML/CSS template|
                    |   + dynamic content|
                    |   -> PNG per slide |
                    |   (1080x1920)      |
                    +--------+-----------+
                             |
                    [slide_1.png, slide_2.png, ... slide_N.png]
                             |
                    +--------v-----------+
                    |   METADATA GEN     |
                    |   (Claude)         |
                    |   - Caption        |
                    |   - Hashtags       |
                    +--------+-----------+
                             |
                    +--------v-----------+
                    |   HUMAN REVIEW     |
                    +--------+-----------+
                             |
                    +--------v-----------+
                    |   POST TO TIKTOK   |
                    |   Content Posting  |
                    |   API (photo mode) |
                    +--------------------+

===========================================================================
```

### 4.2 Slide Content Generation

Claude generates complete slide content using structured output:

```json
{
  "carousel_id": "c-2026-02-22-001",
  "title": "7 Dinners Under $50 This Week",
  "slides": [
    {
      "slide_number": 1,
      "type": "hook",
      "headline": "7 Dinners Under $50",
      "subtext": "Feed your whole family for less",
      "background": "gradient_coral_to_orange",
      "image_query": null
    },
    {
      "slide_number": 2,
      "type": "content",
      "headline": "Monday: Sheet Pan Chicken",
      "body": "Chicken thighs + veggies on one pan. $6.50 total.",
      "image_query": "sheet pan chicken dinner overhead",
      "prep_time": "25 min"
    },
    {
      "slide_number": 3,
      "type": "content",
      "headline": "Tuesday: Pasta Primavera",
      "body": "Use whatever veggies are on sale. $4.80 total.",
      "image_query": "pasta primavera bowl colorful vegetables",
      "prep_time": "20 min"
    },
    // ... slides 4-7 (one dinner per slide)
    {
      "slide_number": 8,
      "type": "summary",
      "headline": "Total: $47.30",
      "body": "That's 7 dinners for a family of 4",
      "background": "gradient_coral_to_orange"
    },
    {
      "slide_number": 9,
      "type": "cta",
      "headline": "Want the full plan?",
      "cta_text": "Save this + follow for more",
      "secondary_text": "I use @slated_app to plan every week"
    }
  ],
  "metadata": {
    "caption": "7 dinners for under $50 this week. Every meal takes 30 min or less. Save this for your next grocery run! #mealplanning #budgetmeals #familydinner #cheapmeals #dinnerideas",
    "hashtags": ["mealplanning", "budgetmeals", "familydinner", "cheapmeals", "dinnerideas"]
  }
}
```

### 4.3 Multi-Slide Template System

**Changes from Pinterest templates:**

| Dimension | Pinterest Pin | TikTok Carousel Slide |
|-----------|--------------|----------------------|
| Aspect ratio | 1000x1500 (2:3) | 1080x1920 (9:16) |
| Content per image | Standalone (single pin) | Part of a sequence (slide N of M) |
| Text size | Medium (desktop + mobile viewing) | Large (mobile-only viewing) |
| Safe zone | Full bleed | Bottom 15-20% reserved for TikTok UI |
| CTA | "Click to read more" | "Save this" / "Follow for more" |
| Visual hierarchy | Image-heavy | Text-heavy with supporting image |

**Template categories:**

| Template | Slide Structure | Visual Style | Best For |
|----------|----------------|-------------|----------|
| `ListicleTemplate` | Hook + N content slides + CTA | Bold numbers, clean layout, food photo per slide | "7 meals," "5 tips," "3 hacks" |
| `StepByStepTemplate` | Hook + numbered steps + CTA | Step numbers prominent, process photos | Recipes, tutorials, how-tos |
| `ComparisonTemplate` | Hook + side-by-side slides + verdict + CTA | Split layout, checkmarks/X marks | "This vs That," "Myth vs Fact" |
| `QuoteCardTemplate` | Hook + quote slides + CTA | Large text, minimal imagery | Tips, advice, testimonials |
| `WeeklyPlanTemplate` | Hook + 7 day slides + summary + CTA | Calendar-style layout, food photos | "What we eat this week" |
| `DataDrivenTemplate` | Hook + stat slides + CTA | Big numbers, charts, icons | "Did you know" content |
| `AppFeatureTemplate` | Hook + feature slides + CTA | App screenshots, annotations | Product education |
| `BeforeAfterTemplate` | Hook + before + after + CTA | Dramatic visual contrast | Transformation content |

**Each template has 3-5 color scheme variants** to prevent visual repetition.

### 4.4 Rendering Pipeline (Puppeteer)

The rendering code is a direct adaptation of the existing Pinterest `pin_assembler.py`:

```python
# Pseudocode -- adapted from existing Pinterest pipeline
async def render_carousel(carousel_data, template_name):
    slides = []
    template = load_template(template_name)

    for slide_data in carousel_data['slides']:
        # Source image if needed
        if slide_data.get('image_query'):
            image = await pexels_api.search_photos(
                query=slide_data['image_query'],
                orientation='portrait',
                size='large'
            )
            slide_data['image_url'] = image.url

        # Render HTML with dynamic data
        html = template.render(slide_data)

        # Screenshot via Puppeteer at 1080x1920
        page = await browser.new_page()
        await page.set_viewport_size({'width': 1080, 'height': 1920})
        await page.set_content(html)
        screenshot = await page.screenshot({'type': 'png'})
        slides.append(screenshot)
        await page.close()

    return slides
```

**Key differences from Pinterest rendering:**
1. Viewport size: 1080x1920 instead of 1000x1500
2. Multi-slide output (list of PNGs) instead of single PNG
3. Safe zone padding at bottom (CSS `padding-bottom: 320px` to clear TikTok UI)
4. Larger text sizes (minimum 48px for body, 72px for headlines)
5. Slide numbering visible (e.g., "3/9" in corner)

### 4.5 Cost Per Carousel

| Component | Cost |
|-----------|------|
| Claude (slide content) | $0.05-0.15 |
| Stock photos (Pexels) | Free |
| Puppeteer rendering | Free (compute) |
| Claude (metadata) | $0.02-0.05 |
| Human review (5 min) | $2.50 (human time) |
| **Total automated** | **$0.07 - $0.20** |
| **Total with review** | **$2.57 - $2.70** |

Carousels are by far the cheapest content type. At 2-3 per week, the monthly carousel cost is essentially zero.

---

## 5. Fully Automated Stitch/Duet Pipeline

### 5.1 The Hard Truth About Stitches and Duets

**Can Stitches/Duets be created via the TikTok Content Posting API?**

**No.** After thorough research of the TikTok developer documentation:

- The Content Posting API supports posting **videos** and **photo carousels** only
- The API has parameters `disable_duet` and `disable_stitch` to control whether OTHER users can Stitch/Duet YOUR content
- But there is NO parameter or endpoint to CREATE a Stitch or Duet programmatically
- Stitches and Duets must be created within the TikTok app itself using its native video creation tools
- This is confirmed across all official documentation and third-party developer guides

**Can this be automated via mobile automation tools (Appium)?**

**Technically possible, but extremely risky:**
- Appium can automate TikTok's mobile app on real devices
- Users on BlackHatWorld report automating TikTok actions (account creation, posting) via Appium + UiAutomator
- However: TikTok detects emulators (comments are blocked), detects automation patterns, and aggressively penalizes bot-like behavior
- Real devices are required (emulators get detected)
- The detection avoidance engineering (random delays, human-like interactions, device fingerprint management) is substantial
- **Risk level: HIGH.** Account suspension or ban is a realistic outcome.
- **Verdict: NOT recommended** for a brand account where account loss is unacceptable

### 5.2 The Automated Alternative: "Reaction-Style" Videos

Since true Stitches cannot be automated via API, we create the same effect programmatically. A "reaction-style" video uses the same format as a Stitch but assembles it as a standard video:

**How a real Stitch works:**
1. 3-5 seconds of the original video plays
2. Your response video follows

**How our automated "reaction" works:**
1. We screen-record or download the target video (with permission/fair use)
2. We clip the relevant 3-5 seconds
3. We generate a response section (stock footage + AI voiceover)
4. We assemble both into a single MP4 via Remotion
5. We post as a standard video via the Content Posting API
6. Caption references the original creator: "@originalcreator made a great point about..."

**This is NOT a true Stitch** (it does not use TikTok's native Stitch feature), but it achieves the same content format and engagement pattern. Many creators already do this manually.

### 5.3 Automated Reaction Pipeline

```
===========================================================================
              AUTOMATED "REACTION-STYLE" VIDEO PIPELINE
===========================================================================

STEP 1: Source Video Identification (Weekly)
     |
     v
Claude analyzes trending content in niche (from manual trend review):
  - Which videos in #mealplanning, #familymeals are getting high engagement?
  - Which have Stitch-worthy claims or tips we can respond to?
  - Filter for: relevant to our niche, has engagement, offers "response opportunity"
     |
     v
Output: List of 2-3 candidate source videos per week

STEP 2: Source Video Acquisition
     |
     v
Option A: Screen-record the TikTok video via Playwright
  (Navigate to TikTok web -> find video -> record playback)
Option B: Download via TikTok API (if video is publicly available)
Option C: Use a clip from a pre-curated library of "response-worthy" content
     |
     v
FFmpeg: Trim to the relevant 3-5 second clip
Store: /assets/reaction/[video_id]/source_clip.mp4

STEP 3: Response Script Generation
     |
     v
Claude generates response script:
  Input: Source video description + our brand context + content pillar
  Output: {
    "intro": "They said meal planning takes too long. Here's my take.",
    "response_voiceover": "Actually, with the right tool, meal planning takes about two minutes. I literally plan my entire week's dinners while my coffee brews.",
    "text_overlays": ["My take:", "2 minutes. That's it.", "Here's proof:"],
    "visual_direction": "screen recording showing fast meal plan generation",
    "outro": "What do you think? Drop your meal planning time in the comments."
  }

STEP 4: Response Visual + Audio Generation
     |
     v
Same pipeline as standard video:
  - ElevenLabs -> voiceover + timestamps
  - Stock footage / screen recording -> visual assets
  - Music selection -> background track

STEP 5: Assembly (Remotion)
     |
     v
ReactionStyleComposition:
  Sequence 1 (0-5s): Source clip plays with "split screen" or "picture in picture" effect
    - Text overlay: "They said:" or "@creator said:"
  Transition: Quick cut or wipe
  Sequence 2 (5-30s): Our response with VO + visuals + captions
  Sequence 3 (last 3s): CTA end card
     |
     v
Remotion Lambda render -> MP4

STEP 6: Metadata
     |
     v
Caption: "Responding to @originalcreator's meal planning take. Here's why it doesn't have to take forever. #mealplanning #mealprepideas #dinnerideas"
Note: Always credit the original creator in the caption. This is good practice AND drives engagement (original creator often responds).

===========================================================================
```

### 5.4 "Comment Reply" Videos

Another Stitch-alternative that is fully automatable:

**How it works on TikTok:** A creator takes a comment from one of their videos and creates a new video responding to it. The comment appears as an overlay on the response video. This format has built-in social proof and typically high engagement.

**Our automated version:**

```
Step 1: Monitor comments on our videos (via Display API or NapoleonCat)
Step 2: Claude identifies "good response opportunity" comments
  - Questions: "How do you plan for picky eaters?"
  - Challenges: "Meal planning never works for me"
  - Requests: "Can you do a budget version?"
Step 3: Claude generates response script
Step 4: Standard video pipeline creates the response
Step 5: Remotion adds the comment screenshot as an overlay in the first 3 seconds
Step 6: Post as standard video
Step 7: Reply to the original comment with "Just made a video about this!"
```

**Comment overlay rendering:**
- Screenshot the comment text (or recreate it using our own HTML/CSS template styled to look like a TikTok comment)
- Overlay in top-left corner for first 3-5 seconds
- Adds social proof and context for why the video exists

### 5.5 Stitch/Duet Alternative Content Mix

| Content Type | True Feature? | API-Postable? | Frequency | Automation Level |
|-------------|--------------|---------------|-----------|-----------------|
| Standard video | N/A | Yes | 3-4/week | 100% automated |
| Photo carousel | N/A | Yes | 2-3/week | 100% automated |
| Reaction-style video (Stitch alternative) | No (looks like one) | Yes | 1/week | 90% automated (source selection is semi-manual) |
| Comment reply video | No (recreated) | Yes | 1/week | 85% automated (comment selection is semi-manual) |
| True Stitch/Duet | Yes (native TikTok) | NO | 0-1/month | 0% automated (manual creation via app) |

**Recommendation:** True Stitches/Duets should be created manually via the TikTok app 1-2 times per month as a supplement. The automated pipeline handles the other 90%+ of content. The reaction-style and comment-reply formats achieve similar engagement patterns without requiring native feature usage.

---

## 6. Content Variety & Anti-Repetition System

### 6.1 The Repetition Problem

The fastest way to kill a faceless TikTok account is making every video look and sound the same. Template-based production naturally trends toward sameness unless variety is engineered in.

### 6.2 Template Rotation System

**Minimum template inventory:**

| Content Type | Minimum Templates | Rotation Rule |
|-------------|-------------------|---------------|
| Stock footage montage | 5 variations | No same template within 3 days |
| Kinetic typography | 4 variations | No same template within 3 days |
| App demo narrated | 3 variations | No same flow within 2 weeks |
| Photo slideshow | 3 variations | Alternate with other video styles |
| Split-screen compare | 2 variations | Max 1 per week |
| Data visualization | 2 variations | Max 1 per week |
| Recipe card | 3 variations | Max 2 per week |
| Quick tip stack | 2 variations | Max 1 per week |
| Carousel: Listicle | 4 color variants | Rotate colors weekly |
| Carousel: Step-by-step | 3 color variants | Rotate colors weekly |
| Carousel: Comparison | 2 color variants | Max 1 per week |
| Carousel: Weekly plan | 3 color variants | 1 per week (series) |
| Reaction-style | 2 layout variants | Max 1 per week |

**Total base templates needed: ~36** (24 video + 12 carousel)
**With color/style variants: ~80-100** unique visual presentations

### 6.3 Dynamic Element Randomization

Each video render randomizes within constrained parameters:

```json
{
  "randomization_config": {
    "text_overlay": {
      "font_family": ["Montserrat Bold", "Poppins Bold", "Inter Bold"],
      "text_color": ["#FFFFFF", "#FFF3E0", "#E8F5E9"],
      "highlight_color": ["#FF6B35", "#FF4081", "#7C4DFF", "#00BCD4"],
      "shadow_style": ["drop_shadow", "outline", "glow"],
      "position_variance_px": 20
    },
    "transitions": {
      "between_shots": ["cut", "fade", "slide_left", "slide_up", "zoom"],
      "text_entrance": ["fade_in", "slide_up", "scale_up", "typewriter"],
      "text_exit": ["fade_out", "slide_down", "scale_down"]
    },
    "caption_style": ["classic_capcut", "minimal", "bold_center", "karaoke"],
    "music_track": "rotate_from_library_no_repeat_within_week",
    "color_scheme": "rotate_from_palette_no_repeat_within_3_days",
    "shot_timing": {
      "variance_seconds": 0.5,
      "note": "Each shot's duration varies +/- 0.5s from script target"
    }
  }
}
```

**What this achieves:** Even when two videos use the same base template, the font, colors, transitions, caption style, music, and timing all differ. A viewer would not recognize them as "the same template."

### 6.4 Content Pillar Rotation

Content pillars ensure topical variety while maintaining niche consistency:

| Pillar | Content Themes | % of Mix |
|--------|---------------|----------|
| **Quick Meals** | Fast dinner ideas, 15-minute meals, weeknight solutions | 25% |
| **Budget Hacks** | Grocery savings, meal cost breakdowns, bulk buying tips | 20% |
| **Meal Prep** | Sunday prep, batch cooking, freezer meals, container organization | 20% |
| **Family Life** | Picky eaters, kid-friendly meals, family table moments | 15% |
| **App Features** | Product demos, feature walkthroughs, "how I use Slated" | 10% |
| **Food Knowledge** | Nutrition tips, food storage, seasonal ingredients, food waste | 10% |

The weekly planner ensures no pillar exceeds 40% of that week's content and no pillar drops below its target for two consecutive weeks.

### 6.5 A/B Testing Framework

**What to test:**
1. **Hook formulas**: Question hook vs contrarian claim vs surprise reveal
2. **Video length**: 15s vs 30s vs 45s for similar content
3. **Visual style**: Stock footage montage vs kinetic typography for same topic
4. **Caption style**: Classic CapCut vs minimal vs bold center
5. **CTA type**: "Save this" vs "Follow for more" vs no CTA
6. **Music mood**: Upbeat vs calm for same content

**How to test:**
- Each week, designate 1-2 pieces of content as A/B tests
- Create two versions of the same content with one variable changed
- Post version A on Monday, version B on Wednesday (or vice versa)
- Track completion rate, saves, shares, comments for each
- After 48 hours, declare a winner and feed the result back into the planning engine

**Automated A/B test tracking:**

```python
# Pseudocode
def log_ab_test(test_id, variable, variant_a_id, variant_b_id):
    sheets_api.write_row('AB_Tests', {
        'test_id': test_id,
        'variable_tested': variable,     # e.g., "hook_formula"
        'variant_a': variant_a_id,       # video ID
        'variant_b': variant_b_id,       # video ID
        'variant_a_data': None,          # filled after 48hrs
        'variant_b_data': None,          # filled after 48hrs
        'winner': None,                  # filled after 48hrs
        'date': datetime.now()
    })

def evaluate_ab_test(test_id):
    a_data = tiktok_api.get_video_stats(test.variant_a)
    b_data = tiktok_api.get_video_stats(test.variant_b)

    # Primary metric: completion rate
    # Secondary: saves + shares
    winner = 'A' if (
        a_data.completion_rate > b_data.completion_rate
        and a_data.saves + a_data.shares >= b_data.saves + b_data.shares
    ) else 'B'

    sheets_api.update_row('AB_Tests', test_id, {
        'variant_a_data': a_data,
        'variant_b_data': b_data,
        'winner': winner
    })

    # Feed back into planning engine
    update_performance_priors(test.variable_tested, winner)
```

### 6.6 Template Refresh Cadence

| Action | Frequency | Effort |
|--------|-----------|--------|
| Add 2-3 new color scheme variants | Monthly | 2-4 hours |
| Add 1 new video composition template | Monthly | 4-8 hours |
| Add 1 new carousel template | Monthly | 2-4 hours |
| Refresh stock footage library (50 clips) | Monthly | 2-3 hours |
| Generate new Suno background tracks (10) | Monthly | 1 hour (automated) |
| Review A/B test results and update priors | Weekly | 30 minutes |
| Retire underperforming templates | Quarterly | 2-3 hours |

---

## 7. Recommended Full-Auto Architecture

### 7.1 Complete System Architecture

```
=====================================================================
         SLATED TIKTOK: FULLY AUTOMATED CONTENT FACTORY
=====================================================================

┌─────────────────────────────────────────────────────────────────────┐
│                         WEEKLY PLANNING                             │
│                                                                     │
│  Monday Morning (automated, GitHub Actions cron):                   │
│                                                                     │
│  pull_tiktok_analytics.py                                          │
│    └── TikTok Display API -> Google Sheets + content-log.jsonl     │
│                                                                     │
│  generate_weekly_plan.py (adapted from Pinterest)                   │
│    ├── Read: strategy docs, content log, prior performance          │
│    ├── Read: A/B test results, template rotation state              │
│    ├── Claude API -> Generate 6-8 content briefs                    │
│    │   ├── 3-4 videos (mixed styles)                                │
│    │   ├── 2-3 carousels (mixed templates)                          │
│    │   └── 1 reaction-style video                                   │
│    └── Write: plan to Google Sheets "TikTok Weekly Plan" tab        │
│                                                                     │
│  slack_notify.py -> "TikTok plan ready for review"                  │
│                                                                     │
│  [HUMAN: Reviews plan in Sheets, approves/adjusts. ~15 min]        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CONTENT CREATION                               │
│                                                                     │
│  Monday-Tuesday (automated, triggered after plan approval):         │
│                                                                     │
│  generate_tiktok_content.py                                        │
│    │                                                                │
│    ├── FOR EACH VIDEO in plan:                                      │
│    │   ├── Claude API -> Generate complete script (JSON)            │
│    │   ├── [parallel]                                               │
│    │   │   ├── ElevenLabs API -> VO audio + word timestamps         │
│    │   │   ├── Pexels/Storyblocks API -> Stock footage clips        │
│    │   │   ├── Playwright -> Screen recordings (if app demo)        │
│    │   │   └── Music library -> Select background track             │
│    │   ├── FFmpeg -> Mix VO + music (15% volume)                    │
│    │   ├── Remotion compose -> React composition from template      │
│    │   ├── Remotion Lambda -> Render MP4 (1080x1920, H.264)        │
│    │   ├── Puppeteer -> Render cover frame (PNG)                    │
│    │   └── Upload to Google Drive + write to Sheets queue           │
│    │                                                                │
│    ├── FOR EACH CAROUSEL in plan:                                   │
│    │   ├── Claude API -> Generate slide content (JSON)              │
│    │   ├── Pexels/Unsplash API -> Stock photos per slide            │
│    │   ├── Puppeteer -> Render slides (1080x1920 PNG each)          │
│    │   └── Upload to Google Drive + write to Sheets queue           │
│    │                                                                │
│    └── FOR REACTION VIDEO:                                          │
│        ├── Source clip identified (semi-manual or from trend scan)  │
│        ├── Claude API -> Generate response script                   │
│        ├── Standard video pipeline (VO + visuals + assembly)        │
│        ├── Remotion -> Assemble source clip + response              │
│        └── Upload to Google Drive + write to Sheets queue           │
│                                                                     │
│  slack_notify.py -> "Content batch ready for review"                │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       REVIEW & APPROVAL                             │
│                                                                     │
│  Tuesday-Wednesday:                                                 │
│                                                                     │
│  [HUMAN: Reviews content in Google Sheets. ~5-10 min per piece.    │
│   Watches video preview in Drive, reads caption, checks hashtags.   │
│   Approves, requests changes, or rejects. Total: ~45-60 min/week] │
│                                                                     │
│  For rejected content:                                              │
│    regen_tiktok_content.py -> Regenerate with notes                │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     POSTING & SCHEDULING                            │
│                                                                     │
│  Wednesday-Sunday (automated, GitHub Actions cron with jitter):     │
│                                                                     │
│  post_tiktok.py (adapted from post_pins.py)                        │
│    ├── Read approved content from Sheets queue                      │
│    ├── Post via TikTok Content Posting API                          │
│    │   ├── Video: chunk upload MP4 -> direct_post                   │
│    │   ├── Carousel: upload PNGs -> photo_post                      │
│    │   └── Jitter: +/- 30 min from scheduled time                  │
│    ├── Fallback: Buffer API if TikTok API fails                     │
│    ├── Log to "TikTok Post Log" tab in Sheets                      │
│    └── slack_notify.py -> "Post live! Engagement window open"       │
│                                                                     │
│  [HUMAN: 20-30 min post-publish engagement per post]               │
│  [HUMAN: 20 min daily community engagement]                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ANALYTICS & OPTIMIZATION                         │
│                                                                     │
│  Weekly (Friday, automated):                                        │
│                                                                     │
│  weekly_tiktok_analysis.py                                         │
│    ├── Pull video metrics from Display API                          │
│    ├── Evaluate A/B test results                                    │
│    ├── Claude analysis -> Weekly performance report                  │
│    ├── Update content-log.jsonl with performance data               │
│    └── Feed insights into next week's planning                      │
│                                                                     │
│  Monthly:                                                           │
│                                                                     │
│  monthly_tiktok_review.py                                          │
│    ├── Full performance review                                      │
│    ├── Template performance analysis (which templates work best?)   │
│    ├── Content pillar performance analysis                          │
│    ├── A/B testing summary and prior updates                        │
│    └── Strategy recommendations for next month                      │
└─────────────────────────────────────────────────────────────────────┘
=====================================================================
```

### 7.2 Tool Chain Summary

| Function | Tool | Cost | Reuse from Pinterest |
|----------|------|------|---------------------|
| **Content planning** | Claude API (Sonnet) | $10-30/mo | 80% reuse |
| **Script generation** | Claude API (Sonnet) | Included above | New prompts |
| **Voiceover** | ElevenLabs API | $5-22/mo | New |
| **Stock video** | Pexels Video API | Free | 80% reuse (add video search) |
| **Stock video (premium)** | Storyblocks API | $20-65/mo (optional) | New |
| **Stock photos** | Pexels/Unsplash API | Free | 100% reuse |
| **Screen recording** | Playwright | Free | New scripts, same tool |
| **AI images** | DALL-E / Flux Pro | $5-15/mo (occasional) | 90% reuse |
| **Background music** | Epidemic Sound + Suno API | $19/mo + $10/mo | New |
| **Audio mixing** | FFmpeg | Free | New |
| **Video composition** | Remotion (React) | $100/mo (Automators) | New |
| **Video rendering** | Remotion Lambda (AWS) | $5-15/mo | New |
| **Carousel rendering** | Puppeteer | Free | 100% reuse |
| **Cover frames** | Puppeteer | Free | 90% reuse |
| **Caption generation** | Remotion createTikTokStyleCaptions() | Free (part of Remotion) | New |
| **Posting** | TikTok Content Posting API | Free | New (adapted posting logic) |
| **Posting fallback** | Buffer | $5/mo | New |
| **Approval workflow** | Google Sheets | Free | 85% reuse |
| **Notifications** | Slack webhooks | Free | 95% reuse |
| **Orchestration** | GitHub Actions | $5-10/mo | 100% reuse |
| **Analytics** | TikTok Display API + Claude | $5-15/mo | 70% reuse |
| **Comment management** | NapoleonCat | $31/mo | New |

### 7.3 Data Flow Diagram

```
                    EXTERNAL SERVICES
                    ─────────────────
                    Claude API ←──────────── Strategy docs + content log
                        │
                        ▼
                    Weekly plan (JSON)
                        │
            ┌───────────┼───────────────┐
            ▼           ▼               ▼
        ElevenLabs   Pexels/SB      Playwright
        (voice)      (footage)      (screen rec)
            │           │               │
            ▼           ▼               ▼
        ┌───────────────────────────────┐
        │         LOCAL ASSETS          │
        │   /assets/audio/              │
        │   /assets/video/              │
        │   /assets/screenshots/        │
        │   /assets/music/              │
        └──────────┬────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │    REMOTION (local)  │
        │    Compose scenes    │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  REMOTION LAMBDA     │
        │  Render MP4          │  ←──── Puppeteer (carousel PNGs)
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  GOOGLE DRIVE        │
        │  (asset storage)     │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  GOOGLE SHEETS       │  ←──── Human review here
        │  (approval queue)    │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  TIKTOK CONTENT      │
        │  POSTING API         │  ──── Fallback: Buffer API
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  TIKTOK DISPLAY API  │
        │  (analytics pull)    │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  CONTENT LOG         │  ──── Feeds back into weekly planning
        │  (content-log.jsonl) │
        └──────────────────────┘
```

### 7.4 Weekly Human Time Budget

| Activity | Time | Frequency | Weekly Total |
|----------|------|-----------|-------------|
| Review weekly plan | 15 min | 1x/week | 15 min |
| Review content batch | 45-60 min | 1x/week | 60 min |
| Post-publish engagement | 20-30 min | 6-8x/week | 150-210 min |
| Daily community engagement | 20 min | 7x/week | 140 min |
| Trend scan (source video selection) | 15 min | 1x/week | 15 min |
| **Weekly total** | | | **6.3-7.3 hours/week** |

**Critical note:** The post-publish engagement and community engagement are the irreducible human elements. These cannot be automated without risking account penalties. Everything else in the pipeline is automated.

**What was automated away:**
- Scripting: 0 hours (was ~2-4 hours/week)
- Filming: 0 hours (was ~3-5 hours/week)
- Editing: 0 hours (was ~3-5 hours/week)
- Design: 0 hours (was ~2-3 hours/week)
- Caption writing: 0 hours (was ~1-2 hours/week)
- **Total saved: ~11-19 hours/week**

---

## 8. Cost Model

### 8.1 Fixed Monthly Costs

| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| Remotion Automators license | $100 | Minimum for automated rendering |
| NapoleonCat | $31 | Comment management |
| Epidemic Sound | $19 | Music library (commercial license) |
| ElevenLabs Starter | $5 | 30K chars/mo (enough for 40+ videos) |
| Suno AI | $10 | Custom background music generation |
| Buffer | $5 | Backup posting |
| AWS Lambda (Remotion rendering) | $5-15 | ~7 videos/week rendering |
| GitHub Actions | $5-10 | Workflow compute |
| Claude API | $15-30 | Planning, scripting, analysis |
| Storyblocks (optional) | $20-65 | Premium stock footage (if Pexels insufficient) |
| **Total without Storyblocks** | **$195-225/mo** | |
| **Total with Storyblocks** | **$215-290/mo** | |

### 8.2 Variable Cost Per Piece

| Content Type | Automated Cost | Human Review Cost | Total Per Piece |
|-------------|---------------|-------------------|-----------------|
| Video (stock footage montage) | $0.50-2.50 | $2.50-5.00 | $3.00-7.50 |
| Video (kinetic typography) | $0.30-1.00 | $2.50-5.00 | $2.80-6.00 |
| Video (app demo) | $0.25-0.75 | $2.50-5.00 | $2.75-5.75 |
| Video (reaction-style) | $0.50-2.00 | $2.50-5.00 | $3.00-7.00 |
| Carousel | $0.07-0.20 | $2.50-5.00 | $2.57-5.20 |

### 8.3 Monthly Production Budget (7 pieces/week)

| Component | Quantity | Monthly Cost |
|-----------|---------|-------------|
| Videos | 16/month | $12-40 (automated) |
| Carousels | 12/month | $1-3 (automated) |
| **Variable production total** | 28/month | **$13-43** |
| **Fixed services** | | **$195-290** |
| **TOTAL MONTHLY** | | **$208-333** |

### 8.4 Comparison: Full Automation vs Alternatives

| Approach | Monthly Cost | Human Hours/Week | Content Quality | Scalability |
|----------|-------------|-----------------|----------------|-------------|
| **Full automation (this pipeline)** | $208-333 | 6-7 hrs (review + engagement) | Good-High | Unlimited |
| Freelance creator (filming + editing) | $1,500-3,000 | 2-3 hrs (review) | High | Limited by person |
| SaaS-only (Argil + tools) | $400-600 | 3-4 hrs (review + engagement) | Medium | Medium |
| In-house hire (part-time) | $2,000-4,000 | 0 hrs (they do it all) | High | Limited by person |
| Hybrid (auto + some human filming) | $250-400 | 8-10 hrs (filming + engagement) | Higher | Medium |

**The full automation pipeline is 5-10x cheaper than hiring or outsourcing**, with comparable content quality and superior scalability. The trade-off is the absence of a human face, which caps viral potential but delivers consistent, reliable content output.

---

## 9. Sources

### Faceless TikTok Accounts & Strategy
- [Whop - 30 Faceless TikTok Ideas to Make You Rich in 2026](https://whop.com/blog/faceless-tiktok-ideas/)
- [Zebracat - Best TikTok Faceless Niches 2025](https://www.zebracat.ai/post/best-tiktok-faceless-niches)
- [Virlo - 35 Best Faceless TikTok Niches to Go Viral](https://virlo.ai/blog/best-faceless-tiktok-niches)
- [VidBoard - Can Faceless Videos Make Money? 2025 Guide](https://www.vidboard.ai/faceless-videos-make-money-guide-2025/)
- [NichePursuits - Best Niches for TikTok 2026](https://www.nichepursuits.com/best-niches-for-tiktok/)
- [Medium - Top 10 Faceless TikTok Niche Ideas](https://medium.com/@wealthwellnessrevolution/top-10-faceless-tiktok-niche-ideas-unleash-your-creativity-with-the-ultimate-tiktok-creativity-e764f66c1f57)

### Video Automation Tools
- [Remotion - Make Videos Programmatically](https://www.remotion.dev/)
- [Remotion TikTok Template](https://www.remotion.dev/templates/tiktok)
- [Remotion createTikTokStyleCaptions()](https://www.remotion.dev/docs/captions/create-tiktok-style-captions)
- [GitHub - remotion-dev/template-tiktok](https://github.com/remotion-dev/template-tiktok)
- [GitHub - SEFI2/text-to-video-bot-python (FFmpeg + MoviePy + ChatGPT)](https://github.com/SEFI2/text-to-video-bot-python)
- [GitHub - Geeoon/ffmpeg-tiktok-formatter](https://github.com/Geeoon/ffmpeg-tiktok-formatter)
- [Medium - Automating Unique Content Creation with Python and FFmpeg](https://medium.com/@tokerb/automating-unique-content-creation-with-python-and-ffmpeg-9279e4569d59)

### Text-to-Speech & Audio
- [ElevenLabs - Create Speech with Timestamps](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps)
- [ElevenLabs - Eleven V3 Timing / Word-Level Timestamps](https://wavespeed.ai/models/elevenlabs/eleven-v3/timing)
- [Suno API Review - Complete 2026 Guide](https://evolink.ai/blog/suno-api-review-complete-guide-ai-music-generation-integration)
- [Kie AI Music API](https://kie.ai/suno-api)
- [GitHub - gcui-art/suno-api](https://github.com/gcui-art/suno-api)

### Stock Footage & Assets
- [Pexels API Documentation](https://www.pexels.com/api/documentation/)
- [Pexels - Food Videos](https://www.pexels.com/search/videos/food/)
- [Pexels - Food Prep Videos](https://www.pexels.com/search/videos/food%20prep/)
- [Storyblocks API Reference](https://documentation.storyblocks.com/)
- [Storyblocks API Business Solutions](https://www.storyblocks.com/resources/business-solutions/api)

### TikTok APIs & Developer Docs
- [TikTok Content Posting API Overview](https://developers.tiktok.com/products/content-posting-api/)
- [TikTok Content Posting API Reference](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)
- [TikTok Content Sharing Guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines)
- [TikTok Stitch Feature](https://support.tiktok.com/en/using-tiktok/creating-videos/stitch)

### Screen Recording & Automation
- [GitHub - trion-development/screen-capture-puppeteer-playwright](https://github.com/trion-development/screen-capture-puppeteer-playwright)
- [Playwright - Videos Documentation](https://playwright.dev/docs/videos)
- [Browserless - How to Create Puppeteer Screencasts](https://www.browserless.io/blog/puppeteer-screencasts)
- [GitHub - raymelon/playwright-screen-recorder](https://github.com/raymelon/playwright-screen-recorder/)

### Music & Trending Sounds
- [Buffer - How to Find Trending TikTok Sounds in 2026](https://buffer.com/resources/how-to-find-trending-tiktok-sounds/)
- [ContentStudio - How to Find Trending TikTok Sounds](https://contentstudio.io/blog/tiktok-sounds)
- [TikTok Commercial Music Library](https://ads.tiktok.com/help/article/commercial-music-library)
- [StackInfluence - Royalty-Free Commercial Music for TikTok](https://stackinfluence.com/find-royalty-free-commercial-music-for-tiktok/)
- [Apify - TikTok Music Trend API](https://apify.com/novi/tiktok-music-trend-api/api)
- [GitHub - davidteather/TikTok-Api](https://github.com/davidteather/TikTok-Api)

### Mobile Automation (for context on Stitch/Duet)
- [BlackHatWorld - TikTok Automation Using Appium](https://www.blackhatworld.com/seo/tiktok-automation-using-appium-youre-about-to-access-a-tiktok-experience-designed-just-for-you.1742984/)
- [Appium Documentation](https://appium.io/docs/en/3.1/intro/appium/)

### Kinetic Typography
- [IKAgency - Kinetic Typography Complete Guide 2026](https://www.ikagency.com/graphic-design-typography/kinetic-typography/)
- [B2W - Top 25 Kinetic Typography Animation Videos](https://www.b2w.tv/blog/kinetic-typography-animation-videos)

### Previous Research Reports (This Repository)
- [00 - Executive Summary & Recommendations](./00-executive-summary-and-recommendations.md)
- [01 - Pipeline Steps Overview](./01-pipeline-steps-overview.md)
- [02 - Tools Landscape](./02-tools-landscape.md)
- [03 - Video Automation Deep Dive](./03-video-automation-deep-dive.md)
- [04 - Build vs Buy Analysis](./04-build-vs-buy-analysis.md)

---

## Appendix A: Template Design Requirements

### Video Templates (Remotion - React/TypeScript)

Each template must be a self-contained Remotion composition that accepts:
- `script`: The script JSON from Claude
- `assets`: Manifest of file paths for video clips, audio, images
- `config`: Randomization parameters (colors, fonts, transitions)

**Deliverables per template:**
1. React component file (`src/compositions/[TemplateName].tsx`)
2. Storybook preview for design review
3. Test script with sample data
4. Style variants (3-5 color schemes per template)

**Template design priorities (build order):**
1. `StockFootageMontage` -- highest versatility, covers most content
2. `KineticTypography` -- no footage needed, pure text animation
3. `AppDemoNarrated` -- direct product marketing
4. `RecipeCard` -- food niche specific, high performer
5. `QuickTipStack` -- simple, fast to build, good variety filler
6. `SplitScreenCompare` -- engagement driver
7. `PhotoSlideshow` -- simple, reuses carousel assets
8. `DataVisualization` -- authority building content
9. `ReactionStyle` -- for Stitch alternative content

### Carousel Templates (Puppeteer - HTML/CSS)

Each template must be an HTML file with CSS that:
- Renders at 1080x1920 when screenshotted
- Accepts data via template variables (Handlebars, Nunjucks, or similar)
- Has safe zone padding for TikTok UI (bottom 320px)
- Uses web fonts loaded from Google Fonts CDN

**Deliverables per template:**
1. HTML template file (`templates/carousel/[template_name].html`)
2. CSS stylesheet (`templates/carousel/[template_name].css`)
3. Sample data JSON for testing
4. Color scheme variants (CSS custom properties)

---

## Appendix B: Phased Implementation Timeline

### Phase 1: Carousel Launch (Weeks 1-3)
- Adapt planning engine for TikTok
- Build 4 carousel templates
- Adapt Puppeteer rendering for 1080x1920
- Set up TikTok Content Posting API
- Set up Google Sheets approval workflow
- **Goal: First carousel posts live by Week 3**

### Phase 2: Video Launch via Creatomate (Weeks 4-6)
- Integrate ElevenLabs TTS pipeline
- Integrate Epidemic Sound music library
- Build FFmpeg audio mixing
- Set up 3-5 Creatomate video templates
- Wire Creatomate API into pipeline
- **Goal: First video posts live by Week 6**

### Phase 3: Remotion Migration + Full Pipeline (Weeks 7-12)
- Build 9 Remotion video compositions
- Set up Lambda rendering
- Migrate from Creatomate to Remotion
- Build reaction-style video pipeline
- Build A/B testing framework
- Build weekly/monthly analysis pipeline
- **Goal: Full automated pipeline operational by Week 12**

### Phase 4: Optimization (Weeks 13+)
- Continuous template additions
- A/B test-driven optimization
- Stock footage library expansion
- Cross-platform repurposing evaluation
- Template refresh based on performance data

---

*This report was produced on February 22, 2026. It overrides the "hybrid human+AI" recommendations from Reports 00-04 with a fully automated approach per client direction. The pipeline is designed for zero human filming, zero manual editing, and zero manual design -- with human review as the only required touchpoint before posting.*
