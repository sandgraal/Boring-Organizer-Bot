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

## Current Capabilities

B.O.B currently ships as a CLI-first/local API experience. The built-in commands, services, and UI that work out of the box right now are:

- **Document tooling:** `bob init`, `bob index`, `bob watchlist`, `bob connectors` plus recursive indexing with hybrid chunking/embedding and sqlite-vec if available.
- **Query surface:** `bob ask` for synthesized answers, `bob search` for raw retrieval, and the FastAPI `POST /ask` route with citations + Coach Mode suggestions.
- **Decision & metadata helpers:** `bob extract-decisions`, `bob decisions`, `bob decision`, `bob supersede`, plus the HTTP settings/suggestion endpoints that keep Coach Mode state in sync.
- **Evaluation + health:** `bob eval run/compare`, `bob status`, and `GET /health` for database stats.
- **Local UI + server:** `bob serve` hosts the FastAPI app that mounts `bob/ui/` (ask/library/indexing/settings panes) and the static editors/Open endpoint.

For a full inventory of what works today (and what gaps remain before routines/fix queue land), see [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md).

## Non-negotiables (answer contract)

Every answer must:

- Include **citations** for claims (file + locator: heading/lines or PDF pages).
- End with:
  - **Sources**
  - **Date confidence**
  - **“This may be outdated”** when applicable
- Follow: **No citation => no claim**  
  If B.O.B cannot support the answer from indexed sources, it returns: **“Not found in sources.”**

## Routines Roadmap

B.O.B ships today with the Ask/Library/Indexing/Settings/Routines/Health UI and the CLI/API surface described above. The deeper lint-driven Fix Queue remediation and connector toggles are still in the plan stage, while Coach Mode now adds health-driven suggestions. The actions and behaviors we intend to deliver are captured in [`docs/ROUTINES_SPEC.md`](docs/ROUTINES_SPEC.md) and include:

- **Daily Check-in / End-of-Day Debrief** → structured daily notes seeded from `open_loops` and recent context.
- **Meeting Prep / Debrief** → pre-flight bundles of agenda bullets, decisions, rejected options, and next actions with citations.
- **Weekly Review** → a weekly summary that flags stale decisions and metadata gaps.
- **New Decision / Trip Debrief** → guided templates for decisions, learnings, checklist seeds, and reusable insights.
- **Fix Queue** → health metrics, lint flags, and ingestion problems surfaced as prioritized tasks before optional-generation layers ship.

The API now exposes template-driven endpoints for `POST /routines/daily-checkin`, `/routines/daily-debrief`, `/routines/weekly-review`, `/routines/meeting-prep`, `/routines/meeting-debrief`, `/routines/new-decision`, and `/routines/trip-debrief`, each writing into the vault with citations. The UI now includes Routines and Health panels to run these templates and review Fix Queue signals, while deeper remediation workflows remain on the roadmap (see `docs/CURRENT_STATE.md` for details).

## Modes

### Boring B.O.B (default)

Neutral tone. No unsolicited advice. Strictly grounded.

### Coach Mode (opt-in)

Coach Mode adds a separate **“Suggestions (Coach Mode)”** section while preserving the answer contract:

- Max 3 suggestions per response
- Evidence-backed where possible (with citations); otherwise labeled **Hypothesis**
- Cooldown to prevent repeated nagging
- Suggestions never override grounded answers

## Knowledge Health & Fix Queue (current API + roadmap)

The Health tab surfaces `GET /health` and `GET /health/fix-queue`, reporting whether the server is running, the version, indexed document counts, and failure signals that drive Fix Queue tasks. For deeper telemetry (ingestion errors, metadata gaps, repeated questions, stale decisions, coach-driven tasks) refer to the Fix Queue design in [`docs/ROUTINES_SPEC.md`](docs/ROUTINES_SPEC.md) and the data-metric goals in [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md). That roadmap also explains how each metric will feed a prioritized task list before optional generation features ship.

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

### Run the Local UI

```bash
# Start the local API + UI server
bob serve
```

Open `http://localhost:8080` in your browser to use the UI.

If `bob` is not on your PATH, run:

```bash
.venv/bin/bob serve
# or
python -m bob.cli.main serve
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

### Watchlist & Automatic Indexing

B.O.B lets you store a small watchlist of frequently indexed locations so you avoid retyping paths.

1. **Add a target** (requires the path to exist or be a git URL):

   ```bash
   bob watchlist add ./my-notes --project personal-notes
   ```

2. **Inspect what’s saved**:

   ```bash
   bob watchlist list
   ```

3. **Start indexing everything in one command**:

   ```bash
   bob index --watchlist
   ```

Watchlist entries are stored in `.bob_watchlist.yaml` in your project root (override with `BOB_WATCHLIST_PATH`). Each entry can specify a project and language per target. Use `bob watchlist remove <path>` to tidy it up.

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

### Decision Review Cadence

```bash
# Review decisions older than 6 months
bob decisions --older-than 6m

# Review active decisions for a project
bob decisions --status active --older-than 90d --project cdc
```

### Advanced Search Syntax

```bash
# Exact phrase match - results must contain this exact text
bob ask '"API endpoint" configuration'

# Exclude terms - filter out results containing unwanted words
bob ask "python tutorial -beginner -introduction"

# Inline project filter - same as --project flag
bob ask "deployment guide project:devops"

# Filter by decision status
bob ask "decision:active decisions about logging"

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

### Backup and Restore

Protect your local knowledge base with regular backups:

```bash
# Create a backup
bob backup backups/bob-2025-12-27.db

# Create a compressed backup (recommended for storage)
bob backup backups/bob-2025-12-27.db --compress

# Restore from a backup
bob restore backups/bob-2025-12-27.db

# Force restore without confirmation
bob restore backups/bob-2025-12-27.db --force
```

