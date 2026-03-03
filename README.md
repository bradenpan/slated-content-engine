# Pinterest Pipeline

Automation pipeline for Slated's Pinterest channel. Takes a content strategy
as input and runs the full loop: content planning, blog post generation,
pin creation, posting, analytics, and review.

## Overview

- **Weekly cycle:** Monday analytics + planning + generation, Tuesday-Monday daily posting
- **Posting cadence:** 4 pins/day (28/week) across 3 daily windows
- **Blog-first workflow:** Blog posts are generated first; pins are derived from them
- **Human review gates:** Plan approval and content approval via Google Sheets
- **Monthly strategy review:** Deep analysis with strategy update recommendations

## Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full system architecture: pipeline flow, file responsibilities, data schemas, external integrations, workflows, and critical gotchas.

## Directory Structure

```
src/          - Pipeline scripts and API wrappers
prompts/      - Prompt templates for Claude/GPT
templates/    - Pin image templates (HTML/CSS)
strategy/     - Strategy docs, keyword lists, board structure, seasonal calendar
data/         - Runtime data (content log, generated content — gitignored)
.github/      - GitHub Actions workflow files
analysis/     - Weekly and monthly analysis outputs
```

## Setup

1. Copy `.env.example` to `.env` and fill in API keys
2. `pip install -r requirements.txt`
3. `playwright install chromium` (for pin rendering)
4. Run initial Pinterest OAuth flow via `python -m src.token_manager`
