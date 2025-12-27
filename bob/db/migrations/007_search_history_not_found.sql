-- Migration: 007_search_history_not_found
-- Created: 2025-12-26
-- Description: Add not_found column to search history

ALTER TABLE search_history
    ADD COLUMN IF NOT EXISTS not_found INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_search_history_project
    ON search_history(project);
CREATE INDEX IF NOT EXISTS idx_search_history_searched_at
    ON search_history(searched_at);

INSERT INTO schema_migrations (version, name) VALUES (7, '007_search_history_not_found');
