"""Ask endpoint for querying the knowledge base."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from bob.answer.formatter import get_date_confidence, is_outdated
from bob.api.schemas import (
    AskFooter,
    AskRequest,
    AskResponse,
    Source,
    SourceLocator,
)
from bob.coach.engine import generate_coach_suggestions
from bob.db.database import get_database
from bob.retrieval.search import SearchResult, search

router = APIRouter()


def _build_locator(result: SearchResult) -> SourceLocator:
    """Build a SourceLocator from a SearchResult's locator_value.

    Args:
        result: Search result with locator information.

    Returns:
        SourceLocator model.
    """
    lv = result.locator_value
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
        # Pass through any extra fields
        **{
            k: v
            for k, v in lv.items()
            if k
            not in {
                "heading",
                "start_line",
                "end_line",
                "page",
                "total_pages",
                "paragraph_index",
                "sheet_name",
                "row_count",
                "section",
            }
        },
    )


def _convert_result_to_source(result: SearchResult, index: int) -> Source:
    """Convert a SearchResult to a Source model.

    Args:
        result: Search result from retrieval.
        index: 1-based index for the source ID.

    Returns:
        Source model for API response.
    """
    confidence = get_date_confidence(result.source_date)
    outdated = is_outdated(result.source_date)

    # Create snippet: first 500 chars of content
    snippet = result.content[:500]
    if len(result.content) > 500:
        snippet += "..."

    return Source(
        id=index,
        chunk_id=result.chunk_id,
        file_path=result.source_path,
        file_type=result.source_type,
        locator=_build_locator(result),
        snippet=snippet,
        date=result.source_date,
        date_confidence=confidence.value,
        project=result.project,
        may_be_outdated=outdated,
        similarity_score=round(result.score, 4),
        git_repo=result.git_repo,
        git_commit=result.git_commit,
    )


def _compute_overall_confidence(sources: list[Source]) -> str | None:
    """Compute overall date confidence from sources.

    Returns the lowest confidence level among all sources.

    Args:
        sources: List of sources.

    Returns:
        Overall confidence level or None if no sources.
    """
    if not sources:
        return None

    # Order: UNKNOWN < LOW < MEDIUM < HIGH
    priority = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    lowest = min(sources, key=lambda s: priority.get(s.date_confidence, 0))
    return lowest.date_confidence


def _resolve_coach_mode(
    request: AskRequest, project: str | None, settings: dict[str, object]
) -> bool:
    """Resolve Coach Mode setting for a request."""
    if request.coach_mode_enabled is not None:
        return request.coach_mode_enabled

    per_project = settings.get("per_project_mode", {}) if settings else {}
    if project and isinstance(per_project, dict):
        mode = per_project.get(project)
        if isinstance(mode, str):
            return mode.lower() == "coach"

    default_mode = settings.get("global_mode_default", "boring")
    return str(default_mode).lower() == "coach"


@router.post("/ask", response_model=AskResponse)
def ask_query(request: AskRequest) -> AskResponse:
    """Query the knowledge base and return answer with citations.

    Args:
        request: Query request with optional filters.

    Returns:
        Answer with sources and footer metadata.
    """
    start_time = time.time()

    # Extract project filter from filters
    project = None
    source_types = None
    date_after = None
    date_before = None
    language = None
    if request.filters and request.filters.projects:
        # For now, use first project filter (multi-project TODO)
        project = request.filters.projects[0]
        source_types = request.filters.types
        date_after = request.filters.date_after
        date_before = request.filters.date_before
        language = request.filters.language
    elif request.filters:
        source_types = request.filters.types
        date_after = request.filters.date_after
        date_before = request.filters.date_before
        language = request.filters.language

    try:
        # Perform search
        results = search(
            query=request.query,
            project=project,
            top_k=request.top_k,
            source_types=source_types,
            date_after=date_after,
            date_before=date_before,
            language=language,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}") from e

    # Convert results to sources
    sources = [_convert_result_to_source(result, idx + 1) for idx, result in enumerate(results)]

    # Build response
    elapsed_ms = int((time.time() - start_time) * 1000)
    db = get_database()
    settings = db.get_user_settings()
    coach_enabled = _resolve_coach_mode(request, project, settings)
    coach_cooldown_days = int(settings.get("coach_cooldown_days", 7))

    if not sources:
        # No results found
        suggestions = generate_coach_suggestions(
            sources=[],
            overall_confidence=None,
            not_found=True,
            project=project,
            coach_enabled=coach_enabled,
            cooldown_days=coach_cooldown_days,
            db=db,
            override_cooldown=request.coach_show_anyway,
        )
        project_key = project or "all"
        for suggestion in suggestions:
            db.log_coach_suggestion(
                project=project_key,
                suggestion_type=suggestion.type,
                suggestion_fingerprint=suggestion.id,
                was_shown=True,
            )
        return AskResponse(
            answer=None,
            coach_mode_enabled=coach_enabled,
            suggestions=suggestions,
            sources=[],
            footer=AskFooter(
                source_count=0,
                date_confidence=None,
                may_be_outdated=False,
                outdated_source_count=0,
                not_found=True,
                not_found_message="No indexed documents contain information matching your query.",
            ),
            query_time_ms=elapsed_ms,
        )

    # Build answer from top result
    top_source = sources[0]
    answer = top_source.snippet

    # Compute footer
    outdated_count = sum(1 for s in sources if s.may_be_outdated)
    overall_confidence = _compute_overall_confidence(sources)
    any_outdated = outdated_count > 0
    suggestions = generate_coach_suggestions(
        sources=sources,
        overall_confidence=overall_confidence,
        not_found=False,
        project=project,
        coach_enabled=coach_enabled,
        cooldown_days=coach_cooldown_days,
        db=db,
        override_cooldown=request.coach_show_anyway,
    )
    project_key = project or "all"
    for suggestion in suggestions:
        db.log_coach_suggestion(
            project=project_key,
            suggestion_type=suggestion.type,
            suggestion_fingerprint=suggestion.id,
            was_shown=True,
        )

    return AskResponse(
        answer=answer,
        coach_mode_enabled=coach_enabled,
        suggestions=suggestions,
        sources=sources,
        footer=AskFooter(
            source_count=len(sources),
            date_confidence=overall_confidence,
            may_be_outdated=any_outdated,
            outdated_source_count=outdated_count,
            not_found=False,
            not_found_message=None,
        ),
        query_time_ms=elapsed_ms,
    )
