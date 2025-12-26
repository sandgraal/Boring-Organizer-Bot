-- Migration: 005_permission_denials
-- Created: 2025-12-25
-- Description: Log permission denials for Fix Queue diagnostics

CREATE TABLE IF NOT EXISTS permission_denials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_name TEXT NOT NULL,
    project TEXT,
    target_path TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    scope_level INTEGER,
    required_scope_level INTEGER,
    allowed_paths TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_permission_denials_reason ON permission_denials(reason_code);
CREATE INDEX IF NOT EXISTS idx_permission_denials_project ON permission_denials(project);
CREATE INDEX IF NOT EXISTS idx_permission_denials_created_at ON permission_denials(created_at);

INSERT INTO schema_migrations (version, name) VALUES (5, '005_permission_denials');
