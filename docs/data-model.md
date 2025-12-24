# Data Model

## Overview

B.O.B uses SQLite as its primary database, with optional sqlite-vec for vector similarity search.

## Entity Relationship

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  documents  │──1:N──│   chunks    │──1:N──│  decisions  │
└─────────────┘       └─────────────┘       └─────────────┘
                            │
                           1:1
                            │
                      ┌─────────────┐
                      │ embeddings  │
                      └─────────────┘
```

Additional tables support health, evaluation, and Coach Mode (see below).

## Tables

### documents

Stores metadata about indexed source files.

| Column       | Type    | Description                                         |
| ------------ | ------- | --------------------------------------------------- |
| id           | INTEGER | Primary key                                         |
| source_path  | TEXT    | Original file path or URL                           |
| source_type  | TEXT    | 'markdown', 'pdf', 'word', 'excel', 'recipe', 'git' |
| project      | TEXT    | Project/collection name                             |
| language     | TEXT    | ISO 639-1 language code                             |
| source_date  | TEXT    | Document date (ISO 8601)                            |
| git_repo     | TEXT    | Repository URL (git only)                           |
| git_commit   | TEXT    | Commit SHA (git only)                               |
| git_branch   | TEXT    | Branch name (git only)                              |
| content_hash | TEXT    | SHA-256 for change detection                        |
| indexed_at   | TEXT    | First indexed timestamp                             |
| updated_at   | TEXT    | Last update timestamp                               |

**Indexes:**

- `(source_path, project)` - unique constraint
- `project` - for filtering
- `source_type` - for filtering
- `source_date` - for date-based queries

### chunks

Stores document chunks with locator information.

| Column        | Type    | Description              |
| ------------- | ------- | ------------------------ |
| id            | INTEGER | Primary key              |
| document_id   | INTEGER | Foreign key to documents |
| content       | TEXT    | Chunk text               |
| locator_type  | TEXT    | Type of locator          |
| locator_value | TEXT    | JSON locator details     |
| chunk_index   | INTEGER | Position in document     |
| token_count   | INTEGER | Estimated token count    |
| created_at    | TEXT    | Creation timestamp       |

**Locator Types:**

- `heading`: `{"heading": "...", "start_line": N, "end_line": M}`
- `page`: `{"page": N, "total_pages": M}`
- `paragraph`: `{"paragraph_index": N, "parent_heading": "..."}`
- `sheet`: `{"sheet_name": "...", "row_count": N}`
- `section`: `{"section": "..."}`
- `line`: `{"start_line": N, "end_line": M, "git_file": "...", "git_commit": "..."}`

### chunk_embeddings (sqlite-vec)

Vector table for semantic search.

| Column    | Type       | Description               |
| --------- | ---------- | ------------------------- |
| chunk_id  | INTEGER    | Primary key, FK to chunks |
| embedding | FLOAT[384] | Vector embedding          |

### chunk_embeddings_fallback

Fallback table when sqlite-vec is not available.

| Column    | Type    | Description               |
| --------- | ------- | ------------------------- |
| chunk_id  | INTEGER | Primary key, FK to chunks |
| embedding | BLOB    | Serialized numpy array    |

### decisions

Extracted decisions stored for decision-aware search and CLI output.

| Column        | Type    | Description                          |
| ------------- | ------- | ------------------------------------ |
| id            | INTEGER | Primary key                          |
| chunk_id      | INTEGER | Source chunk                         |
| decision_text | TEXT    | The decision statement               |
| context       | TEXT    | Surrounding context                  |
| decision_type | TEXT    | Category                             |
| status        | TEXT    | 'proposed', 'decided', 'superseded', 'obsolete' |
| superseded_by | INTEGER | Reference to newer decision          |
| superseded_at | TEXT    | When superseded (optional)           |
| decision_date | TEXT    | When decision was made               |
| confidence    | REAL    | Extraction confidence                |
| extracted_at  | TEXT    | Extraction timestamp                 |

### index_runs

Stores indexing job metadata for health dashboards and audit.

| Column        | Type    | Description                         |
| ------------- | ------- | ----------------------------------- |
| id            | INTEGER | Primary key                         |
| path          | TEXT    | Indexed path                        |
| project       | TEXT    | Project name                        |
| status        | TEXT    | 'running', 'completed', 'failed'    |
| started_at    | TEXT    | Start timestamp                     |
| completed_at  | TEXT    | Completion timestamp (optional)     |
| files_total   | INTEGER | Total files discovered              |
| files_indexed | INTEGER | Successfully indexed files          |
| files_failed  | INTEGER | Failed files                        |

### ingestion_errors

Stores per-file ingestion failures for health dashboards and fix queues.

| Column        | Type    | Description                          |
| ------------- | ------- | ------------------------------------ |
| id            | INTEGER | Primary key                          |
| index_run_id  | INTEGER | FK to index_runs                     |
| file_path     | TEXT    | File path that failed                |
| source_type   | TEXT    | Document type                        |
| error_type    | TEXT    | 'parse_error', 'no_text', 'oversize' |
| error_message | TEXT    | Error message                        |
| created_at    | TEXT    | Error timestamp                      |
| resolved_at   | TEXT    | Resolution timestamp (optional)      |

### eval_runs

Stores evaluation run metadata for regression tracking.

| Column        | Type    | Description                          |
| ------------- | ------- | ------------------------------------ |
| id            | INTEGER | Primary key                          |
| golden_set    | TEXT    | Path or identifier of golden set     |
| started_at    | TEXT    | Run start time                       |
| completed_at  | TEXT    | Run end time                         |
| status        | TEXT    | 'running', 'completed', 'failed'     |
| config_hash   | TEXT    | Hash of retrieval config             |
| baseline      | INTEGER | 1 if baseline run                    |

### eval_results

Stores per-question metrics and drift data.

| Column          | Type    | Description                           |
| --------------- | ------- | ------------------------------------- |
| id              | INTEGER | Primary key                           |
| eval_run_id     | INTEGER | FK to eval_runs                       |
| question_id     | TEXT    | Question identifier                   |
| recall_at_k     | REAL    | Recall@k                              |
| precision_at_k  | REAL    | Precision@k                           |
| mrr             | REAL    | Mean reciprocal rank                  |
| answer_hash     | TEXT    | Hash of answer for drift detection    |
| changed_since   | TEXT    | Reference run id (optional)           |

### search_history

Optional analytics table.

| Column        | Type    | Description       |
| ------------- | ------- | ----------------- |
| id            | INTEGER | Primary key       |
| query         | TEXT    | Search query      |
| project       | TEXT    | Project filter    |
| results_count | INTEGER | Number of results |
| not_found     | INTEGER | 1 if no sources   |
| searched_at   | TEXT    | Timestamp         |

### user_settings

Coach Mode preferences (single-row table).

| Column              | Type    | Description                              |
| ------------------- | ------- | ---------------------------------------- |
| id                  | INTEGER | Primary key                              |
| global_mode_default | TEXT    | "boring" or "coach"                      |
| per_project_mode    | TEXT    | JSON map of project -> mode              |
| coach_cooldown_days | INTEGER | Default cooldown window in days          |
| updated_at          | TEXT    | Last update timestamp                    |

### coach_suggestion_log

Suggestion log for cooldown enforcement.

| Column                | Type    | Description                          |
| --------------------- | ------- | ------------------------------------ |
| id                    | INTEGER | Primary key                          |
| datetime              | TEXT    | When the suggestion was shown/logged |
| project               | TEXT    | Project name or "all"                |
| suggestion_type       | TEXT    | Allowed suggestion category          |
| suggestion_fingerprint | TEXT   | Hash of type + normalized text       |
| was_shown             | INTEGER | 1 if shown, 0 if dismissed/blocked   |

### schema_migrations

Tracks applied migrations.

| Column     | Type    | Description       |
| ---------- | ------- | ----------------- |
| version    | INTEGER | Migration version |
| name       | TEXT    | Migration name    |
| applied_at | TEXT    | Applied timestamp |

## Migrations

Migrations are stored in `bob/db/migrations/` as SQL files:

- `001_initial_schema.sql` - Core tables
- `002_vector_index.sql` - Vector search setup
- `003_coach_mode.sql` - Coach Mode settings and cooldown log
- `004_decision_lifecycle.sql` - Decision status expansion and superseded_at
- `005_health_dashboard.sql` - index_runs and ingestion_errors
- `006_eval_runs.sql` - eval_runs and eval_results

Run migrations with:

```bash
bob init
```

## Vector Search

### With sqlite-vec (preferred)

Uses native SQL for cosine distance:

```sql
SELECT *, vec_distance_cosine(embedding, ?) as distance
FROM chunk_embeddings
ORDER BY distance ASC
LIMIT ?
```

### Fallback (Python)

Loads all embeddings and computes cosine similarity in Python. Works but slower for large datasets.

## Best Practices

1. **Always include project**: Helps with filtering and organization
2. **Use content_hash**: Skip unchanged documents during re-indexing
3. **Keep locators precise**: Good locators enable good citations
4. **Date everything**: Source dates enable freshness warnings
