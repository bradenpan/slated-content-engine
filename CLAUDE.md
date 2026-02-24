# CLAUDE.md — Pinterest Pipeline

## Critical Rules
- **NEVER read .env, .env.*, or data/token-store.json.** These contain live API keys and secrets. If you need to know what env vars exist, read .env.example instead.
- **NEVER display, log, or reference the contents of secret files** in conversation output.
- If you need to edit .env (e.g., add a new variable), use the Edit tool with a targeted old_string/new_string — never Read the full file first.
- **Do NOT add Co-Authored-By lines** or any Claude/AI co-author attribution to git commits.
- **NEVER spawn sub-agents with `bypassPermissions` mode.** All agents must use default permissions so the user retains approval control over tool calls.
- **Plan files and any generated files must use descriptive names** that reflect their content (e.g., `regen-ai-comparison-fix.md`, not `humming-growing-beaver.md`). No random/cute names.

## Project Overview
This is the Slated Pinterest automation pipeline. It generates blog posts and pins via AI, deploys them to goslated.com, posts pins to Pinterest, pulls analytics, and runs weekly/monthly reviews.

## Key Paths
- `src/` — Python pipeline scripts
- `prompts/` — Claude prompt templates for content generation
- `templates/pins/` — HTML/CSS pin templates
- `strategy/` — Content strategy files (keywords, CTAs, boards, brand voice)
- `data/` — Runtime data (content log, token store — gitignored)
- `.github/workflows/` — GitHub Actions workflow definitions
- `.env.example` — Template showing required env vars (safe to read)
- `.env` — Live credentials (NEVER read)
