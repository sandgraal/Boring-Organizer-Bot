-- Migration: 003_coach_mode
-- Created: 2025-12-23
-- Description: Coach Mode settings and suggestion cooldown log

-- User settings (single-row table)
CREATE TABLE IF NOT EXISTS user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    global_mode_default TEXT NOT NULL DEFAULT 'boring', -- 'boring' | 'coach'
    per_project_mode TEXT NOT NULL DEFAULT '{}',       -- JSON map: project -> mode
    coach_cooldown_days INTEGER NOT NULL DEFAULT 7,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Suggestion log for cooldown enforcement
CREATE TABLE IF NOT EXISTS coach_suggestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datetime TEXT NOT NULL DEFAULT (datetime('now')),
    project TEXT NOT NULL,
    suggestion_type TEXT NOT NULL,
    suggestion_fingerprint TEXT NOT NULL,
    was_shown INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_coach_suggestion_project_type
    ON coach_suggestion_log(project, suggestion_type, datetime);
CREATE INDEX IF NOT EXISTS idx_coach_suggestion_fingerprint
    ON coach_suggestion_log(suggestion_fingerprint);

-- Record this migration
INSERT INTO schema_migrations (version, name) VALUES (3, '003_coach_mode');
