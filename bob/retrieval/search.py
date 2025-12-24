"""Search and retrieval functions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bob.config import get_config
from bob.db import get_database
from bob.index.embedder import embed_text


@dataclass
class SearchResult:
    """A search result with metadata and ranking info."""

    chunk_id: int
    content: str
    score: float  # 0-1, higher is better (converted from distance)

    # Locator
    source_path: str
    source_type: str
    locator_type: str
    locator_value: dict[str, Any]

    # Metadata
    project: str
    source_date: datetime | None
    git_repo: str | None
    git_commit: str | None


def search(
    query: str,
    project: str | None = None,
    top_k: int | None = None,
) -> list[SearchResult]:
    """Search the knowledge base for relevant chunks.

    Args:
        query: Natural language query.
        project: Filter by project (optional).
        top_k: Number of results to return.

    Returns:
        List of search results ranked by relevance.
    """
    config = get_config()
    top_k = top_k or config.defaults.top_k

    # Embed the query
    query_embedding = embed_text(query)

    # Search the database
    db = get_database()
    raw_results = db.search_similar(query_embedding, limit=top_k, project=project)

    # Convert to SearchResult objects
    results: list[SearchResult] = []
    for row in raw_results:
        # Parse locator value from JSON if needed
        locator_value = row["locator_value"]
        if isinstance(locator_value, str):
            locator_value = json.loads(locator_value)

        # Parse date if present
        source_date = None
        if row.get("source_date"):
            try:
                source_date = datetime.fromisoformat(row["source_date"])
            except ValueError:
                pass

        # Convert distance to score (lower distance = higher score)
        distance = row.get("distance", 0)
        score = max(0.0, 1.0 - distance)

        results.append(
            SearchResult(
                chunk_id=row["id"],
                content=row["content"],
                score=score,
                source_path=row["source_path"],
                source_type=row["source_type"],
                locator_type=row["locator_type"],
                locator_value=locator_value,
                project=row["project"],
                source_date=source_date,
                git_repo=row.get("git_repo"),
                git_commit=row.get("git_commit"),
            )
        )

    return results


def search_by_metadata(
    project: str | None = None,
    source_type: str | None = None,
    date_after: datetime | None = None,
    date_before: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search documents by metadata (without semantic search).

    Args:
        project: Filter by project.
        source_type: Filter by source type.
        date_after: Filter by documents after this date.
        date_before: Filter by documents before this date.
        limit: Maximum results.

    Returns:
        List of matching documents.
    """
    db = get_database()

    conditions = []
    params = []

    if project:
        conditions.append("project = ?")
        params.append(project)

    if source_type:
        conditions.append("source_type = ?")
        params.append(source_type)

    if date_after:
        conditions.append("source_date >= ?")
        params.append(date_after.isoformat())

    if date_before:
        conditions.append("source_date <= ?")
        params.append(date_before.isoformat())

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    cursor = db.conn.execute(
        f"""
        SELECT * FROM documents
        WHERE {where_clause}
        ORDER BY source_date DESC
        LIMIT ?
        """,
        (*params, limit),
    )

    return [dict(row) for row in cursor.fetchall()]
