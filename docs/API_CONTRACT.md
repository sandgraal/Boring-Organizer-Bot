# B.O.B API Contract

> Local-only HTTP specification for the B.O.B FastAPI server.

**Last Updated:** 2025-12-25  
**Status:** Live (Phase 2) – this document describes the endpoints that exist in the repository today.

For the current CLI/API/UI surface and known gaps, see [`docs/CURRENT_STATE.md`](CURRENT_STATE.md).

---

## Table of Contents

1. [Overview](#overview)
2. [Deployment & Security](#deployment--security)
3. [Endpoints](#endpoints)
   1. [GET /health](#get-health)
   2. [POST /ask](#post-ask)
   3. [POST /index](#post-index)
   4. [GET /index/{job_id}](#get-indexjob_id)
   5. [GET /projects](#get-projects)
   6. [GET /documents](#get-documents)
   7. [POST /open](#post-open)
   8. [GET /settings](#get-settings)
   9. [PUT /settings](#put-settings)
   10. [POST /suggestions/{suggestion_id}/dismiss](#post-suggestionssuggestion_iddismiss)
4. [Models & Schemas](#models--schemas)
5. [Error Handling](#error-handling)
6. [Future Work](#future-work)

---

## Overview

The B.O.B API is a local-only FastAPI server that exposes the same index/retrieval/coach surfaces used by the CLI and the static web UI. Every request/response is JSON, and the server runs inside `bob/api/app.py` when you execute `bob serve`. OpenAPI docs are published at `http://localhost:8080/docs`, and the UI is mounted at `/` with assets under `/static/*`.

## Deployment & Security

- **Default binding:** `bob serve` starts Uvicorn bound to `127.0.0.1:8080`. Binding to another host prints an explicit warning (see `bob/cli/main.py:1198`).
- **Security stance:** There is no authentication because the server is assumed to run locally. CORS is whitelisted to localhost origins, and the `StaticFiles` mount is read-only (see `bob/api/app.py`).
- **Data access:** All writes (indexing jobs, Coach Mode settings, suggestion dismissals) happen through the local SQLite database inside `data/bob.db`. The CLI/serve commands guard the database path, and `.venv` or other model caches remain outside of the checked-in API contract.

## Endpoints

### GET /health

- **Purpose:** Quick status probe for dashboards and CLI health checks (`bob status` calls this indirectly).
- **Implementation:** `bob/api/routes/health.py`
- **Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "indexed_documents": 42
}
```

`indexed_documents` mirrors `db.get_stats().document_count`.

### POST /ask

- **Purpose:** Answer a natural-language query with citations and Coach Mode guidance.
- **Request model:** `AskRequest` (`bob/api/schemas.py`)
  - `query`: required string
  - `filters`: optional projects/types/date/language
  - `top_k`: int 1–20 (default from config)
  - `coach_mode_enabled`: override persisted mode
  - `coach_show_anyway`: bypass cooldowns
- **Behavior:** Delegates to `bob.retrieval.search`, formats the top chunk as the answer, builds citations (`Source`), computes date confidence, and calls `bob.coach.engine.generate_coach_suggestions`. Suggestions and outcomes are logged via `db.log_coach_suggestion`.
- **Response model:** `AskResponse`
  - `answer`: snippet from the highest-ranked chunk
  - `sources`: list of citations (source path, locator, snippet, date)
  - `suggestions`: up to three deterministic Coach Mode suggestions
  - `footer`: counts, date confidence, outdated flags, not-found metadata
  - `query_time_ms`: elapsed milliseconds
  - `coach_mode_enabled`: effective mode for this request

If no sources are returned, `answer` is `null`, `footer.not_found` is `true`, and the coach engine generates coverage suggestions (with cooldown respect).

### POST /index

- **Purpose:** Start indexing a path in the background.
- **Request model:** `IndexRequest` with `path`, `project`, and `recursive`.
- **Concurrency guard:** `IndexJobManager` enforces only one running job. A second request receives HTTP 409 with `IndexAlreadyRunningError`.
- **Processing:** `_run_index_job` (threaded) verifies the path or git URL, counts the indexable files to seed progress, streams progress updates via `IndexJobManager`, and calls `bob.index.index_paths` with the project and `"en"` language.
- **Response model:** `IndexResponse` with job metadata, zeroed errors, initial `IndexProgress`, and a `stats` object (`documents`, `chunks`, `skipped`, `errors`) that updates once the job completes.

After the background thread finishes, the job status moves to `completed` or `failed`, and downstream `GET /index/{job_id}` reports the final progress and any accumulated errors.

### GET /index/{job_id}

- **Purpose:** Poll job status.
- **Lookup:** `IndexJobManager.get_job` returns a snapshot for the requested ID.
- **Response:** `IndexResponse` mirroring `POST /index`, now including `completed_at`, aggregated `stats`, and an updated `progress`/`errors` snapshot once the job finishes.
- **Errors:** HTTP 404 when the job ID is unknown.

### GET /projects

- **Purpose:** Enumerate projects with per-project stats.
- **Implementation:** `bob/api/routes/projects.py`.
- **Response:** `ProjectListResponse` with `projects` entries containing `document_count`, `chunk_count`, and `source_types`.

### GET /documents

- **Purpose:** Paginated view into indexed documents.
- **Query params:** `project`, `source_type`, `page` (≥1), `page_size` (1–100).
- **Implementation:** `bob/api/routes/documents.py` builds SQL WHERE clauses and returns ISO-formatted timestamps.
- **Response:** `DocumentListResponse` with `documents`, `total`, `page`, and `page_size`. Each `DocumentInfo` includes the path, source type, project, and parsed `source_date`, `created_at`, `updated_at`.

### POST /open

- **Purpose:** Launch a local editor for a chunk’s source.
- **Request model:** `OpenRequest` with `file_path`, optional `line`, and optional `editor` hint.
- **Behavior:** `_get_editor_command` selects `code`, `cursor`, `vim`, `subl`, or system defaults per OS/EDITOR environment (`bob/api/routes/open.py`). It returns success when the command launches; otherwise, it replies with instructions.
- **Response model:** `OpenResponse` describing `success`, `message`, and the attempted `command`.

### GET /settings

- **Purpose:** Read persisted Coach Mode settings.
- **Implementation:** `bob/api/routes/settings.py`.
- **Response:** `CoachSettings` with `coach_mode_default`, per-project overrides, and `coach_cooldown_days`. Values come from `db.get_user_settings()`.

### PUT /settings

- **Purpose:** Update Coach Mode defaults/cooldowns.
- **Request:** `CoachSettings`.
- **Behavior:** Calls `db.update_user_settings` to persist the new defaults, overrides, and cooldown.
- **Response:** `SettingsUpdateResponse` (`success: true`).

### POST /suggestions/{suggestion_id}/dismiss

- **Purpose:** Log a dismissal to enforce cooldowns for Coach Mode suggestions.
- **Request:** `SuggestionDismissRequest` with optional `suggestion_type` and `project`. Missing values are backfilled from `db.get_suggestion_context`.
- **Behavior:** Logs `was_shown=False` via `db.log_coach_suggestion`, then returns `SuggestionDismissResponse` containing `cooldown_until`.
- **Errors:** HTTP 400 when `suggestion_type` cannot be determined from the request or stored context.

## Models & Schemas

Key models are defined in [`bob/api/schemas.py`](../bob/api/schemas.py). Examples:

- `AskRequest` / `AskResponse` describe filters, top-k, Coach Mode overrides, source metadata, and the mandatory footer.
- `Source` carries `file_path`, `source_type`, `locator`, `similarity_score`, `project`, and optional Git metadata.
- `IndexRequest` / `IndexResponse` / `IndexProgress` capture job metadata, statuses, timestamps, and per-file errors.
- `ProjectListResponse`, `DocumentListResponse`, and `DocumentInfo` provide project/document metadata for the UI.
- `OpenRequest` / `OpenResponse`, `CoachSettings`, and `SuggestionDismissRequest` round out the coaching + editor flows.

For field-level detail, consult the schema file and rely on the tests under `tests/test_api.py` to verify serialization.

## Error Handling

- **HTTPException** is raised for index conflicts (409), missing jobs (404), missing files (open returns 404), and validation issues.
- **Logging:** CLI commands (`bob serve`, `bob ask`, etc.) surface errors with rich tracebacks when `--verbose` is set. The API itself returns structured JSON errors generated by FastAPI.
- **Index job failure:** `_run_index_job` appends to `job["errors"]` and marks the job `failed`, so `GET /index/{job_id}` reports the failure plus the error list.

## Future Work

- `POST /feedback` (Helpful / Wrong / Outdated / Too long / Didn’t answer) is still planned. Feedback spikes are intended to feed the health metrics described in [`docs/IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).
- `/routines/*` endpoints remain part of the routines/Fix Queue roadmap in [`docs/ROUTINES_SPEC.md`](ROUTINES_SPEC.md). Those actions will orchestrate template writes, lint-driven Fix Queue tasks, and Coach Mode nudges once implemented.
- The Fix Queue dashboard, ingest/metadata monitors, and stale-decision radar currently have no API surface beyond `/health`; they live in the roadmap docs until landed.
