"""Database management for B.O.B.

Handles SQLite database connections, migrations, and vector storage.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bob.config import get_config

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


class Database:
    """SQLite database wrapper with vector search support."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database. If None, uses config.
        """
        self.db_path = db_path or get_config().database.path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self._connections: set[sqlite3.Connection] = set()
        self._connections_lock = threading.Lock()
        self._has_vec: bool | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._create_connection()
            self._local.conn = conn
        return conn

    def _create_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
        if get_config().database.wal_mode:
            conn.execute("PRAGMA journal_mode=WAL")

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

        # Try to load sqlite-vec
        self._try_load_vec(conn)

        with self._connections_lock:
            self._connections.add(conn)

        return conn

    def _try_load_vec(self, conn: sqlite3.Connection) -> None:
        """Try to load sqlite-vec extension."""
        try:
            import sqlite_vec

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            self._has_vec = True
        except (ImportError, OSError):
            self._has_vec = False

    @property
    def has_vec(self) -> bool:
        """Check if sqlite-vec is available."""
        if self._has_vec is None:
            # Ensure connection is initialized
            _ = self.conn
        return self._has_vec or False

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database transactions."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def close(self) -> None:
        """Close all open database connections."""
        with self._connections_lock:
            connections = list(self._connections)
            self._connections.clear()

        for conn in connections:
            with contextlib.suppress(sqlite3.ProgrammingError):
                conn.close()

        if hasattr(self._local, "conn"):
            del self._local.conn

    def migrate(self) -> None:
        """Run database migrations."""
        # Get current version
        try:
            cursor = self.conn.execute("SELECT MAX(version) FROM schema_migrations")
            current_version = cursor.fetchone()[0] or 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            current_version = 0

        # Find and run pending migrations
        migrations_dir = Path(__file__).parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        for migration_file in migration_files:
            # Extract version from filename (e.g., 001_initial_schema.sql -> 1)
            version = int(migration_file.stem.split("_")[0])

            if version > current_version:
                self._run_migration(migration_file, version)

        # Create vector table if sqlite-vec is available
        if self.has_vec:
            self._create_vec_table()

    def _run_migration(self, migration_file: Path, version: int) -> None:
        """Run a single migration file.

        Args:
            migration_file: Path to the migration SQL file.
            version: Migration version number.
        """
        with open(migration_file) as f:
            sql = f.read()

        # Skip the migration record insert - we'll handle it separately
        # to avoid duplicate key errors on re-runs
        statements = sql.split(";")

        with self.transaction():
            for statement in statements:
                statement = statement.strip()
                if statement and "INSERT INTO schema_migrations" not in statement:
                    rewritten = self._rewrite_add_column_if_not_exists(statement)
                    if rewritten:
                        self.conn.execute(rewritten)

            # Check if already recorded
            cursor = self.conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
            )
            if not cursor.fetchone():
                self.conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (version, migration_file.stem),
                )

    def _create_vec_table(self) -> None:
        """Create the vector similarity table using sqlite-vec."""
        dimension = get_config().embedding.dimension

        # Validate dimension is an integer to prevent SQL injection
        if not isinstance(dimension, int) or dimension <= 0:
            raise ValueError(f"Invalid embedding dimension: {dimension}")

        # Safe to use dimension in f-string after validation ensures it's a positive integer
        try:
            self.conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings USING vec0(
                    chunk_id INTEGER PRIMARY KEY,
                    embedding FLOAT[{dimension}]
                )
            """)
            self.conn.commit()
        except sqlite3.OperationalError:
            # Table might already exist or vec0 not available
            pass

    def _rewrite_add_column_if_not_exists(self, statement: str) -> str | None:
        """Handle unsupported ADD COLUMN IF NOT EXISTS syntax in SQLite."""
        pattern = re.compile(
            r"^ALTER TABLE\s+(?P<table>\S+)\s+ADD COLUMN IF NOT EXISTS\s+"
            r"(?P<column>\S+)\s+(?P<definition>.+)$",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.match(statement)
        if not match:
            return statement

        table_token = match.group("table")
        column_token = match.group("column")
        definition = match.group("definition").strip()

        table_name = table_token.strip('"`[]')
        column_name = column_token.strip('"`[]')

        if self._column_exists(table_name, column_name):
            return None

        return f"ALTER TABLE {table_token} ADD COLUMN {column_token} {definition}"

    def _column_exists(self, table: str, column: str) -> bool:
        """Check if a column exists on a table.

        Args:
            table: Table name to check (must be a valid SQL identifier).
            column: Column name to check.

        Returns:
            True if the column exists in the table.
        """
        # Validate table name to prevent SQL injection
        # SQLite identifiers can contain: letters, digits, underscores
        # Must not start with a digit or sqlite_
        if not table or not self._is_valid_identifier(table):
            raise ValueError(f"Invalid table name: {table}")

        cursor = self.conn.execute(f"PRAGMA table_info({table})")
        return any(row["name"] == column for row in cursor.fetchall())

    def _is_valid_identifier(self, identifier: str) -> bool:
        """Check if a string is a valid SQL identifier.

        Args:
            identifier: The identifier to validate.

        Returns:
            True if the identifier is valid and safe to use.
        """
        if not identifier:
            return False

        # Check for valid SQL identifier pattern
        # Allow: letters, digits, underscores
        # Must start with letter or underscore
        # Must not start with 'sqlite_' (reserved prefix)
        if identifier.startswith("sqlite_"):
            return False

        if not identifier[0].isalpha() and identifier[0] != "_":
            return False

        return all(c.isalnum() or c == "_" for c in identifier)

    # Document operations

    def insert_document(
        self,
        source_path: str,
        source_type: str,
        project: str,
        content_hash: str,
        language: str = "en",
        source_date: datetime | None = None,
        git_repo: str | None = None,
        git_commit: str | None = None,
        git_branch: str | None = None,
    ) -> int:
        """Insert or update a document.

        Args:
            source_path: Original file path or URL.
            source_type: Type of document.
            project: Project name.
            content_hash: SHA-256 hash of content.
            language: ISO 639-1 language code.
            source_date: Document date.
            git_repo: Git repository URL (optional).
            git_commit: Git commit SHA (optional).
            git_branch: Git branch name (optional).

        Returns:
            Document ID.
        """
        with self.transaction():
            cursor = self.conn.execute(
                """
                INSERT INTO documents (
                    source_path, source_type, project, content_hash,
                    language, source_date, git_repo, git_commit, git_branch
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path, project) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    source_date = excluded.source_date,
                    git_commit = excluded.git_commit,
                    updated_at = datetime('now')
                RETURNING id
                """,
                (
                    source_path,
                    source_type,
                    project,
                    content_hash,
                    language,
                    source_date.isoformat() if source_date else None,
                    git_repo,
                    git_commit,
                    git_branch,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Failed to insert document")
            return int(row[0])

    def get_document_by_path(self, source_path: str, project: str) -> dict[str, Any] | None:
        """Get a document by path and project.

        Args:
            source_path: Original file path.
            project: Project name.

        Returns:
            Document dict or None.
        """
        cursor = self.conn.execute(
            "SELECT * FROM documents WHERE source_path = ? AND project = ?",
            (source_path, project),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def delete_document_chunks(self, document_id: int) -> None:
        """Delete all chunks for a document.

        Args:
            document_id: Document ID.
        """
        # Get chunk IDs first for vector cleanup
        cursor = self.conn.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))
        chunk_ids = [row[0] for row in cursor.fetchall()]

        with self.transaction():
            # Delete from vector table
            if self.has_vec:
                for chunk_id in chunk_ids:
                    self.conn.execute(
                        "DELETE FROM chunk_embeddings WHERE chunk_id = ?",
                        (chunk_id,),
                    )
            else:
                for chunk_id in chunk_ids:
                    self.conn.execute(
                        "DELETE FROM chunk_embeddings_fallback WHERE chunk_id = ?",
                        (chunk_id,),
                    )

            # Delete chunks (cascades to decisions)
            self.conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))

    # Chunk operations

    def insert_chunk(
        self,
        document_id: int,
        content: str,
        locator_type: str,
        locator_value: dict[str, Any],
        chunk_index: int,
        token_count: int | None = None,
    ) -> int:
        """Insert a chunk.

        Args:
            document_id: Parent document ID.
            content: Chunk text content.
            locator_type: Type of locator.
            locator_value: Locator details as dict.
            chunk_index: Position within document.
            token_count: Token count (optional).

        Returns:
            Chunk ID.
        """
        cursor = self.conn.execute(
            """
            INSERT INTO chunks (
                document_id, content, locator_type, locator_value,
                chunk_index, token_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                document_id,
                content,
                locator_type,
                json.dumps(locator_value),
                chunk_index,
                token_count,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to insert chunk")
        chunk_id = int(row[0])
        self.conn.commit()
        return chunk_id

    def insert_embedding(self, chunk_id: int, embedding: npt.NDArray[np.float32]) -> None:
        """Insert an embedding for a chunk.

        Args:
            chunk_id: Chunk ID.
            embedding: Embedding vector.
        """
        if self.has_vec:
            # Use sqlite-vec
            self.conn.execute(
                "INSERT INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, embedding.tobytes()),
            )
        else:
            # Fallback to blob storage
            self.conn.execute(
                """
                INSERT INTO chunk_embeddings_fallback (chunk_id, embedding)
                VALUES (?, ?)
                """,
                (chunk_id, embedding.tobytes()),
            )
        self.conn.commit()

    def search_similar(
        self,
        query_embedding: npt.NDArray[np.float32],
        limit: int = 5,
        project: str | None = None,
        projects: list[str] | None = None,
        source_types: list[str] | None = None,
        date_after: datetime | None = None,
        date_before: datetime | None = None,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks.

        Args:
            query_embedding: Query embedding vector.
            limit: Maximum number of results.
            project: Filter by project (optional).
            projects: Filter by multiple projects (optional; overrides `project` if provided).
            source_types: Filter by source types (optional).
            date_after: Filter by documents after this date (optional).
            date_before: Filter by documents before this date (optional).
            language: Filter by language (optional).

        Returns:
            List of matching chunks with scores.
        """

        def _normalize_projects(values: list[str] | None) -> list[str] | None:
            if not values:
                return None
            filtered: list[str] = []
            seen: set[str] = set()
            for name in values:
                if name and name not in seen:
                    seen.add(name)
                    filtered.append(name)
            return filtered or None

        raw_projects = projects or ([project] if project else None)
        project_filters = _normalize_projects(raw_projects)

        if self.has_vec:
            return self._search_vec(
                query_embedding,
                limit,
                project_filters,
                source_types,
                date_after,
                date_before,
                language,
            )
        else:
            return self._search_fallback(
                query_embedding,
                limit,
                project_filters,
                source_types,
                date_after,
                date_before,
                language,
            )

    def _search_vec(
        self,
        query_embedding: npt.NDArray[np.float32],
        limit: int,
        projects: list[str] | None,
        source_types: list[str] | None,
        date_after: datetime | None,
        date_before: datetime | None,
        language: str | None,
    ) -> list[dict[str, Any]]:
        """Search using sqlite-vec."""
        conditions = []
        params: list[Any] = [query_embedding.tobytes()]

        if projects:
            placeholders = ",".join("?" * len(projects))
            conditions.append(f"d.project IN ({placeholders})")
            params.extend(projects)

        if source_types:
            placeholders = ",".join("?" * len(source_types))
            conditions.append(f"d.source_type IN ({placeholders})")
            params.extend(source_types)

        if language:
            conditions.append("d.language = ?")
            params.append(language)

        if date_after:
            conditions.append("d.source_date >= ?")
            params.append(date_after.isoformat())

        if date_before:
            conditions.append("d.source_date <= ?")
            params.append(date_before.isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
                SELECT
                    c.id, c.content, c.locator_type, c.locator_value,
                    d.source_path, d.source_type, d.project, d.language, d.source_date,
                    d.git_repo, d.git_commit,
                    vec_distance_cosine(e.embedding, ?) as distance
                FROM chunk_embeddings e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                {where_clause}
                ORDER BY distance ASC
                LIMIT ?
                """
        params.append(limit)

        cursor = self.conn.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def _search_fallback(
        self,
        query_embedding: npt.NDArray[np.float32],
        limit: int,
        projects: list[str] | None,
        source_types: list[str] | None,
        date_after: datetime | None,
        date_before: datetime | None,
        language: str | None,
    ) -> list[dict[str, Any]]:
        """Fallback search using cosine similarity in Python."""
        import numpy as np

        # Get all embeddings (not efficient for large datasets)
        conditions = []
        params: list[Any] = []

        if projects:
            placeholders = ",".join("?" * len(projects))
            conditions.append(f"d.project IN ({placeholders})")
            params.extend(projects)

        if source_types:
            placeholders = ",".join("?" * len(source_types))
            conditions.append(f"d.source_type IN ({placeholders})")
            params.extend(source_types)

        if language:
            conditions.append("d.language = ?")
            params.append(language)

        if date_after:
            conditions.append("d.source_date >= ?")
            params.append(date_after.isoformat())

        if date_before:
            conditions.append("d.source_date <= ?")
            params.append(date_before.isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
                SELECT
                    e.chunk_id, e.embedding,
                    c.id, c.content, c.locator_type, c.locator_value,
                    d.source_path, d.source_type, d.project, d.language, d.source_date,
                    d.git_repo, d.git_commit
                FROM chunk_embeddings_fallback e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                {where_clause}
                """
        cursor = self.conn.execute(query, params)

        results = []
        for row in cursor.fetchall():
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)

            # Cosine similarity
            similarity = np.dot(query_embedding, embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
            )

            results.append(
                {
                    "id": row["id"],
                    "content": row["content"],
                    "locator_type": row["locator_type"],
                    "locator_value": row["locator_value"],
                    "source_path": row["source_path"],
                    "source_type": row["source_type"],
                    "project": row["project"],
                    "language": row["language"],
                    "source_date": row["source_date"],
                    "git_repo": row["git_repo"],
                    "git_commit": row["git_commit"],
                    "distance": 1 - similarity,  # Convert to distance
                }
            )

        # Sort by distance and limit
        results.sort(key=lambda x: x["distance"])
        return results[:limit]

    # Statistics

    def get_stats(self, project: str | None = None) -> dict[str, Any]:
        """Get database statistics.

        Args:
            project: Filter by project (optional).

        Returns:
            Statistics dict.
        """
        if project:
            doc_count = self.conn.execute(
                "SELECT COUNT(*) FROM documents WHERE project = ?", (project,)
            ).fetchone()[0]

            chunk_count = self.conn.execute(
                """
                SELECT COUNT(*) FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.project = ?
                """,
                (project,),
            ).fetchone()[0]

            source_types = self.conn.execute(
                """
                SELECT source_type, COUNT(*) as count
                FROM documents WHERE project = ?
                GROUP BY source_type
                """,
                (project,),
            ).fetchall()
        else:
            doc_count = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

            chunk_count = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

            source_types = self.conn.execute(
                """
                SELECT source_type, COUNT(*) as count
                FROM documents
                GROUP BY source_type
                """
            ).fetchall()

        projects = self.conn.execute("SELECT DISTINCT project FROM documents").fetchall()

        return {
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "source_types": {row[0]: row[1] for row in source_types},
            "projects": [row[0] for row in projects],
            "has_vec": self.has_vec,
        }

    def get_project_document_counts(self, project: str | None = None) -> list[dict[str, Any]]:
        """Return document counts grouped by project, optionally filtered."""
        params: list[Any] = []
        query = """
            SELECT project, COUNT(*) as count
            FROM documents
        """
        if project:
            query += " WHERE project = ?"
            params.append(project)
        query += """
            GROUP BY project
            ORDER BY count ASC
        """
        cursor = self.conn.execute(query, params)
        return [
            {"project": row["project"], "document_count": int(row["count"])}
            for row in cursor.fetchall()
        ]

    def log_search(
        self,
        *,
        query: str,
        project: str | None,
        results_count: int,
    ) -> None:
        """Record search activity for coverage metrics."""
        not_found = 1 if results_count == 0 else 0
        with self.transaction():
            self.conn.execute(
                """
                INSERT INTO search_history (
                    query,
                    project,
                    results_count,
                    not_found
                )
                VALUES (?, ?, ?, ?)
                """,
                (query, project, int(results_count), not_found),
            )

    def get_search_history_stats(
        self,
        *,
        window_hours: int = 168,
        min_count: int = 1,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Summarize search hit rates per project, optionally filtered."""
        window = f"-{int(window_hours)} hours"
        params: list[Any] = [window]
        query = """
            SELECT COALESCE(NULLIF(project, ''), 'all') as project,
                   COUNT(*) as total,
                   SUM(not_found) as not_found
            FROM search_history
            WHERE datetime(searched_at) >= datetime('now', ?)
        """
        if project:
            query += " AND project = ?"
            params.append(project)
        query += """
            GROUP BY COALESCE(NULLIF(project, ''), 'all')
            HAVING COUNT(*) >= ?
            ORDER BY total DESC
        """
        params.append(min_count)
        cursor = self.conn.execute(query, params)
        stats: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            total = int(row["total"])
            not_found = int(row["not_found"] or 0)
            hit_rate = (total - not_found) / total if total else 0.0
            stats.append(
                {
                    "project": row["project"],
                    "total": total,
                    "not_found": not_found,
                    "hit_rate": hit_rate,
                }
            )
        return stats

    def log_feedback(
        self,
        *,
        question: str,
        project: str | None,
        answer_id: str | None,
        feedback_reason: str,
        retrieved_source_ids: list[int] | None = None,
    ) -> None:
        """Record feedback entries for failure signal analysis."""
        payload = json.dumps(retrieved_source_ids or [])
        with self.transaction():
            self.conn.execute(
                """
                INSERT INTO feedback_log (
                    question,
                    project,
                    answer_id,
                    feedback_reason,
                    retrieved_source_ids
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (question, project, answer_id, feedback_reason, payload),
            )

    def log_permission_denial(
        self,
        *,
        action_name: str,
        project: str | None,
        target_path: str,
        reason_code: str,
        scope_level: int | None = None,
        required_scope_level: int | None = None,
        allowed_paths: list[str] | None = None,
    ) -> None:
        """Record permission denials for Fix Queue diagnostics."""
        payload = json.dumps(allowed_paths) if allowed_paths is not None else None
        with self.transaction():
            self.conn.execute(
                """
                INSERT INTO permission_denials (
                    action_name,
                    project,
                    target_path,
                    reason_code,
                    scope_level,
                    required_scope_level,
                    allowed_paths
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_name,
                    project,
                    target_path,
                    reason_code,
                    scope_level,
                    required_scope_level,
                    payload,
                ),
            )

    def log_ingestion_error(
        self,
        *,
        source_path: str,
        source_type: str | None,
        project: str | None,
        error_type: str,
        error_message: str | None = None,
    ) -> None:
        """Record ingestion errors for health metrics."""
        with self.transaction():
            self.conn.execute(
                """
                INSERT INTO ingestion_errors (
                    source_path,
                    source_type,
                    project,
                    error_type,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (source_path, source_type, project, error_type, error_message),
            )

    def get_permission_denial_metrics(
        self,
        *,
        project: str | None = None,
        window_hours: int | None = 168,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Summarize permission denials for Fix Queue signals."""
        base_filters = "WHERE 1=1"
        params: list[Any] = []
        if project:
            base_filters += " AND project = ?"
            params.append(project)
        if window_hours is not None:
            base_filters += " AND datetime(created_at) >= datetime('now', ?)"
            params.append(f"-{int(window_hours)} hours")

        counts_cursor = self.conn.execute(
            f"""
            SELECT reason_code, COUNT(*) as count
            FROM permission_denials
            {base_filters}
            GROUP BY reason_code
            """,
            params,
        )
        counts: dict[str, int] = {}
        total = 0
        for row in counts_cursor.fetchall():
            reason = row["reason_code"]
            count = int(row["count"])
            counts[reason] = count
            total += count

        recent_cursor = self.conn.execute(
            f"""
            SELECT action_name, project, target_path, reason_code,
                   scope_level, required_scope_level, allowed_paths, created_at
            FROM permission_denials
            {base_filters}
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            params + [limit],
        )
        recent: list[dict[str, Any]] = []
        for row in recent_cursor.fetchall():
            allowed_paths = None
            if row["allowed_paths"]:
                try:
                    allowed_paths = json.loads(row["allowed_paths"])
                except json.JSONDecodeError:
                    allowed_paths = None
            recent.append(
                {
                    "action_name": row["action_name"],
                    "project": row["project"],
                    "target_path": row["target_path"],
                    "reason_code": row["reason_code"],
                    "scope_level": row["scope_level"],
                    "required_scope_level": row["required_scope_level"],
                    "allowed_paths": allowed_paths,
                    "created_at": row["created_at"],
                }
            )

        return {
            "total": total,
            "counts": counts,
            "recent": recent,
            "window_hours": window_hours,
        }

    def get_ingestion_error_metrics(
        self,
        *,
        project: str | None = None,
        window_hours: int | None = 168,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Summarize ingestion errors for health metrics."""
        base_filters = "WHERE 1=1"
        params: list[Any] = []
        if project:
            base_filters += " AND project = ?"
            params.append(project)
        if window_hours is not None:
            base_filters += " AND datetime(created_at) >= datetime('now', ?)"
            params.append(f"-{int(window_hours)} hours")

        counts_cursor = self.conn.execute(
            f"""
            SELECT error_type, COUNT(*) as count
            FROM ingestion_errors
            {base_filters}
            GROUP BY error_type
            """,
            params,
        )
        counts: dict[str, int] = {}
        total = 0
        for row in counts_cursor.fetchall():
            error_type = row["error_type"] or "unknown"
            count = int(row["count"])
            counts[error_type] = count
            total += count

        recent_cursor = self.conn.execute(
            f"""
            SELECT source_path, source_type, project, error_type, error_message, created_at
            FROM ingestion_errors
            {base_filters}
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            params + [limit],
        )
        recent = [
            {
                "source_path": row["source_path"],
                "source_type": row["source_type"],
                "project": row["project"],
                "error_type": row["error_type"],
                "error_message": row["error_message"],
                "created_at": row["created_at"],
            }
            for row in recent_cursor.fetchall()
        ]

        return {
            "total": total,
            "counts": counts,
            "recent": recent,
            "window_hours": window_hours,
        }

    def get_feedback_metrics(
        self, *, project: str | None = None, window_hours: int = 48
    ) -> dict[str, Any]:
        """Summarize feedback for Fix Queue signals."""
        base_filters = "WHERE 1=1"
        params: list[str] = []
        if project:
            base_filters += " AND project = ?"
            params.append(project)

        cursor = self.conn.execute(
            f"""
            SELECT feedback_reason, COUNT(*) as count
            FROM feedback_log
            {base_filters}
            GROUP BY feedback_reason
            """,
            params,
        )
        counts: dict[str, int] = {}
        total = 0
        for row in cursor.fetchall():
            reason = row["feedback_reason"]
            count = int(row["count"])
            counts[reason] = count
            total += count

        repeated_cursor = self.conn.execute(
            f"""
            SELECT question, project, COUNT(*) as count
            FROM feedback_log
            {base_filters}
            AND datetime(created_at) >= datetime('now', '-{int(window_hours)} hours')
            GROUP BY question, project
            HAVING count > 1
            ORDER BY count DESC
            LIMIT 5
            """,
            params,
        )
        repeated = [
            {
                "question": row["question"],
                "project": row["project"],
                "count": int(row["count"]),
            }
            for row in repeated_cursor.fetchall()
        ]

        not_found = counts.get("didnt_answer", 0)
        not_found_frequency = (not_found / total) if total else 0.0

        return {
            "total": total,
            "counts": counts,
            "not_found_frequency": not_found_frequency,
            "repeated_questions": repeated,
        }

    def get_documents_missing_metadata(
        self, *, limit: int = 5, project: str | None = None
    ) -> list[dict[str, Any]]:
        """Find documents whose required metadata are blank or missing."""
        params: list[Any] = []
        query = """
            SELECT id, project, source_path, source_date, language
            FROM documents
            WHERE (
                source_date IS NULL OR source_date = ''
                OR project = '' OR language = ''
            )
        """
        if project:
            query += " AND project = ?"
            params.append(project)
        query += " LIMIT ?"
        params.append(limit)
        cursor = self.conn.execute(query, params)

        results: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            missing: list[str] = []
            if not row["source_date"]:
                missing.append("source_date")
            if not row["project"]:
                missing.append("project")
            if not row["language"]:
                missing.append("language")
            results.append(
                {
                    "document_id": row["id"],
                    "project": row["project"],
                    "source_path": row["source_path"],
                    "missing_fields": missing,
                }
            )
        return results

    def get_missing_metadata_total(self, *, project: str | None = None) -> int:
        """Return total count of documents missing required metadata."""
        params: list[Any] = []
        query = """
            SELECT COUNT(*) as count
            FROM documents
            WHERE (
                source_date IS NULL OR source_date = ''
                OR project = '' OR language = ''
            )
        """
        if project:
            query += " AND project = ?"
            params.append(project)
        cursor = self.conn.execute(query, params)
        return int(cursor.fetchone()[0])

    def get_missing_metadata_counts(
        self, *, limit: int = 5, project: str | None = None
    ) -> list[dict[str, Any]]:
        """Return top projects with missing metadata by file count."""
        params: list[Any] = []
        query = """
            SELECT COALESCE(NULLIF(project, ''), 'unknown') as project,
                   COUNT(*) as count
            FROM documents
            WHERE (
                source_date IS NULL OR source_date = ''
                OR project = '' OR language = ''
            )
        """
        if project:
            query += " AND project = ?"
            params.append(project)
        query += """
            GROUP BY COALESCE(NULLIF(project, ''), 'unknown')
            ORDER BY count DESC
            LIMIT ?
        """
        params.append(limit)
        cursor = self.conn.execute(query, params)
        return [
            {"project": row["project"], "count": int(row["count"])} for row in cursor.fetchall()
        ]

    def get_stale_document_buckets(
        self,
        *,
        buckets_days: list[int],
        source_type: str | None = None,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return counts of stale documents for the given age buckets."""
        buckets = sorted({int(days) for days in buckets_days if int(days) > 0})
        results: list[dict[str, Any]] = []
        for days in buckets:
            params: list[Any] = [f"-{days} days"]
            query = """
                SELECT COUNT(*) as count
                FROM documents
                WHERE source_date IS NOT NULL
                  AND source_date != ''
                  AND datetime(source_date) <= datetime('now', ?)
            """
            if source_type:
                query += " AND source_type = ?"
                params.append(source_type)
            if project:
                query += " AND project = ?"
                params.append(project)
            count = self.conn.execute(query, params).fetchone()[0]
            results.append({"days": days, "count": int(count)})
        return results

    def get_stale_decision_buckets(
        self,
        *,
        buckets_days: list[int],
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return counts of stale active decisions for the given age buckets."""
        buckets = sorted({int(days) for days in buckets_days if int(days) > 0})
        results: list[dict[str, Any]] = []
        for days in buckets:
            params: list[Any] = [f"-{days} days"]
            query = """
                SELECT COUNT(*) as count
                FROM decisions
                JOIN chunks ON decisions.chunk_id = chunks.id
                JOIN documents ON chunks.document_id = documents.id
                WHERE decisions.status = 'active'
                  AND decisions.decision_date IS NOT NULL
                  AND decisions.decision_date != ''
                  AND datetime(decisions.decision_date) <= datetime('now', ?)
            """
            if project:
                query += " AND documents.project = ?"
                params.append(project)
            count = self.conn.execute(query, params).fetchone()[0]
            results.append({"days": days, "count": int(count)})
        return results

    # Coach Mode settings and suggestion log

    def _ensure_user_settings(self) -> None:
        """Ensure a user_settings row exists."""
        cursor = self.conn.execute("SELECT id FROM user_settings LIMIT 1")
        if cursor.fetchone():
            return

        with self.transaction():
            self.conn.execute(
                """
                INSERT INTO user_settings (global_mode_default, per_project_mode, coach_cooldown_days)
                VALUES ('boring', '{}', 7)
                """
            )

    def get_user_settings(self) -> dict[str, Any]:
        """Get Coach Mode user settings."""
        self._ensure_user_settings()
        cursor = self.conn.execute(
            """
            SELECT global_mode_default, per_project_mode, coach_cooldown_days
            FROM user_settings
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if row is None:
            return {
                "global_mode_default": "boring",
                "coach_mode_default": "boring",
                "per_project_mode": {},
                "coach_cooldown_days": 7,
            }

        try:
            per_project = json.loads(row["per_project_mode"]) or {}
        except (TypeError, json.JSONDecodeError):
            per_project = {}

        global_default = row["global_mode_default"] or "boring"
        return {
            "global_mode_default": global_default,
            "coach_mode_default": global_default,
            "per_project_mode": per_project,
            "coach_cooldown_days": int(row["coach_cooldown_days"]),
        }

    def update_user_settings(
        self,
        *,
        global_mode_default: str | None = None,
        per_project_mode: dict[str, str] | None = None,
        coach_cooldown_days: int | None = None,
    ) -> dict[str, Any]:
        """Update Coach Mode user settings."""
        self._ensure_user_settings()
        current = self.get_user_settings()

        new_global = global_mode_default or current["global_mode_default"]
        new_per_project = (
            per_project_mode if per_project_mode is not None else current["per_project_mode"]
        )
        new_cooldown = (
            int(coach_cooldown_days)
            if coach_cooldown_days is not None
            else current["coach_cooldown_days"]
        )

        with self.transaction():
            self.conn.execute(
                """
                UPDATE user_settings
                SET global_mode_default = ?,
                    per_project_mode = ?,
                    coach_cooldown_days = ?,
                    updated_at = datetime('now')
                """,
                (new_global, json.dumps(new_per_project), int(new_cooldown)),
            )

        return {
            "global_mode_default": new_global,
            "coach_mode_default": new_global,
            "per_project_mode": new_per_project,
            "coach_cooldown_days": int(new_cooldown),
        }

    def log_coach_suggestion(
        self,
        *,
        project: str,
        suggestion_type: str,
        suggestion_fingerprint: str,
        was_shown: bool = True,
    ) -> None:
        """Log a Coach Mode suggestion for cooldown enforcement."""
        with self.transaction():
            self.conn.execute(
                """
                INSERT INTO coach_suggestion_log (
                    project, suggestion_type, suggestion_fingerprint, was_shown
                )
                VALUES (?, ?, ?, ?)
                """,
                (project, suggestion_type, suggestion_fingerprint, 1 if was_shown else 0),
            )

    def is_suggestion_type_in_cooldown(
        self, *, project: str, suggestion_type: str, cooldown_days: int
    ) -> bool:
        """Check if a suggestion type is within cooldown window."""
        cursor = self.conn.execute(
            """
            SELECT 1
            FROM coach_suggestion_log
            WHERE project = ?
              AND suggestion_type = ?
              AND datetime >= datetime('now', ?)
            LIMIT 1
            """,
            (project, suggestion_type, f"-{int(cooldown_days)} days"),
        )
        return cursor.fetchone() is not None

    def get_suggestion_context(self, suggestion_fingerprint: str) -> dict[str, str] | None:
        """Get the latest suggestion context for a fingerprint."""
        cursor = self.conn.execute(
            """
            SELECT project, suggestion_type
            FROM coach_suggestion_log
            WHERE suggestion_fingerprint = ?
            ORDER BY datetime DESC
            LIMIT 1
            """,
            (suggestion_fingerprint,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {"project": row["project"], "suggestion_type": row["suggestion_type"]}


# Global database instance
_db: Database | None = None


def get_database() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


def reset_database() -> None:
    """Reset the global database (useful for testing)."""
    global _db
    if _db:
        _db.close()
    _db = None


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content.

    Args:
        content: Content to hash.

    Returns:
        Hex-encoded hash.
    """
    return hashlib.sha256(content.encode()).hexdigest()
