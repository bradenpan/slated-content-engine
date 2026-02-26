# Approval Flow: Monday Pipeline Flow -- Step by Step

*Updated for pipeline simplification (Feb 2026). See "New in this version" at the bottom.*

---

## Step 1: Weekly Review runs automatically (Monday 6am ET)

* `weekly-review.yml` fires on cron schedule
* Pulls Pinterest analytics for the past week
* Generates content memory summary + weekly performance analysis via Claude
* Generates the weekly content plan (8-10 blog posts + derived pins) via Claude
* Writes plan to the **Weekly Review** tab in Google Sheet
* You get a Slack notification: "Weekly review ready"

## Step 2: You review the plan

* Open Google Sheet -> Weekly Review tab
* Review the plan (blog post topics, pillars, keywords, pin assignments, boards, schedule)
* If everything looks good, skip to Step 3 (approve the plan)
* If some blog post topics need replacing, go to Step 2.5 first

## Step 2.5: Plan-Level Regen (OPTIONAL -- NEW)

Only needed if specific blog post topics are wrong, off-strategy, duplicated, or not seasonal enough. Skip this entirely if the plan looks fine.

* In the Weekly Review tab, scroll to the "CONTENT PLAN" section
* Blog post rows have columns: ID, Type, Topic, Pillar, Keywords, **Status** (column F), **Feedback** (column G)
* For each blog post you want replaced:
    * Set column F (Status) to `regen`
    * Optionally write what you want changed in column G (Feedback) -- be specific, this gets fed directly to the AI. Examples: "too similar to last week's chicken post", "need something about spring grilling instead", "this pillar is over-represented, swap for pillar 3"
* Leave blog posts you're happy with alone (blank Status = keep as-is)
* Trigger the regen:
    * Click the **Run Plan Regen** button (if you set one up), OR
    * Set cell **B5** to `regen`
* Apps Script fires -> triggers `regen-plan` workflow (~2-5 min)
* The Weekly Review tab refreshes with updated plan. Replaced posts get new topics, and their derived pins are also updated
* B5 automatically resets to "idle"
* You get a Slack notification summarizing what was replaced
* Review the updated plan again. If you need more changes, repeat this step
* When you're satisfied, proceed to Step 3

## Step 3: You approve the plan

* Change cell B3 from `pending_review` to `approved`
* Apps Script fires -> triggers `generate-content` workflow

## Step 4: Content generation runs (~15-30 min)

* Generates 8-10 blog post MDX files via Claude
* Generates pin copy (titles, descriptions, alt text, text overlays) via GPT-5 Mini (with Claude fallback)
* Generates AI image prompts via GPT-5 Mini (with Claude fallback)
* Generates AI images via gpt-image-1.5 -- all images are AI-generated, no stock photos
* Renders ~28 pin PNGs (HTML/CSS templates + AI hero images + text overlays via Puppeteer)
* Commits generated files to repo
* Uploads pin images and blog hero images to GCS (Google Cloud Storage)
* Writes **Content Queue** tab with inline pin/blog image previews + blog summaries
* You get a Slack notification: "28 pins + 10 blog posts ready for review"

## Step 5: You review the generated content

* Open Google Sheet -> Content Queue tab
* The Content Queue has 12 columns (A-L): ID, Type, Title, Description, Board, Blog URL, Schedule, Pillar, Thumbnail, Status, Notes, Feedback
* Pin rows show the actual rendered pin image inline (column I)
* Blog rows show the hero image thumbnail (column I) and blog description (column D)
* For each item, change column J (Status):
    * `approved` -- good to go
    * `rejected` -- won't be deployed (add notes in column K if needed)
    * `regen_image` -- image doesn't work, get a new one
    * `regen_copy` -- title/description needs a redo (pins only -- not available for blog posts)
    * `regen` -- redo both image and copy
* For any regen status: type what you want changed in column L (Feedback). Be specific -- this gets fed directly to the AI.

## Step 6 (if needed): Regeneration

* After flagging items in Step 5, click the **Run Regen** button or type `run` in cell **N1**
* Apps Script fires -> triggers `regen-content` workflow (~5-10 min)
* Only the flagged rows are regenerated -- everything else is untouched
* Regenerated items reset to `pending_review` with updated thumbnails and/or text
* You get a Slack notification
* Go back to Step 5 and re-review
* The deploy gate does NOT fire until every row is `approved` or `rejected`

## Step 7: Preview deployment runs (~3 min)

* Once ALL rows are approved or rejected, Apps Script fires automatically -> triggers `deploy-to-preview`
* Deploys blog posts + hero images to the `develop` branch on goslated.com
* Vercel auto-creates a preview deployment

## Step 8: You approve production

* Check blog posts on Vercel preview URL
* Change cell B4 from `pending_review` to `approved`

## Step 9: Production promotion runs (~3 min)

* Merges develop -> main on goslated.com
* Verifies blog post URLs are live (retries up to 3 min)
* Creates `pin-schedule.json` from approved pins

## Step 10: Daily posting (daily, 4 pins/day)

* `daily-post-morning.yml` (10am ET) -- 1 pin
* `daily-post-afternoon.yml` (3pm ET) -- 1 pin
* `daily-post-evening.yml` (8pm ET) -- 2 pins (peak Pinterest usage window)

---

**Your touch points:** Steps 2, 2.5 (if needed), 3, 5, 6 (if needed), and 8.

---

## New in this version

* **Plan-level regen (Step 2.5):** You can now flag individual blog post topics for replacement during plan review, with specific feedback. This happens BEFORE content generation, so you catch bad topics early instead of after 30 minutes of generation.
* **GPT-5 Mini for pin copy and image prompts:** Pin titles/descriptions and image prompts are now generated by GPT-5 Mini (~10x cheaper) with automatic Claude fallback if GPT-5 Mini fails.
* **All images are AI-generated:** No more stock photos. All pin and blog hero images come from gpt-image-1.5. The old stock photo comparison workflow is gone.
* **No more `use_ai_image` status:** Since all images are AI from the start, the `use_ai_image` review option has been removed. Just `approved`, `rejected`, `regen`, `regen_image`, and `regen_copy`.
* **Content Queue is now 12 columns (A-L):** The old Column M "AI Image" is gone. Regen trigger is at cells M1:N1 (label + trigger).
* **Images upload to GCS:** Pin images and blog hero images upload to Google Cloud Storage instead of Google Drive. Faster and more reliable for Sheet previews.
