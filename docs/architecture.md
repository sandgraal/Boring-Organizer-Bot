# B.O.B Architecture

## Overview

B.O.B (Boring Organizer Bot) is a local-first personal knowledge assistant. This document describes the system architecture and design decisions.

## Design Principles

1. **Local-first**: All data stays on your machine. No cloud dependencies for core functionality.
2. **Boring technology**: SQLite, Python, simple file parsers. No exotic dependencies.
3. **Citation-grounded**: Every claim must be backed by a source. No hallucinations.
4. **Developer-friendly**: Clear code, good tests, easy to extend.

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
```

## Data Flow

### Indexing Pipeline

```
File → Parser → ParsedDocument → Chunker → Chunks → Embedder → Database
                     │                        │
                     └── Metadata ────────────┘
```

1. **Parser** reads file and extracts structured sections with locators
2. **Chunker** splits sections into indexable chunks while preserving locators
3. **Embedder** generates vector embeddings for semantic search
4. **Database** stores chunks, embeddings, and metadata

### Query Pipeline

```
Query → Embedder → Vector Search → Results → Formatter → Output
                        │              │
                        └── Metadata ──┘
```

1. **Embedder** converts query to vector
2. **Vector Search** finds similar chunks
3. **Formatter** adds citations, date confidence, and warnings

## Database Schema

See [data-model.md](data-model.md) for detailed schema documentation.

### Key Tables

- `documents`: Source file metadata (path, type, project, dates)
- `chunks`: Text chunks with locator information
- `chunk_embeddings`: Vector embeddings (sqlite-vec or fallback)
- `decisions`: Extracted decisions (placeholder)

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

### Adding Decision Extraction

The `decisions` table is ready for:

1. Pattern-based extraction from chunks
2. Classification of decision types
3. Tracking superseded decisions

See `bob/extract/decisions.py` (TODO).
