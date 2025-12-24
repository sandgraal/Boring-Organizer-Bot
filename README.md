# B.O.B — Boring Organizer Bot

A local-first personal knowledge assistant with a **beautiful local web UI**, **citations-first answers**, and (optionally) **Coach Mode**. No cloud required: B.O.B indexes _your_ files (Markdown/PDF/recipes/docs) and answers questions with sources you can click and verify.

## What B.O.B is for

B.O.B answers questions like:

- “Where did I write about this idea?”
- “What recipe used achiote + hibiscus?”
- “What did I decide about CDC agent sizing?”
- “What option did I reject and why?”
- “What trips did I plan and what did I learn?”

It’s designed to become a daily-use partner via **routines** (daily check-in, meeting prep/debrief, weekly review), not just terminal search.

## Philosophy

- **Boring is good.** Simple, predictable, maintainable.
- **Local-first.** Your data stays on your machine. No API keys required for core functionality.
- **Citations or nothing.** Every answer includes source file + locator. No hallucinated claims.
- **Date-aware.** Answers include confidence about freshness and warn when content may be outdated.
- **Beautiful & inspectable.** The UI makes source verification one click away.
- **Smart retrieval.** Hybrid search combining semantic vectors with keyword matching.

## Non-negotiables (answer contract)

Every answer must:

- Include **citations** for claims (file + locator: heading/lines or PDF pages).
- End with:
  - **Sources**
  - **Date confidence**
  - **“This may be outdated”** when applicable
- Follow: **No citation => no claim**  
  If B.O.B cannot support the answer from indexed sources, it returns: **“Not found in sources.”**

## Daily use: routines (UI-first)

B.O.B is not terminal-only. The primary experience is a **local web UI** with one-click entry points that create structured notes and/or run grounded queries.

Planned routine actions (implemented incrementally):

- **Daily Check-in** → creates `daily/YYYY-MM-DD.md` from a template + pulls open loops/recent context
- **End-of-day Debrief** → adds lessons/open loops to today’s note
- **Meeting Prep** → pulls last decisions, unresolved questions, relevant notes + produces agenda bullets
- **Meeting Debrief** → captures decisions, rejected options + why, next actions; updates decision index
- **Weekly Review** → creates a weekly note + flags stale decisions
- **New Decision** → structured capture with lifecycle (decided/superseded)
- **Trip Debrief** → “what I learned” + reusable checklist seeds
- **Fix Queue** → prioritized cleanup tasks (metadata gaps, ingestion errors, staleness)

## Modes

### Boring B.O.B (default)

Neutral tone. No unsolicited advice. Strictly grounded.

### Coach Mode (opt-in)

Coach Mode adds a separate **“Suggestions (Coach Mode)”** section while preserving the answer contract:

- Max 3 suggestions per response
- Evidence-backed where possible (with citations); otherwise labeled **Hypothesis**
- Cooldown to prevent repeated nagging
- Suggestions never override grounded answers

## Knowledge Health + Fix Queue (keep it reliable over years)

B.O.B tracks system health and turns it into a prioritized Fix Queue:

- “Not found in sources” frequency by project
- PDFs with no text / ingestion errors
- missing metadata counts
- repeated questions (discoverability issues)
- stale decisions radar

## Quick Start

### Install

```bash
# Clone the repo
git clone https://github.com/sandgraal/Boring-Organizer-Bot.git
cd Boring-Organizer-Bot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Initialize the database
bob init
```

### Index Your Documents

```bash
# Index a folder of markdown files
bob index ./my-notes --project "personal-notes"

# Index multiple paths
bob index ./docs ./recipes ./projects --project "everything"

# Index a git repository (README + /docs only)
bob index https://github.com/user/repo --project "external-docs"
```

### Ask Questions

```bash
# Simple query
bob ask "What did I decide about CDC agent sizing?" --project cdc

# Filter by project
bob ask "Where did I write about the prefetch idea?" --project personal-notes

# Get more context
bob ask "How did I implement auth?" --top-k 10

# JSON output (for scripts / tooling)
bob ask "Summarize my decisions about logging" --json
```

### Search (no synthesis)

```bash
# Search without answer synthesis - shows raw search results
bob search "API configuration"

# Filter by project
bob search "deployment" --project devops

# Limit results to documents less than 90 days old
bob search "authentication" --max-age 90

# Output as JSON for scripting
bob search "error handling" --json
```

### Advanced Search Syntax

```bash
# Exact phrase match - results must contain this exact text
bob ask '"API endpoint" configuration'

# Exclude terms - filter out results containing unwanted words
bob ask "python tutorial -beginner -introduction"

# Inline project filter - same as --project flag
bob ask "deployment guide project:devops"

# Combine all syntax types
bob ask '"error handling" best practices -deprecated project:docs'
```

### Output Format

Every answer must end with Sources + Date confidence (+ outdated warning):

