# B.O.B API Contract

> HTTP API specification for local-only B.O.B server.

**Last Updated:** 2025-12-23  
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
```

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
  "coach_mode_enabled": false
}
```

**Coach Mode:**

- `coach_mode_enabled` is optional; if omitted, server uses persisted settings.

**Response:**

```json
{
  "answer": "To configure logging, edit the `config.yaml` file [1] and set the `log_level` field to your desired level [2].",
  "coach_mode_enabled": false,
  "suggestions": [],
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
  "coach_cooldown_days": 7
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
  "coach_cooldown_days": 7
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
| `status`  | string | Filter: `active`, `superseded`, `all` |
| `project` | string | Filter by project                     |
| `search`  | string | Search in decision text               |
| `page`    | int    | Page number                           |

**Response:**

```json
{
  "decisions": [
    {
      "id": "DEC-001",
      "decision_text": "Use SQLite for all local storage",
      "context": "We evaluated PostgreSQL, SQLite, and file-based storage. SQLite was chosen for portability and zero-config operation.",
      "status": "active",
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
}
```

#### `CoachSettings`

```typescript
interface CoachSettings {
  coach_mode_default: CoachMode;
  per_project_mode: Record<string, CoachMode>;
  coach_cooldown_days: number;
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
    "coach_mode_enabled": false
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
