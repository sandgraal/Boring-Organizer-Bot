"""Search and retrieval functions."""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from bob.config import get_config
from bob.db import get_database
from bob.index.embedder import embed_text
from bob.retrieval.query_parser import filter_results_by_query, parse_query
from bob.retrieval.scoring import HybridScorer, ScoringConfig


@dataclass
class DecisionInfo:
    """Information about a decision associated with a chunk."""

    decision_id: int
    decision_text: str
    status: str  # 'active', 'superseded', 'deprecated'
    superseded_by: int | None = None
    confidence: float = 0.0


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

    # Decision info (if this chunk contains decisions)
    decisions: list[DecisionInfo] = field(default_factory=list)


def normalize_source_types(source_types: list[str] | None) -> list[str] | None:
    """Normalize source type filters to internal identifiers.

    Args:
        source_types: Raw source type filters.

    Returns:
        Normalized list of source types or None.
    """
    if not source_types:
        return None

    aliases = {
        "md": "markdown",
        "markdown": "markdown",
        "pdf": "pdf",
        "docx": "word",
        "word": "word",
        "xlsx": "excel",
        "xls": "excel",
        "excel": "excel",
        "recipe": "recipe",
        "git": "git",
    }

    normalized: list[str] = []
    for source_type in source_types:
        if not source_type:
            continue
        key = source_type.strip().lower()
        normalized.append(aliases.get(key, key))

    unique = sorted(set(normalized))
    return unique or None


def search(
    query: str,
    project: str | None = None,
    projects: list[str] | None = None,
    top_k: int | None = None,
    use_hybrid: bool | None = None,
    scoring_config: ScoringConfig | None = None,
    source_types: list[str] | None = None,
    date_after: datetime | None = None,
    date_before: datetime | None = None,
    language: str | None = None,
) -> list[SearchResult]:
    """Search the knowledge base for relevant chunks.

    Supports advanced query syntax:
        - "phrase": Exact phrase match
        - -term: Exclude results containing term
        - project:name: Filter to specific project

    Args:
        query: Natural language query with optional syntax.
        project: Filter by project (optional; used when `projects` is not provided).
        projects: Filter by multiple projects (optional; overrides `project` when present).
        top_k: Number of results to return.
        use_hybrid: Enable hybrid scoring (vector + keyword matching).
            If None, uses config.search.hybrid_enabled setting.
        scoring_config: Custom scoring configuration for hybrid mode.
            If None and hybrid is enabled, uses config.search settings.
        source_types: Filter by source types (optional).
        date_after: Filter by documents after this date (optional).
        date_before: Filter by documents before this date (optional).
        language: Filter by language (optional).

    Returns:
        List of search results ranked by relevance.
    """
    config = get_config()
    top_k = top_k or config.defaults.top_k

    parsed = parse_query(query)

    # Derive project filters: prefer explicit list, fallback to single project,
    # and always include parsed project filters without duplicates.
    project_candidates: list[str] = []
    seen_projects: set[str] = set()

    def _add_project(name: str | None) -> None:
        if name and name not in seen_projects:
            seen_projects.add(name)
            project_candidates.append(name)

    if projects:
        for project_name in projects:
            _add_project(project_name)
    else:
        _add_project(project)

    _add_project(parsed.project_filter)
    effective_projects = project_candidates or None
    normalized_types = normalize_source_types(source_types)

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

    # Embed the query text (without syntax markers)
    search_text = parsed.text or query
    query_embedding = embed_text(search_text)

    # Search the database - fetch more if using filters or hybrid (for post-filtering)
    db = get_database()
    fetch_multiplier = 3 if use_hybrid else 1
    has_metadata_filters = bool(normalized_types or date_after or date_before or language)
    if parsed.has_filters() or has_metadata_filters:
        fetch_multiplier = max(fetch_multiplier, 5)  # Fetch more when filtering
    fetch_limit = top_k * fetch_multiplier

    raw_results = db.search_similar(
        query_embedding,
        limit=fetch_limit,
        projects=effective_projects,
        source_types=normalized_types,
        date_after=date_after,
        date_before=date_before,
        language=language,
    )

    # Apply phrase and exclusion filters
    if parsed.has_filters():
        raw_results = filter_results_by_query(raw_results, parsed, content_key="content")

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


def enrich_with_decisions(results: list[SearchResult]) -> list[SearchResult]:
    """Enrich search results with decision information.

    If a chunk has associated decisions stored in the database,
    adds them to the result so they can be displayed.

    Args:
        results: List of search results.

    Returns:
        Same results with decisions field populated.
    """
    if not results:
        return results

    db = get_database()
    chunk_ids = [r.chunk_id for r in results]

    # Query decisions for all chunks at once
    placeholders = ",".join("?" * len(chunk_ids))
    cursor = db.conn.execute(
        f"""
        SELECT
            chunk_id,
            id as decision_id,
            decision_text,
            status,
            superseded_by,
            confidence
        FROM decisions
        WHERE chunk_id IN ({placeholders})
        """,
        chunk_ids,
    )

    # Group decisions by chunk_id
    decisions_by_chunk: dict[int, list[DecisionInfo]] = {}
    for row in cursor.fetchall():
        chunk_id = row["chunk_id"]
        if chunk_id not in decisions_by_chunk:
            decisions_by_chunk[chunk_id] = []
        decisions_by_chunk[chunk_id].append(
            DecisionInfo(
                decision_id=row["decision_id"],
                decision_text=row["decision_text"],
                status=row["status"],
                superseded_by=row["superseded_by"],
                confidence=row["confidence"],
            )
        )

    # Enrich results
    for result in results:
        if result.chunk_id in decisions_by_chunk:
            result.decisions = decisions_by_chunk[result.chunk_id]

    return results


def has_superseded_decisions(results: list[SearchResult]) -> bool:
    """Check if any results contain superseded decisions.

    Args:
        results: Search results.

    Returns:
        True if any result has a superseded decision.
    """
    for result in results:
        for decision in result.decisions:
            if decision.status == "superseded":
                return True
    return False


def get_active_decisions(results: list[SearchResult]) -> list[DecisionInfo]:
    """Get all active decisions from search results.

    Args:
        results: Search results.

    Returns:
        List of active decisions found in results.
    """
    active: list[DecisionInfo] = []
    for result in results:
        for decision in result.decisions:
            if decision.status == "active":
                active.append(decision)
    return active
