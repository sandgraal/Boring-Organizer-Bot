# B.O.B API Contract

> HTTP API specification for local-only B.O.B server.

**Last Updated:** 2025-12-24  
**Status:** Implemented (Phase 2 Complete)  
**Version:** 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Security Stance](#security-stance)
3. [Base Configuration](#base-configuration)
4. [Endpoints](#endpoints)
5. [Request/Response Schemas](#requestresponse-schemas)
6. [Error Handling](#error-handling)
7. [Example Payloads](#example-payloads)

---

## Overview

The B.O.B API is a **local-only HTTP API** that exposes core functionality to the web interface. It is designed for single-user operation on a local machine.

### Design Principles

1. **Local-only**: Binds to `127.0.0.1` only. Never exposed to network.
2. **Stateless requests**: Each request is independent. No sessions.
3. **Job-based async**: Long operations return job IDs for polling.
4. **Structured citations**: Every answer includes machine-readable source data.
5. **Explicit failures**: Clear error responses, never empty or ambiguous.

### Tech Stack

- **Framework**: FastAPI
- **Server**: Uvicorn (single process)
- **Data**: JSON request/response
- **Auth**: None (local-only assumption)

---

## Security Stance

### Local-Only Binding

The server MUST bind to `127.0.0.1` only:

```python
uvicorn.run(app, host="127.0.0.1", port=8080)
```

### No Remote Exposure

- Default configuration rejects non-localhost connections
- No authentication/authorization implemented (not needed for local)
- CORS allows `http://localhost:*` for development

### Security Non-Goals

- Multi-user authentication
- HTTPS (local traffic only)
- Rate limiting (single user)
- API keys or tokens

### Optional: Remote Access

If a user explicitly wants remote access (not recommended):

1. Bind to `0.0.0.0` via config override
2. User takes full responsibility for security
3. Document warnings prominently

---

## Base Configuration

### Default Settings

```yaml
api:
  host: "127.0.0.1"
  port: 8080
  cors_origins:
    - "http://localhost:8080"
    - "http://127.0.0.1:8080"
```

### Server Start

```bash
# Start the server
bob serve

# Start on custom port
bob serve --port 9000

# Start with verbose logging
bob serve --verbose
```

### Health Check

```
GET /health
```

Returns:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "indexed_documents": 156
}

---

## Endpoints

### Query Endpoints

#### `POST /ask`

Submit a question and receive an answer with structured citations.

**Request:**

```json
{
  "query": "How do I configure logging?",
  "filters": {
    "projects": ["docs", "notes"],
    "types": ["markdown", "pdf"],
    "date_after": "2025-01-01",
    "date_before": null,
    "language": null
  },
  "top_k": 5,
  "coach_mode_enabled": false,
  "coach_show_anyway": false,
  "include_audit": true,
  "include_report": true,
  "report_format": "markdown"
}
```

**Coach Mode:**

- `coach_mode_enabled` is optional; if omitted, server uses persisted settings.
- `coach_show_anyway` bypasses Coach Mode cooldown checks for this request.

**Response:**

```json
{
  "answer": "To configure logging, edit the `config.yaml` file [1] and set the `log_level` field to your desired level [2].",
  "coach_mode_enabled": false,
  "suggestions": [],
  "report": {
    "format": "markdown",
    "content": "..."
  },
  "sources": [
    {
      "id": 1,
      "document_id": 42,
      "file_path": "docs/configuration.md",
      "file_type": "markdown",
      "locator": {
        "type": "heading",
        "heading": "Logging Configuration",
        "start_line": 45,
        "end_line": 67
      },
      "snippet": "The logging configuration section allows you to...",
      "date": "2025-12-15",
      "date_confidence": "HIGH",
      "project": "docs",
      "may_be_outdated": false,
      "similarity_score": 0.92
    },
    {
      "id": 2,
      "document_id": 43,
      "file_path": "docs/reference.md",
      "file_type": "markdown",
      "locator": {
        "type": "heading",
        "heading": "Config Fields",
        "start_line": 120,
        "end_line": 145
      },
      "snippet": "log_level: Sets the minimum log level. Options: DEBUG...",
      "date": "2025-06-10",
      "date_confidence": "MEDIUM",
      "project": "docs",
      "may_be_outdated": true,
      "similarity_score": 0.87
    }
  ],
  "audit": {
    "retrieved": [
      {
        "chunk_id": 101,
        "rank": 1,
        "score": 0.92,
        "used": true,
        "locator": {
          "type": "heading",
          "heading": "Logging Configuration",
          "start_line": 45,
          "end_line": 67
        }
      }
    ],
    "used_chunk_ids": [101, 102],
    "unsupported_claims": []
  },
  "footer": {
    "source_count": 2,
    "date_confidence": "MEDIUM",
    "may_be_outdated": true,
    "outdated_source_count": 1
  },
  "query_time_ms": 127
}
```

**Coach Mode fields:**

- `coach_mode_enabled` reflects the effective mode used for the response.
- `suggestions` is empty when Coach Mode is disabled or no suggestions pass gates.
- `suggestions` entries may include `routine_action` so the UI can link to `/routines/<action>` when reporting evidence or hypotheses.
- `include_audit` returns an `audit` payload with retrieved/used/unsupported info.
- `include_report` returns a formatted `report` payload for "copy as report".

**Not Found Response:**

```json
{
  "answer": null,
  "coach_mode_enabled": true,
  "suggestions": [
    {
      "id": "sug_coverage_gaps_8f2a",
      "type": "coverage_gaps",
      "text": "Index the project notes that cover logging configuration and tag them under the relevant project.",
      "why": "No sources matched this query, so adding or indexing coverage will enable grounded answers.",
      "hypothesis": true
    }
  ],
  "sources": [],
  "footer": {
    "source_count": 0,
    "date_confidence": null,
    "may_be_outdated": false,
    "outdated_source_count": 0,
    "not_found": true,
    "not_found_message": "No indexed documents contain information matching your query."
  },
  "query_time_ms": 45
}


### Routine Endpoints

Routine endpoints run predefined workflows, surface the retrieval context that triggered them, and write with the templates described in `docs/ROUTINES_SPEC.md`. Each action accepts:

```json
{
  "project": "docs",
  "metadata": {
    "date": "2025-12-24",
    "language": "en",
    "source": "routine/daily-checkin"
  },
  "context": {
    "meeting_slug": "weekly-sync",
    "trip_name": "weekend-trip"
  },
  "filters": {
    "topics": ["open_loops"]
  },
  "coach_mode_enabled": false
}
```

The response includes:

- `written_file`: path written (null for Fix Queue refresh).
- `retrieved_context`: citations (locator, snippet, similarity_score).
- `lint_issues`: hygiene flags (`missing_rejected_options`, `missing_metadata`, `missing_next_actions`).
- `suggestions`: optional Coach Mode follow-ups.

Supported actions:

- `POST /routines/daily-checkin`: writes `vault/routines/daily/YYYY-MM-DD.md`, queries `open_loops(status=proposed)` and `recent_context(days=3)`, and shows morning priorities plus open loops with citations; missing metadata or low-confidence sources keep the note in review.
- `POST /routines/end-of-day-debrief`: captures lessons, open loops, and decisions modified today via `decisions(modified=today)` and the day’s context.
- `POST /routines/meeting-prep`: builds agenda bullets from `last_decisions(project)` and `open_questions(project)`, saves to `vault/meetings/<project>/<meeting-slug>-prep.md`, and returns relevant notes.
- `POST /routines/meeting-debrief`: creates or updates `vault/decisions/decision-<slug>.md`, records rejected options, next actions, and links to retrieved evidence; it returns the `decision_id` for downstream lookups.
- `POST /routines/weekly-review`: writes `vault/routines/weekly/YYYY-WW.md`, highlights stale decisions (`decisions(older_than=6m)`), and points to metadata gaps.
- `POST /routines/new-decision`: enforces Decision/Context/Evidence/Rejected Options/Next Actions sections, links retrieved sources, and optionally marks `supersedes`.
- `POST /routines/trip-debrief`: writes `vault/trips/<trip>/debrief.md` with learnings and reusable checklist seeds derived from `trip_notes`.
- `POST /routines/fix-queue`: refreshes the Fix Queue (`GET /health/fix-queue`) and returns prioritized tasks (metadata fixes, ingestion errors, repeated questions) without writing a new file.

Every routine checks the caller’s permission level (`docs/PERMISSIONS.md`) before writing; failures surface as structured errors and feed the Fix Queue metrics.

#### Example: Daily Check-in

```bash
curl -X POST http://localhost:8080/routines/daily-checkin \
  -H "Content-Type: application/json" \
  -d '{
    "project": "docs",
    "metadata": { "date": "2025-12-24", "language": "en", "source": "routine/daily-checkin" },
    "filters": { "topics": ["open loops"] }
  }'
```

```json
{
  "written_file": "vault/routines/daily/2025-12-24.md",
  "retrieved_context": [
    {
      "file_path": "docs/decisions.md",
      "locator": { "heading": "Open Loops", "start_line": 30 },
      "snippet": "Decision DEC-010 requires follow-up on the migration plan.",
      "similarity_score": 0.88
    }
  ],
  "lint_issues": [],
  "coach_mode_enabled": false
}
```

---

### Indexing Endpoints

#### `POST /index`

Start an indexing job for a path.

**Request:**

```json
{
  "path": "/Users/me/Documents/notes",
  "project": "notes",
  "recursive": true
}
```

**Response:**

```json
{
  "job_id": "idx_a1b2c3d4",
  "status": "started",
  "path": "/Users/me/Documents/notes",
  "project": "notes",
  "started_at": "2025-12-23T10:30:00Z"
}
```

**Error (already running):**

```json
{
  "error": {
    "code": "INDEX_JOB_RUNNING",
    "message": "An indexing job is already running. Wait for completion or cancel it.",
    "current_job_id": "idx_x9y8z7"
  }
}
```

---

#### `GET /index/{job_id}`

Get status of an indexing job.

**Response (in progress):**

```json
{
  "job_id": "idx_a1b2c3d4",
  "status": "running",
  "path": "/Users/me/Documents/notes",
  "project": "notes",
  "started_at": "2025-12-23T10:30:00Z",
  "progress": {
    "total_files": 75,
    "processed_files": 34,
    "percent": 45,
    "current_file": "meeting-notes-dec.md"
  },
  "errors": [
    {
      "file": "corrupt.pdf",
      "error": "Failed to parse PDF: file appears corrupted"
    }
  ]
}
```

**Response (completed):**

```json
{
  "job_id": "idx_a1b2c3d4",
  "status": "completed",
  "path": "/Users/me/Documents/notes",
  "project": "notes",
  "started_at": "2025-12-23T10:30:00Z",
  "completed_at": "2025-12-23T10:32:15Z",
  "progress": {
    "total_files": 75,
    "processed_files": 75,
    "percent": 100,
    "current_file": null
  },
  "summary": {
    "files_indexed": 73,
    "files_skipped": 0,
    "files_failed": 2,
    "chunks_created": 412
  },
  "errors": [
    {
      "file": "corrupt.pdf",
      "error": "Failed to parse PDF: file appears corrupted"
    },
    {
      "file": "empty.md",
      "error": "No content extracted from file"
    }
  ]
}
```

---

#### `DELETE /index/{job_id}`

Cancel a running indexing job.

**Response:**

```json
{
  "job_id": "idx_a1b2c3d4",
  "status": "cancelled",
  "message": "Job cancelled. Partial results have been saved."
}
```

---

### Document Endpoints

#### `GET /projects`

List all projects with document counts.

**Response:**

```json
{
  "projects": [
    {
      "name": "docs",
      "document_count": 45,
      "chunk_count": 312,
      "last_indexed": "2025-12-23T10:30:00Z"
    },
    {
      "name": "recipes",
      "document_count": 23,
      "chunk_count": 89,
      "last_indexed": "2025-12-22T14:15:00Z"
    },
    {
      "name": "work",
      "document_count": 88,
      "chunk_count": 567,
      "last_indexed": "2025-12-20T09:00:00Z"
    }
  ],
  "total_documents": 156,
  "total_chunks": 968
}
```

---

#### `GET /documents`

List documents with optional filters.

**Query Parameters:**

| Parameter  | Type   | Description                  |
| ---------- | ------ | ---------------------------- |
| `project`  | string | Filter by project name       |
| `type`     | string | Filter by document type      |
| `after`    | date   | Documents dated after this   |
| `before`   | date   | Documents dated before this  |
| `search`   | string | Search in file paths         |
| `page`     | int    | Page number (default: 1)     |
| `per_page` | int    | Items per page (default: 20) |

**Response:**

```json
{
  "documents": [
    {
      "id": 42,
      "source_path": "docs/configuration.md",
      "source_type": "markdown",
      "project": "docs",
      "language": "en",
      "source_date": "2025-12-15",
      "chunk_count": 8,
      "indexed_at": "2025-12-23T10:30:00Z",
      "may_be_outdated": false
    },
    {
      "id": 43,
      "source_path": "docs/reference.md",
      "source_type": "markdown",
      "project": "docs",
      "language": "en",
      "source_date": "2025-06-10",
      "chunk_count": 15,
      "indexed_at": "2025-12-23T10:30:00Z",
      "may_be_outdated": true
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 8,
    "total_documents": 156
  }
}
```

---

#### `GET /documents/{id}`

Get detailed information about a single document.

**Response:**

```json
{
  "id": 42,
  "source_path": "docs/configuration.md",
  "source_type": "markdown",
  "project": "docs",
  "language": "en",
  "source_date": "2025-12-15",
  "indexed_at": "2025-12-23T10:30:00Z",
  "content_hash": "sha256:a1b2c3d4...",
  "chunks": [
    {
      "id": 101,
      "locator": {
        "type": "heading",
        "heading": "Overview",
        "start_line": 1,
        "end_line": 15
      },
      "token_count": 156,
      "preview": "Configuration allows you to customize..."
    },
    {
      "id": 102,
      "locator": {
        "type": "heading",
        "heading": "Logging Configuration",
        "start_line": 45,
        "end_line": 67
      },
      "token_count": 234,
      "preview": "The logging section controls how B.O.B..."
    }
  ]
}
```

---

### Health Dashboard

#### `GET /health`

Return coverage, hygiene, staleness, ingestion, and failure metrics plus the Fix Queue task list. Failure signals include Not found frequency, PDF ingestion errors, missing metadata counts, and repeated questions; these signals seed the Fix Queue algorithm described in `docs/ROUTINES_SPEC.md`.

**Response:**

```json
{
  "coverage": {
    "low_volume_projects": ["cdc", "travel"],
    "low_hit_projects": ["construction"]
  },
  "metadata_hygiene": {
    "missing_project": 4,
    "missing_date": 12,
    "missing_language": 1,
    "missing_source": 2
  },
  "staleness": {
    "over_6_months": 18,
    "over_12_months": 6
  },
  "ingestion_failures": [
    { "file": "broken.pdf", "error_type": "no_text" }
  ],
  "failure_signals": {
    "not_found_frequency": [
      { "project": "docs", "value": 0.12 }
    ],
    "pdf_no_text": [
      { "file": "vault/reports/broken.pdf", "count": 2 }
    ],
    "missing_metadata_counts": {
      "project": "docs",
      "missing_date": 3,
      "missing_language": 1,
      "missing_source": 2
    },
    "repeated_questions": [
      { "query": "how to configure logging", "count": 3 }
    ]
  },
  "fix_queue": [
    {
      "id": "fix_001",
      "action": "fix_metadata",
      "target": "/notes/2022/decision.md",
      "reason": "missing_date",
      "priority": "high"
    }
  ]
}
```

#### `GET /health/fix-queue`

Return only the prioritized Fix Queue tasks derived from lint issues, ingestion failures, repeated questions, and metadata gaps. Each task records `id`, `action`, `target`, `reason`, and `priority` so routines can act on the top problems before optional generation layers ship.

**Response:**

```json
{
  "fix_queue": [
    {
      "id": "fix_002",
      "action": "run_routine",
      "target": "traceable-decision",
      "reason": "missing_rejected_options",
      "priority": "medium"
    }
  ]
}
```

---

### Feedback Endpoint

#### `POST /feedback`

Log user feedback from the Ask UI buttons (Helpful / Wrong or missing source / Outdated / Too long / Didn’t answer). The API stores the feedback locally and the Fix Queue/health dashboards surface aggregate counts.

**Request:**

```json
{
  "question": "How do I configure logging?",
  "answer_id": "ans_123",
  "project": "docs",
  "feedback_reason": "wrong_or_missing_source",
  "retrieved_sources": [
    {
      "file_path": "docs/configuration.md",
      "locator": { "heading": "Logging Configuration", "start_line": 45 }
    }
  ]
}
```

**Response:**

```json
{
  "success": true,
  "feedback_id": "fb_2025_12_24_0900"
}
```

Aggregated feedback counts contribute to the `failure_signals.not_found_frequency` and repeated question metrics described above.

---

### Templates and Notes

#### `GET /templates`

List built-in templates.

**Response:**

```json
{
  "templates": [
    { "id": "decision", "title": "Decision", "description": "Decision record" },
    { "id": "experiment", "title": "Experiment", "description": "Evaluation log" }
  ]
}
```

#### `POST /notes/create`

Create a new note from a template. The API renders canonical templates under `docs/templates/`, fills metadata placeholders, enforces allowed vault paths, and requires a template-write scope (Level 3 or higher from `docs/PERMISSIONS.md`).

**Request:**

```json
{
  "template_id": "decision",
  "project": "cdc",
  "title": "Data retention policy",
  "target_path": "/vault/cdc/decisions/decision-2025-12-24.md",
  "metadata": {
    "date": "2025-12-24",
    "language": "en",
    "source": "template/decision"
  }
}
```

**Response:**

```json
{
  "success": true,
  "file_path": "/vault/cdc/decisions/decision-2025-12-24.md"
}
```

If the caller lacks Level 3 scope or requests a target outside the approved vault directories, the API returns `PERMISSION_DENIED` and logs the denied intent in the Fix Queue metrics.

#### `POST /lint`

Lint a note for missing required sections.

**Request:**

```json
{
  "file_path": "/vault/cdc/decisions/decision-2025-12-24.md"
}
```

**Response:**

```json
{
  "issues": [
    { "type": "missing_rationale", "message": "Decision has no rationale section." }
  ]
}
```

Lint results are surfaced in the Fix Queue and Coach Mode suggestions so the user can act on capture hygiene issues (e.g., run a routine to fill missing rejected options).

---

### Connectors (Opt-in)

#### `POST /connectors/bookmarks/import`

Import browser HTML bookmarks into the vault.

**Request:**

```json
{
  "file_path": "/Downloads/bookmarks.html",
  "project": "bookmarks"
}
```

**Response:**

```json
{
  "imported": 124,
  "created_files": 18
}
```

#### `POST /connectors/highlights`

Save a manual highlight to the vault.

**Request:**

```json
{
  "text": "Key paragraph...",
  "source_url": "https://example.com/article",
  "project": "research"
}
```

**Response:**

```json
{
  "success": true,
  "file_path": "/vault/research/highlights/2025-12-24.md"
}
```

#### `POST /connectors/pdf-annotations/import`

Import local PDF annotations (optional).

**Request:**

```json
{
  "file_path": "/vault/annotations/export.json",
  "project": "research"
}
```

**Response:**

```json
{
  "imported": 42,
  "linked_pdfs": 3
}
```

---

### Evaluation Endpoints

#### `POST /eval/run`

Run evaluation on golden sets.

**Request:**

```json
{
  "golden_sets": ["food", "travel", "cdc"],
  "baseline": false
}
```

**Response:**

```json
{
  "run_id": "eval_2025_12_24_0900",
  "status": "started"
}
```

#### `GET /eval/runs`

List evaluation runs.

**Response:**

```json
{
  "runs": [
    { "id": "eval_2025_12_24_0900", "status": "completed", "baseline": false }
  ]
}
```

#### `GET /eval/runs/{id}`

Get evaluation metrics and per-domain summaries.

#### `GET /eval/diff`

Compare two evaluation runs for drift.

---

### Settings Endpoints

#### `GET /settings`

Return persisted user settings, including Coach Mode defaults.

**Response:**

```json
{
  "coach_mode_default": "boring",
  "per_project_mode": {
    "docs": "coach",
    "work": "boring"
  },
  "coach_cooldown_days": 7,
  "vault_path": "/vault",
  "audit_mode_default": "summary",
  "connectors": {
    "bookmarks_import_enabled": true,
    "highlights_enabled": true,
    "pdf_annotations_enabled": false
  }
}
```

---

#### `PUT /settings`

Update persisted user settings.

**Request:**

```json
{
  "coach_mode_default": "coach",
  "per_project_mode": {
    "docs": "coach",
    "work": "boring"
  },
  "coach_cooldown_days": 7,
  "vault_path": "/vault",
  "audit_mode_default": "summary",
  "connectors": {
    "bookmarks_import_enabled": true,
    "highlights_enabled": true,
    "pdf_annotations_enabled": false
  }
}
```

**Response:**

```json
{
  "success": true
}
```

---

#### `POST /suggestions/{suggestion_id}/dismiss`

Record a dismissal to enforce cooldown rules.

**Request (optional):**

```json
{
  "suggestion_type": "coverage_gaps",
  "project": "docs"
}
```

**Response:**

```json
{
  "success": true,
  "cooldown_until": "2026-01-01T00:00:00Z"
}
```

---

### Decision Endpoints

#### `GET /decisions`

List extracted decisions.

**Query Parameters:**

| Parameter | Type   | Description                           |
| --------- | ------ | ------------------------------------- |
| `status`  | string | Filter: `proposed`, `decided`, `superseded`, `obsolete`, `all` |
| `project` | string | Filter by project                     |
| `search`  | string | Search in decision text               |
| `older_than` | string | Age filter like `6m`, `1y`         |
| `page`    | int    | Page number                           |

**Response:**

```json
{
  "decisions": [
    {
      "id": "DEC-001",
      "decision_text": "Use SQLite for all local storage",
      "context": "We evaluated PostgreSQL, SQLite, and file-based storage. SQLite was chosen for portability and zero-config operation.",
      "status": "decided",
      "decision_date": "2025-12-01",
      "source": {
        "document_id": 42,
        "file_path": "docs/architecture.md",
        "locator": {
          "type": "heading",
          "heading": "Database Choice",
          "start_line": 89,
          "end_line": 102
        }
      },
      "superseded_by": null
    },
    {
      "id": "DEC-002",
      "decision_text": "Use PostgreSQL for storage",
      "context": "Initial decision before portability concerns were raised.",
      "status": "superseded",
      "decision_date": "2023-11-15",
      "source": {
        "document_id": 58,
        "file_path": "docs/old-decisions.md",
        "locator": {
          "type": "heading",
          "heading": "Initial Database Decision",
          "start_line": 12,
          "end_line": 25
        }
      },
      "superseded_by": "DEC-001"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 1,
    "total_decisions": 2
  }
}
```

---

### Recipe Endpoints

#### `GET /recipes`

List structured recipes (if indexed).

**Response:**

```json
{
  "recipes": [
    {
      "id": 1,
      "title": "Pasta Carbonara",
      "description": "Classic Italian pasta dish",
      "prep_time_minutes": 15,
      "cook_time_minutes": 20,
      "servings": 4,
      "difficulty": "easy",
      "source": {
        "document_id": 101,
        "file_path": "recipes/carbonara.yaml"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 2,
    "total_recipes": 23
  }
}
```

---

#### `GET /recipes/{id}`

Get full recipe details.

**Response:**

```json
{
  "id": 1,
  "title": "Pasta Carbonara",
  "description": "Classic Italian pasta dish with eggs, cheese, and pancetta",
  "prep_time_minutes": 15,
  "cook_time_minutes": 20,
  "servings": 4,
  "difficulty": "easy",
  "ingredients": [
    { "item": "spaghetti", "amount": "400g" },
    { "item": "pancetta", "amount": "200g" },
    { "item": "eggs", "amount": "4" },
    { "item": "parmesan", "amount": "100g, grated" },
    { "item": "black pepper", "amount": "to taste" }
  ],
  "instructions": [
    "Bring a large pot of salted water to boil",
    "Cook pasta according to package directions",
    "Meanwhile, cook pancetta until crispy",
    "Whisk eggs with cheese and pepper",
    "Toss hot pasta with egg mixture and pancetta",
    "Serve immediately"
  ],
  "source": {
    "document_id": 101,
    "file_path": "recipes/carbonara.yaml",
    "indexed_at": "2025-12-22T14:15:00Z"
  }
}
```

---

### File Opening

#### `POST /open`

Request to open a file at a specific locator.

**Request:**

```json
{
  "file_path": "docs/configuration.md",
  "locator": {
    "type": "heading",
    "start_line": 45
  }
}
```

**Response (success):**

```json
{
  "success": true,
  "action": "opened",
  "message": "File opened in default editor"
}
```

**Response (file not found):**

```json
{
  "success": false,
  "action": "not_found",
  "message": "File does not exist at specified path",
  "fallback": {
    "path": "docs/configuration.md",
    "locator_description": "Line 45 (heading: Logging Configuration)"
  }
}
```

**Response (cannot open):**

```json
{
  "success": false,
  "action": "no_handler",
  "message": "No application available to open this file type",
  "fallback": {
    "path": "/full/path/to/docs/configuration.md",
    "locator_description": "Line 45 (heading: Logging Configuration)",
    "instruction": "Open this file manually and navigate to line 45"
  }
}
```

---

## Request/Response Schemas

### Common Types

#### `Locator`

```typescript
interface Locator {
  type: "heading" | "page" | "paragraph" | "sheet" | "section" | "line";

  // For heading/line
  heading?: string;
  start_line?: number;
  end_line?: number;

  // For page (PDF)
  page?: number;
  total_pages?: number;

  // For paragraph (Word)
  paragraph_index?: number;
  parent_heading?: string;

  // For sheet (Excel)
  sheet_name?: string;
  row_count?: number;

  // For section (Recipe)
  section?: string;

  // For git
  git_file?: string;
  git_commit?: string;
}
```

#### `DateConfidence`

```typescript
type DateConfidence = "HIGH" | "MEDIUM" | "LOW";

// HIGH: Source date within last 3 months
// MEDIUM: Source date 3-6 months ago
// LOW: Source date more than 6 months ago, or unknown
```

#### `Source`

```typescript
interface Source {
  id: number;
  document_id: number;
  file_path: string;
  file_type: "markdown" | "pdf" | "word" | "excel" | "recipe" | "git";
  locator: Locator;
  snippet: string;
  date: string | null;
  date_confidence: DateConfidence;
  project: string;
  may_be_outdated: boolean;
  similarity_score: number;
}
```

#### `Report`

```typescript
interface Report {
  format: "markdown" | "text";
  content: string;
}
```

#### `AnswerAudit`

```typescript
interface AnswerAudit {
  retrieved: Array<{
    chunk_id: number;
    rank: number;
    score: number;
    used: boolean;
    locator: Locator;
  }>;
  used_chunk_ids: number[];
  unsupported_claims: Array<{
    text: string;
    reason: string;
    matched_source_ids?: number[];
  }>;
}
```

#### `CoachMode`

```typescript
type CoachMode = "boring" | "coach";
```

#### `SuggestionType`

```typescript
type SuggestionType =
  | "capture_hygiene"
  | "staleness"
  | "coverage_gaps"
  | "system_improvements"
  | "workflow_nudges";
```

#### `CoachSuggestion`

```typescript
interface CoachSuggestion {
  id: string; // suggestion_fingerprint
  type: SuggestionType;
  text: string;
  why: string;
  hypothesis: boolean;
  citations?: Source[];
  routine_action?: "daily-checkin" | "end-of-day-debrief" | "meeting-prep" | "meeting-debrief" | "weekly-review" | "new-decision" | "trip-debrief" | "fix-queue";
}
```

#### `CoachSettings`

```typescript
interface CoachSettings {
  coach_mode_default: CoachMode;
  per_project_mode: Record<string, CoachMode>;
  coach_cooldown_days: number;
  vault_path?: string;
  audit_mode_default?: "off" | "summary" | "full";
  connectors?: {
    bookmarks_import_enabled: boolean;
    highlights_enabled: boolean;
    pdf_annotations_enabled: boolean;
  };
}
```

#### `HealthDashboard`

```typescript
interface HealthDashboard {
  coverage: {
    low_volume_projects: string[];
    low_hit_projects: string[];
  };
  metadata_hygiene: {
    missing_project: number;
    missing_date: number;
    missing_language: number;
    missing_source: number;
  };
  staleness: {
    over_6_months: number;
    over_12_months: number;
  };
  ingestion_failures: Array<{
    file: string;
    error_type: string;
  }>;
  fix_queue: Array<{
    id: string;
    action: "open" | "reindex" | "fix_metadata";
    file: string;
    reason: string;
  }>;
}
```

#### `TemplateSummary`

```typescript
interface TemplateSummary {
  id: string;
  title: string;
  description: string;
}
```

#### `LintIssue`

```typescript
interface LintIssue {
  type: string;
  message: string;
  line?: number;
}
```

#### `EvalRunSummary`

```typescript
interface EvalRunSummary {
  id: string;
  status: "running" | "completed" | "failed";
  baseline: boolean;
  started_at?: string;
  completed_at?: string;
}
```

#### `AnswerFooter`

```typescript
interface AnswerFooter {
  source_count: number;
  date_confidence: DateConfidence | null;
  may_be_outdated: boolean;
  outdated_source_count: number;
  not_found?: boolean;
  not_found_message?: string;
}
```

#### `AskRequest`

```typescript
interface AskRequest {
  query: string;
  filters?: {
    projects?: string[];
    types?: string[];
    date_after?: string | null;
    date_before?: string | null;
    language?: string | null;
  };
  top_k?: number;
  coach_mode_enabled?: boolean;
  coach_show_anyway?: boolean;
  include_audit?: boolean;
  include_report?: boolean;
  report_format?: "markdown" | "text";
}
```

#### `AskResponse`

```typescript
interface AskResponse {
  answer: string | null;
  coach_mode_enabled: boolean;
  suggestions: CoachSuggestion[];
  sources: Source[];
  audit?: AnswerAudit;
  report?: Report;
  footer: AnswerFooter;
  query_time_ms: number;
}
```

---

## Error Handling

### Error Response Format

All errors follow RFC 7807 Problem Details:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  }
}
```

### Error Codes

| Code                | HTTP Status | Description                        |
| ------------------- | ----------- | ---------------------------------- |
| `VALIDATION_ERROR`  | 400         | Invalid request parameters         |
| `NOT_FOUND`         | 404         | Resource not found                 |
| `INDEX_JOB_RUNNING` | 409         | Cannot start new job while running |
| `JOB_NOT_FOUND`     | 404         | Job ID does not exist              |
| `FILE_NOT_FOUND`    | 404         | File path does not exist           |
| `DATABASE_ERROR`    | 500         | Database operation failed          |
| `INTERNAL_ERROR`    | 500         | Unexpected server error            |

### Not Found Behaviors

| Resource            | Behavior                                        |
| ------------------- | ----------------------------------------------- |
| Query with no match | Return 200 with `footer.not_found = true`       |
| Document by ID      | Return 404 with `NOT_FOUND` error               |
| Job by ID           | Return 404 with `JOB_NOT_FOUND` error           |
| File to open        | Return 200 with `success = false`, include path |

---

## Agent Tool Server (MCP)

An optional MCP-compatible tool server exposes local-only tools for agents.

- **Transport:** JSON-RPC over localhost (configurable port)
- **Tools:** `search`, `ask` (with citations), `read_note`, `write_note`, `list_projects`, `index_status`
- **Permissions:** allowed paths, read/write scopes, and dry-run enforcement
- **Security:** local-only binding by default, explicit errors on denied actions

---

## Example Payloads

### Full Ask Flow

**Request:**

```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What database should I use?",
    "filters": {
      "projects": ["docs"]
    },
    "top_k": 3,
    "coach_mode_enabled": false,
    "coach_show_anyway": false
  }'
```

**Response:**

```json
{
  "answer": "Based on the architectural decisions [1], you should use SQLite for all local storage. It was chosen for its portability and zero-config operation [1]. The database schema is documented in the data model [2].",
  "coach_mode_enabled": false,
  "suggestions": [],
  "sources": [
    {
      "id": 1,
      "document_id": 42,
      "file_path": "docs/architecture.md",
      "file_type": "markdown",
      "locator": {
        "type": "heading",
        "heading": "Database Choice",
        "start_line": 89,
        "end_line": 102
      },
      "snippet": "We evaluated PostgreSQL, SQLite, and file-based storage. SQLite was chosen for portability...",
      "date": "2025-12-15",
      "date_confidence": "HIGH",
      "project": "docs",
      "may_be_outdated": false,
      "similarity_score": 0.94
    },
    {
      "id": 2,
      "document_id": 43,
      "file_path": "docs/data-model.md",
      "file_type": "markdown",
      "locator": {
        "type": "heading",
        "heading": "Overview",
        "start_line": 1,
        "end_line": 20
      },
      "snippet": "B.O.B uses SQLite as its primary database, with optional sqlite-vec for vector similarity...",
      "date": "2025-12-10",
      "date_confidence": "HIGH",
      "project": "docs",
      "may_be_outdated": false,
      "similarity_score": 0.89
    }
  ],
  "footer": {
    "source_count": 2,
    "date_confidence": "HIGH",
    "may_be_outdated": false,
    "outdated_source_count": 0
  },
  "query_time_ms": 134
}
```

### Indexing Flow

**Start job:**

```bash
curl -X POST http://localhost:8080/index \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/Users/me/notes",
    "project": "notes"
  }'
```

**Poll progress:**

```bash
curl http://localhost:8080/index/idx_a1b2c3d4
```

**Cancel if needed:**

```bash
curl -X DELETE http://localhost:8080/index/idx_a1b2c3d4
```

### Open Source File

```bash
curl -X POST http://localhost:8080/open \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "docs/architecture.md",
    "locator": {
      "type": "heading",
      "start_line": 89
    }
  }'
```

---

## Sources

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Phase 2 requirements
- [UI_PLAN.md](UI_PLAN.md) — UI specifications
- [architecture.md](architecture.md) — System design
- [data-model.md](data-model.md) — Database schema

**Date Confidence:** HIGH (document created 2025-12-23)

---

_This API contract is a living document. Update as implementation progresses._
