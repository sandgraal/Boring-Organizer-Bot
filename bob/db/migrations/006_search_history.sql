-- Migration: 006_search_history
-- Created: 2025-12-26
-- Description: Search history tracking table

CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    project TEXT,
    results_count INTEGER NOT NULL,
    not_found INTEGER NOT NULL DEFAULT 0,
    searched_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_search_history_project
    ON search_history(project);
CREATE INDEX IF NOT EXISTS idx_search_history_searched_at
    ON search_history(searched_at);

INSERT INTO schema_migrations (version, name) VALUES (6, '006_search_history');
