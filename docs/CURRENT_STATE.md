# Current Implementation State

This document summarizes what is implemented today (CLI + API + UI flow) and outlines the most important gaps that we are actively planning to close. It is the source of truth for what B.O.B actually does when you run it locally right now.

## CLI Surface (`bob/cli/main.py`)
1. **Initialization** – `bob init` prepares the database (with sqlite-vec if available) and prints the current vector-search fallback status.
2. **Indexing** – `bob index <paths>` or `bob index --watchlist` drives `bob.index.index_paths`, chunking/embedding documents and respecting the `.bob_watchlist.yaml` targets as needed.
3. **Watchlist helpers** – `bob watchlist list/add/remove/clear` live-manages watchlist entries, normalizing absolute paths for deduplication.
4. **Querying** – `bob ask` synthesizes an answer (snippet + citations) while `bob search` surfaces raw chunks with decision badges, highlighting outdated sources and respecting max-age filters.
5. **Decision management** – `bob extract-decisions`, `bob decisions` (including `--older-than` cadence filters), `bob decision`, and `bob supersede` wrap the NLP-based extractor (`bob.extract.decisions`) plus the decision table stored with metadata.
6. **Evaluation** – `bob eval run` and `bob eval compare` execute the evaluation harness (`tests`/`bob.eval.runner`) and expose metrics/JSON exports for regressions.
7. **Status & Server** – `bob status` reports database stats, project breakdowns, and vector capability; `bob serve` boots the FastAPI app (with optional reload) that powers both the CLI’s API target and the static UI.
8. **MCP Server** – `bob mcp` starts a local-only JSON-RPC MCP server exposing grounded `ask`, project stats, index status, and permissioned vault read/write (with dry-run).

## API Surface (`bob/api/routes/`)
- `GET /health` – quick status, version, and total indexed document count.
- `POST /ask` – natural-language query → formatted snippet + `sources` + Coach Mode suggestions + footer (`AskFooter`) based on `bob.answer.formatter` + deterministic coach engine (`bob.coach.engine`).
- `POST /index` / `GET /index/{job_id}` – single-worker job manager enforces one concurrent job, tracks progress/errors, and spawns `_run_index_job` to drive `index_paths`.
- `GET /documents` – paginated document list with optional `project`/`source_type` filters and consistent ISO timestamps.
- `GET /projects` – per-project stats (`document_count`, `chunk_count`, `source_types`) derived from `bob.db.database.get_stats`.
- `POST /open` – heuristics for launching editors (VS Code, Cursor, Vim, Sublime, system defaults) and returns success/message/command.
- `GET /settings`, `PUT /settings`, `POST /suggestions/{id}/dismiss` – Coach Mode preferences, cooldown updates, and dismissal logging stored in the `settings` table.
- `POST /feedback` – logs user feedback buttons so future Fix Queue calculations know which answers were helpful, wrong, outdated, too long, or missing.
- `POST /routines/daily-checkin`, `POST /routines/daily-debrief`, `POST /routines/weekly-review`, `POST /routines/meeting-prep`, `POST /routines/meeting-debrief`, `POST /routines/new-decision`, `POST /routines/trip-debrief` – template-backed writes with cited retrieval buckets that persist to `vault/routines/`, `vault/meetings/`, `vault/decisions/`, and `vault/trips/`.
- `POST /notes/create` – template-backed manual note creation that renders any canonical template into an allowed vault path.
- `GET /health/fix-queue` – returns failure signals (not-found frequency, metadata gaps + top offenders, stale notes/decisions, low indexed volume, low retrieval hit rate, repeated questions, permission denials) and prioritized Fix Queue tasks derived from feedback, metadata deficits, staleness prompts (weekly review), low volume/hit rate prompts (indexing), denied write attempts, and capture lint issues.
- Static UI (`GET /`) + `/static/*` – `bob/api.app.create_app` mounts `bob/ui/static` and serves `bob/ui/index.html`.

## Web UI (`bob/ui/`)
- Built as a 3-pane experience with navigation tabs (Ask, Routines, Library, Indexing, Settings, Health), filter sidebar, answer + footer, suggestion list, and a sources panel with an Audit tab for retrieved vs used chunks.
- Interacts with the API endpoints above; it is fully local and wired to the `ask`, `documents`, `index`, `settings`, `routines`, `notes/create`, and `health/fix-queue` endpoints today.
- Coach Mode toggle, suggestion list (with routine run actions when available), source footer, and "not found"/error states are functional. The Routines page can run daily, weekly, meeting, decision, and trip routines with previews, warnings, and cited retrieval buckets. The Health page surfaces Fix Queue signals and tasks, with run routine, run query, and open-file actions where applicable.
- Global "New note" action renders canonical templates into vault paths via `POST /notes/create`, echoing warnings and open actions for capture.
- Settings now includes a permissions summary (scope, vault root, allowed paths, connector states) for quick visibility.

## Data & Quality Helpers
- **Watchlist**: `.bob_watchlist.yaml` entries (via `bob.watchlist`) define repeated indexing targets so users can `bob index --watchlist`.
- **Decision extraction**: `bob.extract.decisions` finds ADR-style patterns, stores confidences, and surfaces rejected alternatives used by the CLI/UI.
- **Coach suggestions**: `bob.coach.engine.generate_coach_suggestions` enforces deterministic rules (coverage, staleness, capture hygiene) with cooldowns logged in `bob.db.database`.
- **Evaluation suite**: `bob.eval.runner` computes recall/precision/MRR metrics, while `tests/` + CLI commands offer regression tooling out of the box.

## Known Gaps & Next Steps
1. **Routines & Fix Queue depth** - The detailed workflow in `docs/ROUTINES_SPEC.md` guides the captures and citations. `/routines/daily-checkin`, `/routines/daily-debrief`, `/routines/weekly-review`, `/routines/meeting-prep`, `/routines/meeting-debrief`, `/routines/new-decision`, and `/routines/trip-debrief` now write their canonical templates into `vault/routines/`, `vault/meetings/`, `vault/decisions/`, and `vault/trips/` with cited retrieval buckets, and `POST /feedback` feeds `GET /health/fix-queue`. Capture lint tasks now surface in Fix Queue, and the Health UI offers one-click open for lint/metadata fixes, but connector toggles beyond running routines remain missing.
2. **Coach Mode UI integration** – The UI exposes a toggle and suggestions list, but coach suggestions are limited to explainers from `/ask` rather than actionable routine prompts until the Fix Queue landings ship.
3. **Planner + decision lifecycle automation** – While the API now provides the individual routine endpoints, the orchestration that wires them into recurring planner flows, automatic decision superseding, and coach-driven nudges still awaits UI triggers and actionable Fix Queue guidance in `docs/IMPLEMENTATION_PLAN.md`.
4. **Health dashboard follow-through** - A Fix Queue dashboard and ingestion telemetry are described in the implementation plan; `/health/fix-queue` now delivers the failure signals (not-found frequency, metadata gaps + top offenders, stale notes/decisions, ingestion errors, low indexed volume, low retrieval hit rate, repeated questions, permission denials) plus lint-driven tasks, and Fix Queue actions can open flagged files or jump to indexing, but deeper remediation still remains manual.

This document should be update-first when anything in the CLI/API/UI surface changes; it drives PR descriptions so contributors can immediately see “what works vs. what still needs to be built.”
