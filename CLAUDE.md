# CLAUDE.md — Pinterest Pipeline

## Critical Rules
- **NEVER read .env, .env.*, or data/token-store.json.** These contain live API keys and secrets. If you need to know what env vars exist, read .env.example instead.
- **NEVER display, log, or reference the contents of secret files** in conversation output.
- If you need to edit .env (e.g., add a new variable), use the Edit tool with a targeted old_string/new_string — never Read the full file first.
- **Do NOT add Co-Authored-By lines** or any Claude/AI co-author attribution to git commits.
- **NEVER spawn sub-agents with `bypassPermissions` mode.** All agents must use default permissions so the user retains approval control over tool calls.
- **Plan files and any generated files must use descriptive names** that reflect their content (e.g., `regen-ai-comparison-fix.md`, not `humming-growing-beaver.md`). No random/cute names.
- **NEVER make assumptions about how external systems behave.** Before writing code that depends on how goslated.com, Vercel, Pinterest, or any external service works (routing, URL structure, API behavior, deployment timing), VERIFY the actual behavior first — check the deployed site, read the service's config, or ask the user. Do not guess. Wrong assumptions cause production failures.
- **NEVER speculate about root causes.** When diagnosing a failure, gather evidence (logs, HTTP responses, actual behavior) BEFORE proposing a fix. If you don't have evidence, say so and ask the user where to find it. Do not theorize and then build fixes on top of unverified theories.

## Project Overview
This is the Slated Pinterest automation pipeline. It generates blog posts and pins via AI, deploys them to goslated.com, posts pins to Pinterest, pulls analytics, and runs weekly/monthly reviews.

## Key Paths
- `ARCHITECTURE.md` — **Start here.** Full system architecture, pipeline flow, file responsibilities, data schemas, gotchas
- `src/` — Python pipeline scripts
- `src/apis/` — API wrappers (Claude, Pinterest, Sheets, GCS, GitHub, Slack, etc.)
- `src/utils/` — Shared utilities (content log, plan helpers, safe_get, etc.)
- `prompts/` — Claude/GPT prompt templates for content generation
- `templates/pins/` — HTML/CSS pin templates (5 types × 3 variants)
- `strategy/` — Content strategy files (keywords, CTAs, boards, brand voice)
- `data/` — Runtime data (content log, token store — gitignored)
- `.github/workflows/` — GitHub Actions workflow definitions
- `.env.example` — Template showing required env vars (safe to read)
- `.env` — Live credentials (NEVER read)
- `memory-bank/architecture/architecture-data-flows.md` — Deep-dive data flow reference (schemas, column layouts, field mappings)
