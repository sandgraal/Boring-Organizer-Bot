"""Utility helpers shared across API routes."""

from __future__ import annotations

from typing import Iterable

from bob.answer.formatter import get_date_confidence, is_outdated
from bob.api.schemas import Source, SourceLocator
from bob.retrieval.search import SearchResult


def build_locator(result: SearchResult) -> SourceLocator:
    """Build a SourceLocator from a SearchResult's locator metadata."""
    lv = result.locator_value or {}
    return SourceLocator(
        type=result.locator_type,
        heading=lv.get("heading"),
        start_line=lv.get("start_line"),
        end_line=lv.get("end_line"),
        page=lv.get("page"),
        total_pages=lv.get("total_pages"),
        paragraph_index=lv.get("paragraph_index"),
        sheet_name=lv.get("sheet_name"),
        row_count=lv.get("row_count"),
        section=lv.get("section"),
        **{k: v for k, v in lv.items() if k not in {"heading", "start_line", "end_line", "page", "total_pages", "paragraph_index", "sheet_name", "row_count", "section"}},
    )


def convert_result_to_source(result: SearchResult, index: int) -> Source:
    """Convert a SearchResult to a Source model used in API responses."""
    confidence = get_date_confidence(result.source_date)
    outdated_flag = is_outdated(result.source_date)

    snippet = result.content[:500]
    if len(result.content) > 500:
        snippet += "..."

    return Source(
        id=index,
        chunk_id=result.chunk_id,
        file_path=result.source_path,
        file_type=result.source_type,
        locator=build_locator(result),
        snippet=snippet,
        date=result.source_date,
        date_confidence=confidence.value,
        project=result.project,
        may_be_outdated=outdated_flag,
        similarity_score=round(result.score, 4),
        git_repo=result.git_repo,
        git_commit=result.git_commit,
    )


def compute_overall_confidence(sources: Iterable[Source]) -> str | None:
    """Return the minimum date confidence level among all sources."""
    source_list = list(sources)
    if not source_list:
        return None

    priority = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    lowest = min(source_list, key=lambda s: priority.get(s.date_confidence, 0))
    return lowest.date_confidence
