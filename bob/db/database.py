"""Database management for B.O.B.

Handles SQLite database connections, migrations, and vector storage.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
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

        self._conn: sqlite3.Connection | None = None
        self._has_vec: bool | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._conn.row_factory = sqlite3.Row

            # Enable WAL mode for better concurrency
            if get_config().database.wal_mode:
                self._conn.execute("PRAGMA journal_mode=WAL")

            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys=ON")

            # Try to load sqlite-vec
            self._try_load_vec()

        return self._conn

    def _try_load_vec(self) -> None:
        """Try to load sqlite-vec extension."""
        try:
            import sqlite_vec

            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)
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
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

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
                    self.conn.execute(statement)

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
    ) -> list[dict[str, Any]]:
        """Search for similar chunks.

        Args:
            query_embedding: Query embedding vector.
            limit: Maximum number of results.
            project: Filter by project (optional).

        Returns:
            List of matching chunks with scores.
        """
        if self.has_vec:
            return self._search_vec(query_embedding, limit, project)
        else:
            return self._search_fallback(query_embedding, limit, project)

    def _search_vec(
        self,
        query_embedding: npt.NDArray[np.float32],
        limit: int,
        project: str | None,
    ) -> list[dict[str, Any]]:
        """Search using sqlite-vec."""
        if project:
            cursor = self.conn.execute(
                """
                SELECT
                    c.id, c.content, c.locator_type, c.locator_value,
                    d.source_path, d.source_type, d.project, d.source_date,
                    d.git_repo, d.git_commit,
                    vec_distance_cosine(e.embedding, ?) as distance
                FROM chunk_embeddings e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                WHERE d.project = ?
                ORDER BY distance ASC
                LIMIT ?
                """,
                (query_embedding.tobytes(), project, limit),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT
                    c.id, c.content, c.locator_type, c.locator_value,
                    d.source_path, d.source_type, d.project, d.source_date,
                    d.git_repo, d.git_commit,
                    vec_distance_cosine(e.embedding, ?) as distance
                FROM chunk_embeddings e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                ORDER BY distance ASC
                LIMIT ?
                """,
                (query_embedding.tobytes(), limit),
            )

        return [dict(row) for row in cursor.fetchall()]

    def _search_fallback(
        self,
        query_embedding: npt.NDArray[np.float32],
        limit: int,
        project: str | None,
    ) -> list[dict[str, Any]]:
        """Fallback search using cosine similarity in Python."""
        import numpy as np

        # Get all embeddings (not efficient for large datasets)
        if project:
            cursor = self.conn.execute(
                """
                SELECT
                    e.chunk_id, e.embedding,
                    c.id, c.content, c.locator_type, c.locator_value,
                    d.source_path, d.source_type, d.project, d.source_date,
                    d.git_repo, d.git_commit
                FROM chunk_embeddings_fallback e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                WHERE d.project = ?
                """,
                (project,),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT
                    e.chunk_id, e.embedding,
                    c.id, c.content, c.locator_type, c.locator_value,
                    d.source_path, d.source_type, d.project, d.source_date,
                    d.git_repo, d.git_commit
                FROM chunk_embeddings_fallback e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN documents d ON d.id = c.document_id
                """
            )

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
