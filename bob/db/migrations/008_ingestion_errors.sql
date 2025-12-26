-- Migration: 008_ingestion_errors
-- Created: 2025-12-26
-- Description: Log ingestion errors for health metrics

CREATE TABLE IF NOT EXISTS ingestion_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    source_type TEXT,
    project TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ingestion_errors_type ON ingestion_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_ingestion_errors_project ON ingestion_errors(project);
CREATE INDEX IF NOT EXISTS idx_ingestion_errors_created_at ON ingestion_errors(created_at);

INSERT INTO schema_migrations (version, name) VALUES (8, '008_ingestion_errors');
