"""Search and retrieval functions."""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bob.config import get_config
from bob.db import get_database
from bob.index.embedder import embed_text
from bob.retrieval.scoring import HybridScorer, ScoringConfig


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
    use_hybrid: bool | None = None,
    scoring_config: ScoringConfig | None = None,
) -> list[SearchResult]:
    """Search the knowledge base for relevant chunks.

    Args:
        query: Natural language query.
        project: Filter by project (optional).
        top_k: Number of results to return.
        use_hybrid: Enable hybrid scoring (vector + keyword matching).
            If None, uses config.search.hybrid_enabled setting.
        scoring_config: Custom scoring configuration for hybrid mode.
            If None and hybrid is enabled, uses config.search settings.

    Returns:
        List of search results ranked by relevance.
    """
    config = get_config()
    top_k = top_k or config.defaults.top_k

    # Determine if hybrid scoring should be used
    if use_hybrid is None:
        use_hybrid = config.search.hybrid_enabled

    # Build scoring config from settings if not provided
    if use_hybrid and scoring_config is None:
        scoring_config = ScoringConfig(
            vector_weight=config.search.vector_weight,
            keyword_weight=config.search.keyword_weight,
            bm25_k1=config.search.bm25_k1,
            bm25_b=config.search.bm25_b,
            recency_boost_enabled=config.search.recency_boost_enabled,
            recency_half_life_days=config.search.recency_half_life_days,
        )

    # Embed the query
    query_embedding = embed_text(query)

    # Search the database - fetch more if using hybrid (for re-ranking)
    db = get_database()
    fetch_limit = top_k * 3 if use_hybrid else top_k
    raw_results = db.search_similar(query_embedding, limit=fetch_limit, project=project)

    if use_hybrid and raw_results:
        # Apply hybrid scoring
        vector_scores = [max(0.0, 1.0 - row.get("distance", 0)) for row in raw_results]
        scorer = HybridScorer(scoring_config)
        scored_results = scorer.score_results(query, raw_results, vector_scores)

        # Convert scored results to SearchResult objects
        hybrid_results: list[SearchResult] = []
        for scored in scored_results[:top_k]:
            row = scored.metadata
            hybrid_results.append(_row_to_search_result(row, scored.final_score))
        return hybrid_results

    # Standard vector-only scoring
    results: list[SearchResult] = []
    for row in raw_results[:top_k]:
        distance = row.get("distance", 0)
        score = max(0.0, 1.0 - distance)
        results.append(_row_to_search_result(row, score))

    return results


def _row_to_search_result(row: dict[str, Any], score: float) -> SearchResult:
    """Convert a database row to a SearchResult.

    Args:
        row: Database row dictionary.
        score: Pre-computed score (0-1).

    Returns:
        SearchResult object.
    """
    # Parse locator value from JSON if needed
    locator_value = row["locator_value"]
    if isinstance(locator_value, str):
        locator_value = json.loads(locator_value)

    # Parse date if present
    source_date = None
    if row.get("source_date"):
        with suppress(ValueError):
            source_date = datetime.fromisoformat(row["source_date"])

    return SearchResult(
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
