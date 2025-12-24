-- Migration: 002_vector_index
-- Created: 2024-12-23
-- Description: Create vector similarity search index using sqlite-vec
-- 
-- NOTE: This migration must be applied programmatically using sqlite-vec bindings.
-- The SQL here is for documentation. See bob/db/database.py for implementation.

-- This is a placeholder. The actual virtual table creation happens in Python:
--
-- import sqlite_vec
-- 
-- db.execute("""
--     CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings USING vec0(
--         chunk_id INTEGER PRIMARY KEY,
--         embedding FLOAT[384]
--     )
-- """)
--
-- If sqlite-vec is not available, fall back to storing embeddings as BLOBs
-- in a regular table and doing brute-force cosine similarity in Python.

-- Fallback table for when sqlite-vec is not available
CREATE TABLE IF NOT EXISTS chunk_embeddings_fallback (
    chunk_id INTEGER PRIMARY KEY,
    embedding BLOB NOT NULL,  -- numpy array serialized as bytes
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);

-- Record this migration
INSERT INTO schema_migrations (version, name) VALUES (2, '002_vector_index');
