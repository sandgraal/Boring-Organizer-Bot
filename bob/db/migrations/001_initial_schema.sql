-- Migration: 001_initial_schema
-- Created: 2024-12-23
-- Description: Initial database schema for B.O.B

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Documents table: tracks all indexed source files
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Source identification
    source_path TEXT NOT NULL,           -- Original file path or URL
    source_type TEXT NOT NULL,           -- 'markdown', 'pdf', 'word', 'excel', 'recipe', 'git'
    
    -- Metadata (always required)
    project TEXT NOT NULL,               -- Project/collection name
    language TEXT NOT NULL DEFAULT 'en', -- ISO 639-1 language code
    source_date TEXT,                    -- Date from document or file mtime (ISO 8601)
    
    -- Git-specific metadata
    git_repo TEXT,                       -- Repository URL or path
    git_commit TEXT,                     -- Commit SHA
    git_branch TEXT,                     -- Branch name
    
    -- Content hash for change detection
    content_hash TEXT NOT NULL,          -- SHA-256 of content
    
    -- Timestamps
    indexed_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Ensure unique documents per source
    UNIQUE(source_path, project)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project);
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_source_date ON documents(source_date);

-- Chunks table: stores document chunks with embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    
    -- Chunk content
    content TEXT NOT NULL,               -- The actual chunk text
    
    -- Locator information (type-specific)
    locator_type TEXT NOT NULL,          -- 'heading', 'page', 'paragraph', 'sheet', 'section', 'line'
    locator_value TEXT NOT NULL,         -- JSON: {"heading": "...", "start_line": N, "end_line": M}
    
    -- Chunk ordering
    chunk_index INTEGER NOT NULL,        -- Position within document
    
    -- Token count for context management
    token_count INTEGER,
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Index for retrieval
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);

-- Virtual table for vector similarity search (sqlite-vec)
-- Note: This is created programmatically as sqlite-vec requires special handling
-- The table will have:
--   chunk_id INTEGER PRIMARY KEY
--   embedding FLOAT[384]  -- dimension matches embedding model

-- Decisions table: extracted decisions from documents
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    
    -- Decision content
    decision_text TEXT NOT NULL,         -- The decision statement
    context TEXT,                         -- Surrounding context
    
    -- Classification
    decision_type TEXT,                  -- 'architecture', 'process', 'api', 'feature', etc.
    status TEXT DEFAULT 'active',        -- 'active', 'superseded', 'deprecated'
    superseded_by INTEGER,               -- Reference to newer decision
    
    -- Metadata
    decision_date TEXT,                  -- When the decision was made
    confidence REAL,                     -- Extraction confidence (0-1)
    
    -- Timestamps
    extracted_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (superseded_by) REFERENCES decisions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_chunk ON decisions(chunk_id);
CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);

-- Search history for analytics (optional)
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    project TEXT,
    results_count INTEGER,
    searched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Migration tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Record this migration
INSERT INTO schema_migrations (version, name) VALUES (1, '001_initial_schema');
