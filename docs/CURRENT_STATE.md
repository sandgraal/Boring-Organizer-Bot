# Current Implementation State

This document summarizes what is implemented today (CLI + API + UI flow) and outlines the most important gaps that we are actively planning to close. It is the source of truth for what B.O.B actually does when you run it locally right now.

## CLI Surface (`bob/cli/main.py`)
1. **Initialization** – `bob init` prepares the database (with sqlite-vec if available) and prints the current vector-search fallback status.
2. **Indexing** – `bob index <paths>` or `bob index --watchlist` drives `bob.index.index_paths`, chunking/embedding documents and respecting the `.bob_watchlist.yaml` targets as needed.
3. **Watchlist helpers** – `bob watchlist list/add/remove/clear` live-manages watchlist entries, normalizing absolute paths for deduplication.
4. **Querying** – `bob ask` synthesizes an answer (snippet + citations) while `bob search` surfaces raw chunks with decision badges, highlighting outdated sources and respecting max-age filters.
5. **Decision management** – `bob extract-decisions`, `bob decisions`, `bob decision`, and `bob supersede` wrap the NLP-based extractor (`bob.extract.decisions`) plus the decision table stored with metadata.
6. **Evaluation** – `bob eval run` and `bob eval compare` execute the evaluation harness (`tests`/`bob.eval.runner`) and expose metrics/JSON exports for regressions.
7. **Status & Server** – `bob status` reports database stats, project breakdowns, and vector capability; `bob serve` boots the FastAPI app (with optional reload) that powers both the CLI’s API target and the static UI.

## API Surface (`bob/api/routes/`)
- `GET /health` – quick status, version, and total indexed document count.
- `POST /ask` – natural-language query → formatted snippet + `sources` + Coach Mode suggestions + footer (`AskFooter`) based on `bob.answer.formatter` + deterministic coach engine (`bob.coach.engine`).
- `POST /index` / `GET /index/{job_id}` – single-worker job manager enforces one concurrent job, tracks progress/errors, and spawns `_run_index_job` to drive `index_paths`.
- `GET /documents` – paginated document list with optional `project`/`source_type` filters and consistent ISO timestamps.
- `GET /projects` – per-project stats (`document_count`, `chunk_count`, `source_types`) derived from `bob.db.database.get_stats`.
- `POST /open` – heuristics for launching editors (VS Code, Cursor, Vim, Sublime, system defaults) and returns success/message/command.
- `GET /settings`, `PUT /settings`, `POST /suggestions/{id}/dismiss` – Coach Mode preferences, cooldown updates, and dismissal logging stored in the `settings` table.
- Static UI (`GET /`) + `/static/*` – `bob/api.app.create_app` mounts `bob/ui/static` and serves `bob/ui/index.html`.

## Web UI (`bob/ui/`)
- Built as a 3-pane experience with navigation tabs (Ask, Library, Indexing, Settings), filter sidebar, answer + footer, suggestion list, and sources panel.
- Interacts with the API endpoints above; it is fully local and wired to the `ask`, `documents`, `index`, and `settings` endpoints today.
- Coach Mode toggle, source footer, and “not found”/error states are functional; the currently visible UI does *not yet include the planned `/routines` or Fix Queue flows (the API now exposes `/routines/daily-checkin`, but the UI still lacks a Routines/Fix Queue surface).

## Data & Quality Helpers
- **Watchlist**: `.bob_watchlist.yaml` entries (via `bob.watchlist`) define repeated indexing targets so users can `bob index --watchlist`.
- **Decision extraction**: `bob.extract.decisions` finds ADR-style patterns, stores confidences, and surfaces rejected alternatives used by the CLI/UI.
- **Coach suggestions**: `bob.coach.engine.generate_coach_suggestions` enforces deterministic rules (coverage, staleness, capture hygiene) with cooldowns logged in `bob.db.database`.
- **Evaluation suite**: `bob.eval.runner` computes recall/precision/MRR metrics, while `tests/` + CLI commands offer regression tooling out of the box.

## Known Gaps & Next Steps
1. **Routines & Fix Queue** – The detailed workflow in `docs/ROUTINES_SPEC.md` is still a roadmap. `/routines/daily-checkin` and `/routines/weekly-review` now write their respective templates into `vault/routines/daily/YYYY-MM-DD.md` and `vault/routines/weekly/YYYY-W##.md` with retrieval-backed citations, but the remaining `/routines/*` actions, Fix Queue dashboard, and UI routines surface remain unimplemented.
2. **Coach Mode UI integration** – The UI exposes a toggle and suggestions list, but coach suggestions are limited to explainers from `/ask` rather than actionable routine prompts until the Fix Queue landings ship.
3. **Planner + decision lifecycle automation** – Automated daily/meeting/weekly routines, decision superseding, and coach-driven nudges remain documented in `docs/IMPLEMENTATION_PLAN.md` but are not triggered by the UI/API today.
4. **Health dashboard** – A Fix Queue dashboard and ingestion telemetry are described in the implementation plan but not surfaced in the `/health` endpoint or UI.

This document should be update-first when anything in the CLI/API/UI surface changes; it drives PR descriptions so contributors can immediately see “what works vs. what still needs to be built.”
