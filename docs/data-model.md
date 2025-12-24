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

### decisions (placeholder)

For future decision extraction feature.

| Column        | Type    | Description                          |
| ------------- | ------- | ------------------------------------ |
| id            | INTEGER | Primary key                          |
| chunk_id      | INTEGER | Source chunk                         |
| decision_text | TEXT    | The decision statement               |
| context       | TEXT    | Surrounding context                  |
| decision_type | TEXT    | Category                             |
| status        | TEXT    | 'active', 'superseded', 'deprecated' |
| superseded_by | INTEGER | Reference to newer decision          |
| decision_date | TEXT    | When decision was made               |
| confidence    | REAL    | Extraction confidence                |
| extracted_at  | TEXT    | Extraction timestamp                 |

### search_history

Optional analytics table.

| Column        | Type    | Description       |
| ------------- | ------- | ----------------- |
| id            | INTEGER | Primary key       |
| query         | TEXT    | Search query      |
| project       | TEXT    | Project filter    |
| results_count | INTEGER | Number of results |
| searched_at   | TEXT    | Timestamp         |

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