```
Answer: [synthesized response based on retrieved chunks]

Sources:
  1. [docs/api.md] heading: "Logging Configuration" (lines 45-67)
     Date: 2025-03-15 | Confidence: HIGH
  2. [notes/decisions.md] heading: "API Design" (lines 12-34)
     Date: 2023-11-20 | Confidence: MEDIUM
     ⚠️  This may be outdated (>6 months old)
```

### Check Status

```bash
# Show indexed documents and stats
bob status

# Show status for specific project
bob status --project "personal-notes"
```

### Evaluate Retrieval Quality

```bash
# Run evaluation suite (golden questions + regressions)
bob eval

# Run evaluation for a single project
bob eval --project "cdc"
```

## API Server (local-only)

```bash
# Start the server
bob serve

# Start on a custom port
bob serve --port 9000

# Enable auto-reload for development
bob serve --reload
```

The API provides (core today; expands as routines/health ship):

- `POST /ask` — Query with structured citations
- `POST /index` — Start indexing jobs
- `GET /index/{job_id}` — Check indexing progress
- `GET /projects` — List all projects
- `GET /documents` — List indexed documents with filters
- `POST /open` — Open files at specific locations

Planned additions:

- `GET /health` — Metrics + Fix Queue
- `POST /feedback` — Helpful / wrong / outdated / too long / didn’t answer
- `GET/PUT /settings` — Mode preferences (boring/coach), thresholds, per-project defaults
- `/routines/*` — Daily check-in, meeting prep/debrief, weekly review, new decision

OpenAPI docs: `http://localhost:8080/docs`

## Web Interface

B.O.B includes a local UI designed to be **inspectable**:

- **Ask**: 3-pane layout (filters/projects, answer, clickable sources)
- **Library**: browse indexed documents + filters
- **Indexing**: start indexing jobs and monitor progress
- **Decisions**: decision lifecycle, superseded links, rejected options
- **Routines**: one-click daily/meeting/weekly flows (planned)
- **Health**: Fix Queue + ingestion/metadata/staleness metrics (planned)

All features work offline — no external network requests.

![Ask Page](docs/screenshots/ask-page.png) _(screenshot placeholder)_

## Permissions (safe “deep access”)

B.O.B uses explicit permission scopes so deeper access stays safe and intentional:

- **Level 0**: read-only vault indexing/search
- **Level 1**: optional calendar import (local ICS/Caldav file import)
- **Level 2**: optional manual browser saves (explicit “save to vault” action)
- **Level 3**: template-bound note writing only (no arbitrary edits)
- **Level 4**: external accounts (out of scope for now)

## Configuration

Configuration lives in `bob.yaml` (project root or `~/.config/bob/bob.yaml`):

```yaml
# See bob.yaml.example for full options
database:
  path: ./data/bob.db

embedding:
  model: all-MiniLM-L6-v2
  dimension: 384

defaults:
  project: main
  top_k: 5

# Hybrid search (combines vector + keyword matching)
search:
  hybrid_enabled: true
  vector_weight: 0.7
  keyword_weight: 0.3
```

Environment variables override config:

- `BOB_DB_PATH` — database path
- `BOB_EMBEDDING_MODEL` — embedding model name
- `BOB_DEFAULT_PROJECT` — default project name

## Supported Inputs

| Type                | Extensions                     | Locator Format             |
| ------------------- | ------------------------------ | -------------------------- |
| Markdown            | `.md`, `.markdown`             | heading + line range       |
| PDF                 | `.pdf`                         | page range                 |
| Word                | `.docx`                        | paragraph index            |
| Excel               | `.xlsx`, `.xls`                | sheet + row range          |
| Recipe (structured) | `.recipe.yaml`, `.recipe.json` | section                    |
| Git Docs            | URL or path                    | commit + file + line range |

## Project Structure

```
/bob                 # Python package
  /api               # HTTP API server
  /ui                # Web interface assets
  /cli               # CLI commands
  /ingest            # File parsers
  /index             # Chunking and embedding
  /retrieval         # Search and ranking
  /answer            # Citation formatting + confidence rules
  /db                # Database and migrations
/prompts             # Agent prompt templates
/tests               # Unit and integration tests
/docs                # Architecture & specs
/data                # Local data (gitignored)
```

## Documentation

- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) — Phased roadmap (UI + routines + health prioritized)
- [UI Plan](docs/UI_PLAN.md) — Interface design specification
- [API Contract](docs/API_CONTRACT.md) — HTTP API endpoints and schemas
- [Architecture](docs/architecture.md) — System design
- [Data Model](docs/data-model.md) — Database schema

Planned/added as the roadmap evolves:

- `docs/ROUTINES_SPEC.md` — Daily/meeting/weekly workflows + templates
- `docs/COACH_MODE_SPEC.md` — Coach Mode gates, cooldowns, suggestion types
- `docs/PERMISSIONS.md` — Scope model and enforcement
- Health/Fix Queue spec (name may vary) — metrics, queues, and acceptance tests

## Development

```bash
# Run tests
make test

# Format code
make format

# Lint
make lint

# All checks
make check
```

## License

MIT — See [LICENSE](LICENSE)

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
