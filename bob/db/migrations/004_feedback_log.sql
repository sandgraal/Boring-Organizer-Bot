-- Migration: 004_feedback_log
-- Created: 2025-12-25
-- Description: Log user feedback for failure diagnostics and Fix Queue metrics

CREATE TABLE IF NOT EXISTS feedback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    project TEXT,
    answer_id TEXT,
    feedback_reason TEXT NOT NULL,
    retrieved_source_ids TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_log_reason ON feedback_log(feedback_reason);
CREATE INDEX IF NOT EXISTS idx_feedback_log_project ON feedback_log(project);
CREATE INDEX IF NOT EXISTS idx_feedback_log_created_at ON feedback_log(created_at);

INSERT INTO schema_migrations (version, name) VALUES (4, '004_feedback_log');
