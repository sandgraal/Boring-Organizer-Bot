ALTER TABLE search_history
    ADD COLUMN IF NOT EXISTS not_found INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_search_history_project
    ON search_history(project);
CREATE INDEX IF NOT EXISTS idx_search_history_searched_at
    ON search_history(searched_at);
