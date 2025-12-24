# B.O.B Architecture

## Overview

B.O.B (Boring Organizer Bot) is a local-first personal knowledge assistant. This document describes the system architecture and design decisions.

## Design Principles

1. **Local-first**: All data stays on your machine. No cloud dependencies for core functionality.
2. **Boring technology**: SQLite, Python, simple file parsers. No exotic dependencies.
3. **Citation-grounded**: Every claim must be backed by a source. No hallucinations.
4. **Auditability**: Provenance is visible; unsupported claims are blocked or marked.
5. **Developer-friendly**: Clear code, good tests, easy to extend.

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                       Web Interface                          │
│            bob/ui/ (HTML + CSS + vanilla JS)                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                       API Layer                              │
│       bob/api/ (FastAPI - localhost:8080)                   │
│  POST /ask | POST /index | GET /projects | POST /open       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│             Agent Tool Server (Optional MCP)                │
│   bob/agents/ (MCP-compatible tool endpoints)               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  bob index | bob ask | bob status | bob serve | bob eval    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│    Ingest     │     │   Retrieval   │     │    Answer     │
│   (parsers)   │     │   (search)    │     │  (citations)  │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│    Index      │     │   Scoring     │     │  Formatter    │
│  (chunking)   │     │ (hybrid)      │     │ (output)      │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │
        └──────────┬──────────┘
                   ▼
        ┌───────────────────┐
        │      Database     │
        │  (SQLite + vec)   │
        └───────────────────┘

Additional components (local-only):

- **Answer audit**: claim validation + retrieved/used audit payload
- **Knowledge health**: coverage, metadata hygiene, staleness, failures
- **Capture helpers**: templates, new-note writer, linter
- **Connectors**: bookmarks import, manual highlights, PDF annotations
- **Eval UI**: golden set regression and drift display
```

## Data Flow

### Indexing Pipeline

```
File/Connector → Parser → ParsedDocument → Chunker → Chunks → Embedder → Database
                     │                        │
                     └── Metadata ────────────┘
```

1. **Parser** reads file and extracts structured sections with locators
2. **Chunker** splits sections into indexable chunks while preserving locators
3. **Embedder** generates vector embeddings for semantic search
4. **Database** stores chunks, embeddings, and metadata

### Query Pipeline

```
Query → Embedder → Vector Search → Results → Claim Validator → Formatter → Output
                        │                      │
                        └── Metadata + Audit ──┘
```

1. **Embedder** converts query to vector
2. **Vector Search** finds similar chunks
3. **Formatter** adds citations, date confidence, and warnings
4. **Claim Validator** removes or marks unsupported spans and emits audit data

## Database Schema

See [data-model.md](data-model.md) for detailed schema documentation.

### Key Tables

- `documents`: Source file metadata (path, type, project, dates)
- `chunks`: Text chunks with locator information
- `chunk_embeddings`: Vector embeddings (sqlite-vec or fallback)
- `decisions`: Extracted decisions with status and supersession

## Locator System

Every chunk maintains a locator that points back to its source:

| Source Type | Locator Format                                 |
| ----------- | ---------------------------------------------- |
| Markdown    | `{heading, start_line, end_line}`              |
| PDF         | `{page, total_pages}`                          |
| Word        | `{paragraph_index, parent_heading}`            |
| Excel       | `{sheet_name, row_count}`                      |
| Recipe      | `{section}`                                    |
| Git         | `{git_file, git_commit, start_line, end_line}` |

## Configuration

Configuration is loaded in order:

1. `./bob.yaml` (project root)
2. `~/.config/bob/bob.yaml` (user config)
3. Environment variables (`BOB_*`)

See [bob.yaml.example](../bob.yaml.example) for all options.

## Extension Points

### Adding a New Parser

1. Create `bob/ingest/myformat.py`
2. Implement `Parser` base class
3. Register in `bob/ingest/registry.py`

### Adding a New Embedding Model

1. Modify `bob/index/embedder.py`
2. Update `bob.yaml.example` with model options
3. Update database dimension if needed

### Decision Extraction

Decision extraction is implemented in `bob/extract/decisions.py` and
`bob/extract/patterns.py`. To extend coverage, add or tune patterns and
update `tests/test_decisions.py` to validate new formats.

#### Supported decision formats (examples)

The extractor looks for explicit markers and common decision language.

```md
# ADR-003: Use SQLite for local storage
## Status
Accepted
## Context
We need a local database with zero setup.
## Decision
We will use SQLite for local storage.
```

```md
## Meeting Notes 2025-01-15
Decision: We will deploy weekly on Tuesdays.
Agreed: Rotate on-call weekly.
```

```md
We decided to use PostgreSQL instead of MySQL for reliability.
```

Rejected alternatives are captured when phrases like "Rejected:", "considered X
but decided against", "instead of", "rather than", or "not X" appear.

Decision dates currently come from document metadata (`source_date`) and are not
parsed from inline text.

### Agent Interop (MCP)

Optional MCP-compatible tool server exposes local-only tools:

- search/ask with citations
- read/write notes
- list projects and index status
- permissioning (paths, scopes, dry-run)

This server is opt-in and never binds to non-localhost by default.
