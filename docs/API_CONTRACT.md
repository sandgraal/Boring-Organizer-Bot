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
   8. [POST /routines/daily-checkin](#post-routinesdaily-checkin)
   9. [POST /routines/daily-debrief](#post-routinesdaily-debrief)
   10. [POST /routines/weekly-review](#post-routinesweekly-review)
   11. [POST /routines/meeting-prep](#post-routinesmeeting-prep)
   12. [POST /routines/meeting-debrief](#post-routinesmeeting-debrief)
   13. [POST /routines/new-decision](#post-routinesnew-decision)
   14. [POST /routines/trip-debrief](#post-routinestrip-debrief)
   15. [POST /notes/create](#post-notescreate)
   16. [GET /permissions](#get-permissions)
   17. [GET /settings](#get-settings)
   18. [PUT /settings](#put-settings)
   19. [POST /suggestions/{suggestion_id}/dismiss](#post-suggestionssuggestion_iddismiss)
   20. [POST /feedback](#post-feedback)
   21. [GET /health/fix-queue](#get-healthfix-queue)
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
  - `audit`: retrieved vs used chunks plus unsupported spans (for the Audit tab)
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

### POST /routines/daily-checkin

- **Purpose:** Generate the daily routine note by rendering `docs/templates/daily.md`, gathering cited passages for open loops and recent context, and writing `vault/routines/daily/{{YYYY-MM-DD}}.md`.
- **Implementation:** `bob/api/routes/routines.py` handles the template substitution, source rewriting, and vault write while collecting citations from two search queries before returning the rendered note plus retrieval metadata.
- **Request model:** `RoutineRequest` (`project`, `language`, `date`, `top_k` + optional `slug`/meeting/trip/decision fields that are ignored by this action).
- **Response model:** `RoutineResponse` (`routine`, `file_path`, `template`, `content`, `retrievals`, `warnings`).
- **Behavior:** The endpoint runs `search` with `"open loop"` and `"recent context"` queries (respecting `project`/`top_k`), converts the chunks into `Source` citations, records warnings when citations are missing or a previous note is overwritten, writes the filled template to the vault, and returns the note path, template path, content, retrieval buckets, and any warnings.
- **Errors:** Returns HTTP 500 if the template is missing, the retrieval search fails, or writing the note to the vault path fails. Also returns HTTP 403 (`PERMISSION_DENIED`) when the configured scope level is below 3 or the target path is outside `permissions.allowed_vault_paths`; the detail includes `scope_level`, `required_scope_level`, and `target_path`.

### POST /routines/daily-debrief

- **Purpose:** Generate the end-of-day debrief note by filling `docs/templates/daily-debrief.md`, sourcing the prior 24 hours of context and decisions, and persisting `vault/routines/daily/{{YYYY-MM-DD}}-debrief.md`.
- **Implementation:** `bob/api/routes/routines.py` invokes `_run_routine` with the `daily-debrief` action to rewrite the template’s front matter `source` tag to `routine/daily-debrief`, inject project/date/language placeholders, and drive the vault write while collecting retrieval metadata.
- **Request model:** `RoutineRequest` (`project`, `language`, `date`, `top_k` + optional `slug`/meeting/trip/decision fields that are ignored by this action).
- **Response model:** `RoutineResponse` (`routine`, `file_path`, `template`, `content`, `retrievals`, `warnings`).
- **Behavior:** The handler runs `search` for two queries—`"recent context"` and `"decisions decided today"`, each constrained to the 24-hour window ending at the requested date—and converts the results into the `recent_context` and `decisions_today` retrieval buckets containing `Source` citations. Empty retrievals add warnings advising manual capture, and overwriting an existing note adds the configured warning message before the rendered template is written to the vault. The response returns the path, template, rendered content, retrievals, and any warnings.
- **Errors:** HTTP 500 is returned when the template is missing, any search query fails, or writing the debrief note fails. HTTP 403 (`PERMISSION_DENIED`) is issued when `permissions.default_scope` is below 3 or the target path falls outside `permissions.allowed_vault_paths`; the detail object includes the offending path plus `scope_level`/`required_scope_level`.

### POST /routines/weekly-review

- **Purpose:** Create a weekly review note from `docs/templates/weekly.md`, fill in the `week_range` front matter, cite the most relevant highlights/stale decisions/metadata gaps, and persist it to `vault/routines/weekly/{{YYYY}}-W{{week}}.md`.
- **Implementation:** `bob/api/routes/routines.py` orchestrates the retrieval queries (`"weekly highlights"`, `"stale decisions"`, `"missing metadata"`), renders the template (overwriting the `source` tag with `routine/weekly-review`), writes the file with a week-based filename, and surfaces any warnings (empty retrievals or overwrites).
- **Request model:** `RoutineRequest` (`project`, `language`, `date`, `top_k` + optional `slug`/meeting/trip/decision fields that are ignored by this action).
- **Response model:** `RoutineResponse` with the same fields as daily check-in plus the collected retrieval buckets (three queries) and warnings.
- **Behavior:** Retrieval queries run in order, each producing a `RoutineRetrieval` with source citations; the handler calculates the Monday-to-Sunday `week_range`, injects it into the template, and writes the note. `warnings` capture missing citations or overwritten review notes.
- **Errors:** HTTP 500 is returned if the template is missing, any of the search queries fail, or writing the weekly note fails. HTTP 403 (`PERMISSION_DENIED`) is used when the scope level is insufficient or the target path is not covered by `permissions.allowed_vault_paths` (detail enumerates the allowed directories plus the offending `target_path`).

### POST /routines/meeting-prep

- **Purpose:** Generate a meeting prep note by rendering `docs/templates/meeting.md`, populating `meeting_date`/`participants`, gathering agenda-related citations, and writing `vault/meetings/{{project}}/{{meeting-slug}}-prep.md`.
- **Implementation:** The handler uses `_meeting_target_factory("prep")` to derive a slugified path, rewrites the template `source` tag to `routine/meeting-prep`, and runs the three queries (`"recent decisions"`, `"unresolved questions"`, `"recent notes"` with a 7-day bound) before writing the template to the vault.
- **Request model:** `RoutineRequest` with optional `meeting_slug`, `slug`, `meeting_date`, and `participants` to seed the metadata.
- **Response model:** `RoutineResponse` with retrieval buckets for each query plus warnings when citations are missing or an existing prep note is overwritten.
- **Behavior:** The handler defaults `meeting_date` to the routine date when not provided, inserts the first participant (and any extras if the template expands), and writes the note inside `vault/meetings/<sanitized-project>/<slug>-prep.md`. Each query contributes a `RoutineRetrieval`, and empty retrievals add instructions to capture context manually.
- **Errors:** Same as the other routine endpoints—HTTP 500 for missing templates/search/write failures and HTTP 403 when the configured scope `default_scope` is below 3 or the target path is outside `permissions.allowed_vault_paths`.

### POST /routines/meeting-debrief

- **Purpose:** Capture the meeting debrief with a filled `docs/templates/meeting.md`, citing meeting notes and open decisions, and persist it as `vault/meetings/{{project}}/{{meeting-slug}}-debrief.md`.
- **Implementation:** The route runs `_meeting_target_factory("debrief")`, rewrites the template’s `source` tag to `routine/meeting-debrief`, and executes the `"meeting notes"` (last 24 hours) and `"open decisions"` queries before writing to the vault.
- **Request model:** `RoutineRequest` plus the same meeting metadata hints (`meeting_slug`, `slug`, `meeting_date`, `participants`).
- **Response model:** `RoutineResponse` carrying the two retrieval buckets and any warnings.
- **Behavior:** Meeting notes retrieval is bounded to the 24 hours ending at the requested date, open decisions are surfaced regardless of time, and the participant list is rendered into the template’s `participants` block before the note is written.
- **Errors:** Mirrors the other routine endpoints—500 for missing template/search/write failures and 403 when scope or allowed paths disallow the write.

### POST /routines/new-decision

- **Purpose:** Create a structured decision record by rendering `docs/templates/decision.md`, linking evidence/conflicts, and storing it under `vault/decisions/decision-{{slug}}.md`.
- **Implementation:** `_decision_target_path` derives a slug from `decision_slug`, `slug`, or the provided `title` (falling back to the date) and rewrites the template’s `source` tag to `routine/new-decision`. Two queries—`"related decision sources"` and `"conflicting decisions"`—populate the retrieval buckets.
- **Request model:** `RoutineRequest` with optional `decision_slug`, `slug`, and `title` fields to influence the filename and narrative.
- **Response model:** `RoutineResponse` with the two retrieval buckets and warnings for missing citations/overwrites.
- **Behavior:** The slug is sanitized to avoid unsafe filenames, retrievals are attached as evidence/conflicts, and the resulting file always lives under `vault/decisions/`.
- **Errors:** HTTP 500 for template/search/write failures and HTTP 403 for insufficient `default_scope` or disallowed vault paths.

### POST /routines/trip-debrief

- **Purpose:** Document a trip debrief by rendering `docs/templates/trip.md`, injecting the trip name, and saving `vault/trips/{{trip-slug}}/debrief.md`.
- **Implementation:** `_trip_target_path` builds the destination folder from `trip_slug`, `slug`, or a sanitized version of `trip_name`, rewrites the template’s `source` tag to `routine/trip-debrief`, and runs three queries (`"trip notes"` capped at the last 30 days, `"trip recipes"`, `"trip open loops"`) to gather context.
- **Request model:** `RoutineRequest` with optional `trip_name`, `trip_slug`, and `slug`.
- **Response model:** `RoutineResponse` holding the retrieval buckets and warnings.
- **Behavior:** The handler ensures `trip_name` is populated in the template, the `trip notes` query honors the 30-day lookback, and the note is written under the slugified trip folder.
- **Errors:** Same 500/403 semantics as the other routine endpoints when templates/searches/writes fail or scope/path checks reject the action.

### POST /notes/create

- **Purpose:** Render a canonical template and write a note to an allowed vault path.
- **Request model:** `NoteCreateRequest` with `template`, `target_path`, optional `project`/`language`/`date`, and optional `values` for template placeholders.
- **Response model:** `NoteCreateResponse` returning the resolved template path, rendered content, and overwrite warnings.
- **Behavior:** Resolves templates from `docs/templates/`, fills `project`/`date`/`language` defaults plus any provided values, and writes to `target_path` (relative paths resolve under the configured vault). Scope and allowed-path checks mirror routine endpoints.
- **Errors:** HTTP 400 for missing template/target path, 404 when the template does not exist, 403 for permission scope/path denials, and 500 for write failures.

### GET /permissions

- **Purpose:** Surface current permission scope and allowed vault paths for UI visibility.
- **Implementation:** `bob/api/routes/permissions.py`.
- **Response model:** `PermissionsResponse` with `default_scope`, `enabled_connectors`, `allowed_vault_paths`, and `vault_root`.
- **Behavior:** Mirrors the configured permission block so the UI can show scope status and allowed write directories without mutating state.

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

### POST /feedback

- **Purpose:** Capture the five inline feedback signals (Helpful, Wrong or missing source, Outdated, Too long, Didn’t answer) so that failure metrics and Fix Queue tasks reflect user pain points.
- **Implementation:** `bob/api/routes/feedback.py` calls `db.log_feedback` and stores `{question, project, answer_id, feedback_reason, retrieved_source_ids}` in the `feedback_log` table for later aggregation.
- **Request model:** `FeedbackRequest` (`question`, optional `project`, `answer_id`, `feedback_reason`, `retrieved_source_ids`).
- **Response model:** `FeedbackResponse` (`success: true`).
- **Behavior:** UI feedback buttons render `feedback_reason` enumerations (`helpful`, `wrong_source`, `outdated`, `too_long`, `didnt_answer`) and include the chunk IDs that were shown so the Fix Queue can reference the same citations when it surfaces tasks.

### GET /health/fix-queue

- **Purpose:** Provide the health dashboard and Fix Queue with failure signals (not-found frequency, metadata deficits, stale notes/decisions, repeated questions, permission denials, low indexed volume, low retrieval hit rate) plus actionable tasks derived from those signals.
- **Query params:** Optional `project` filters failure signals and tasks to a single project when provided.
- **Implementation:** The `/health/fix-queue` handler in `bob/api/routes/health.py` calls `db.get_feedback_metrics(project)`, `db.get_documents_missing_metadata(project)`, `db.get_permission_denial_metrics(project)`, `db.get_project_document_counts(project)`, and `db.get_search_history_stats(..., project)` to build `FixQueueResponse`.
- **Response model:** `FixQueueResponse` with `failure_signals` (instances of `FailureSignal`) and `tasks` (instances of `FixQueueTask`).
- **Behavior:** 
  - `failure_signals` include `not_found_frequency`, `metadata_deficits`, `metadata_top_offenders`, `stale_notes`, `stale_decisions`, `repeated_questions`, `permission_denials`, `low_indexed_volume`, and `low_retrieval_hit_rate`, each with counts/details that the UI can render directly.
  - `failure_signals` now also include `ingestion_errors`, summarizing parse/no-text failures with recent file previews.
  - `tasks` are prioritized actions such as `run_routine` for high not-found ratios, `fix_metadata` for documents missing `source_date`/`project`/`language`, and `run_query` for repeated queries (question text is the target).
  - `tasks` include an optional `project` field when a failure signal is project-specific, so the UI can scope routines and queries.
  - Capture lint issues generate `fix_capture` tasks that point at the offending vault note paths with a reason describing the missing sections or metadata.
  - Permission denials create `raise_scope` (target `permissions.default_scope`) and `allow_path` (target is the blocked path) tasks.
  - Task IDs are deterministic (`not-found-<project>`, `metadata-<doc>-<index>`, `repeat-<hash>`, `permission-<hash>`, `lint-<code>-<hash>`) so that UI state can track dismissals or completions.
- **Example response:**

```json
{
  "failure_signals": [
    {
      "name": "not_found_frequency",
      "value": 0.3,
      "details": "3 of 10 feedback entries were 'didn't answer'"
    },
    {
      "name": "metadata_deficits",
      "value": 1,
      "details": "Documents missing source_date/project/language"
    },
    {
      "name": "metadata_top_offenders",
      "value": 1,
      "details": "Top project: docs (1)"
    },
    {
      "name": "stale_notes",
      "value": 4,
      "details": "Notes older than 90d+: 4, 180d+: 2, 365d+: 1"
    },
    {
      "name": "stale_decisions",
      "value": 2,
      "details": "Decisions older than 90d+: 2, 180d+: 1, 365d+: 0"
    },
    {
      "name": "ingestion_errors",
      "value": 1,
      "details": "parse error: 1. Recent: broken.pdf"
    },
    {
      "name": "repeated_questions",
      "value": 1,
      "details": "Repeated queries observed over the past 48 hours"
    },
    {
      "name": "permission_denials",
      "value": 1,
      "details": "1 scope denials in the last 168h"
    },
    {
      "name": "low_indexed_volume",
      "value": 1,
      "details": "1 project under 5 docs: docs (2)"
    },
    {
      "name": "low_retrieval_hit_rate",
      "value": 1,
      "details": "1 project below 40% hit rate: docs (20% hits)"
    }
  ],
  "tasks": [
    {
      "id": "not-found-global",
      "action": "run_routine",
      "target": "routines/daily-checkin",
      "reason": "30.0% of feedback entries were 'didn't answer'",
      "priority": 3
    },
    {
      "id": "metadata-100-1",
      "action": "fix_metadata",
      "target": "/docs/notes.md",
      "project": "docs",
      "reason": "Missing metadata fields: source_date",
      "priority": 3
    },
    {
      "id": "repeat-abcdef",
      "action": "run_query",
      "target": "Where is the API?",
      "project": "docs",
      "reason": "Question repeated 2 times in the last 48h",
      "priority": 2
    },
    {
      "id": "permission-7ac1c2d9",
      "action": "raise_scope",
      "target": "permissions.default_scope",
      "reason": "Routine 'daily-checkin' blocked at scope 2; requires 3 for /vault/routines/daily/2025-01-01.md",
      "priority": 2
    }
  ]
}
```

## Models & Schemas

Key models are defined in [`bob/api/schemas.py`](../bob/api/schemas.py). Examples:

- `AskRequest` / `AskResponse` describe filters, top-k, Coach Mode overrides, source metadata, and the mandatory footer.
- `CoachSuggestion` includes optional `routine_action` values (for example, `daily-checkin` or `weekly-review`) so the UI can trigger routines directly from Coach Mode suggestions.
- `Source` carries `file_path`, `source_type`, `locator`, `similarity_score`, `project`, and optional Git metadata.
- `RoutineRequest` / `RoutineResponse` cover all `/routines/*` actions: base fields (`project`, `language`, `date`, `top_k`) plus optional `slug`, `meeting_slug`, `meeting_date`, `participants`, `trip_name`, `trip_slug`, `decision_slug`, and `title`, and the rendered note path/content + retrieval buckets + warnings returned.
- `NoteCreateRequest` / `NoteCreateResponse` capture template name, target path, placeholder values, and the rendered note content for manual template writes.
- `IndexRequest` / `IndexResponse` / `IndexProgress` capture job metadata, statuses, timestamps, and per-file errors.
- `ProjectListResponse`, `DocumentListResponse`, and `DocumentInfo` provide project/document metadata for the UI.
- `OpenRequest` / `OpenResponse`, `CoachSettings`, and `SuggestionDismissRequest` round out the coaching + editor flows.

For field-level detail, consult the schema file and rely on the tests under `tests/test_api.py` to verify serialization.

## Error Handling

- **HTTPException** is raised for index conflicts (409), missing jobs (404), missing files (open returns 404), and validation issues.
- **Logging:** CLI commands (`bob serve`, `bob ask`, etc.) surface errors with rich tracebacks when `--verbose` is set. The API itself returns structured JSON errors generated by FastAPI.
- **Index job failure:** `_run_index_job` appends to `job["errors"]` and marks the job `failed`, so `GET /index/{job_id}` reports the failure plus the error list.

## Future Work

- The Routine/Fix Queue UI surfaces and coach-driven automation that guide users through the `/routines/*` endpoints (and surface lint/metadata remediation suggestions) remain part of the roadmap documented in [`docs/ROUTINES_SPEC.md`](ROUTINES_SPEC.md).
- The Fix Queue dashboard, ingest/metadata monitors, and stale-decision radar still need UI surfaces, but they can consume the failure signals that `GET /health/fix-queue` now exposes.