**Backup best practices:**
- Backups use SQLite's backup API for consistency
- Compressed backups (.gz) save disk space
- Restore automatically backs up your current database first
- Schedule regular backups (e.g., via cron) for important data

## API Server (local-only)

```bash
# Start the server
bob serve

# Start on a custom port
bob serve --port 9000

# Enable auto-reload for development
bob serve --reload
```

The UI is served at `http://localhost:8080` when the server is running.

The API currently exposes the following local-only endpoints:

- `GET /health` — Uptime, version, database status, and indexed document count.
- `GET /health/fix-queue` — Failure signals and Fix Queue tasks derived from feedback, repeated questions, and metadata gaps.
- `POST /ask` — Natural-language query with citations plus Coach Mode suggestions and footer metadata.
- `POST /index` / `GET /index/{job_id}` — Submit an indexing job, stream progress/errors, and fetch its status once finished.
- `GET /projects` — Enumerate projects with document/chunk counts.
- `GET /documents` — Paginated document list filtered by project and source type.
- `POST /open` — Launch a suitable editor (or fallback instructions) for the requested file path and line.
- `POST /feedback` — Capture Helpful / Wrong or missing source / Outdated / Too long / Didn’t answer signals for the Fix Queue metrics.
- `POST /notes/create` — Render a canonical template into an allowed vault path.
- `POST /connectors/bookmarks/import`, `POST /connectors/highlights` — Import bookmarks and save manual highlights into `vault/manual-saves`.
- `GET /settings`, `PUT /settings`, `POST /suggestions/{id}/dismiss` — Coach Mode preferences, cooldowns, and dismissal logging.

Implementation details, request/response models, and example payloads live in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). 

Template-write APIs (implemented):

- `/routines/daily-checkin`, `/routines/daily-debrief`, `/routines/weekly-review`, `/routines/meeting-prep`, `/routines/meeting-debrief`, `/routines/new-decision`, `/routines/trip-debrief` — each renders a canonical template, gathers cited retrievals, and writes to the vault (`vault/routines`, `vault/meetings`, `vault/decisions`, `vault/trips`). See `docs/API_CONTRACT.md` for details.
- `/notes/create` — renders any canonical template to a vault path using the same permission checks.

Planned additions:

- Fix Queue remediation flows, calendar connector toggles, and richer lint guidance layered on top of the existing Routines/Health panels.

OpenAPI docs: `http://localhost:8080/docs`

## MCP Server (agent interoperability, local-only)

```bash
# Start the MCP server (JSON-RPC over HTTP)
bob mcp

# Override host/port
bob mcp --port 8091
```

The MCP server exposes tools for grounded `ask`, listing projects, index status, and
permissioned vault read/write (with dry-run). It is local-only by default and uses the
same vault scope rules as the routine endpoints.

## Web Interface

B.O.B includes a local UI designed to be **inspectable**:

- **Ask**: 3-pane layout (filters/project list, answer, clickable sources) backed by `/ask`.
- **Library**: browse indexed documents, drill into chunks, view sources.
- **Indexing**: dispatch indexing jobs via `/index` and monitor progress.
- **Settings**: Coach Mode preferences and toggle state via `/settings`.
- **Routines**: one-click daily/meeting/weekly/decision/trip flows driven by the spec in [`docs/ROUTINES_SPEC.md`](docs/ROUTINES_SPEC.md).
- **Health**: Fix Queue metrics, ingestion insights, and stale-decision radars before optional generation layers ship.

All features work offline — no external network requests.

![Ask Page](docs/screenshots/ask-page.png) _(screenshot placeholder)_

## Permissions (safe “deep access”)

B.O.B uses explicit permission scopes so deeper access stays safe and intentional:

- **Level 0**: read-only vault indexing/search
- **Level 1**: optional calendar import (local ICS/Caldav file import) — *planned, not yet implemented*
- **Level 2**: optional manual browser saves (explicit "save to vault" action)
- **Level 3**: template-bound note writing only (no arbitrary edits)
- **Level 4**: external accounts (out of scope for now)

The `permissions` block in `bob.yaml` mirrors this model and defaults to `scope=3`. Template writes (e.g., `/routines/daily-checkin`) require scope 3 and `permissions.allowed_vault_paths` to cover the target directory; setting the scope to `0` or removing a directory will make those endpoints return HTTP 403 `PERMISSION_DENIED` with the offending `target_path`/`scope_level`.

```yaml
permissions:
  default_scope: 3
  enabled_connectors:
    calendar_import: false
    browser_saves: false
  allowed_vault_paths:
    - vault/routines
    - vault/decisions
    - vault/trips
    - vault/meetings
    - vault/manual-saves
```

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

- [Current State](docs/CURRENT_STATE.md) — Live CLI/API/UI surface and known gaps.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Common issues and solutions
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) — Phased roadmap (UI + routines + health prioritized)
- [UI Plan](docs/UI_PLAN.md) — Interface design specification
- [API Contract](docs/API_CONTRACT.md) — HTTP API endpoints and schemas
- [Architecture](docs/architecture.md) — System design
- [Data Model](docs/data-model.md) — Database schema
- [Coach Mode Spec](docs/COACH_MODE_SPEC.md) — Coach Mode gates, cooldowns, suggestion types
- [Permissions](docs/PERMISSIONS.md) — Scope model and enforcement

Roadmap/longer-term specs:

- `docs/ROUTINES_SPEC.md` — Daily/meeting/weekly workflows + templates (planning stage)
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
