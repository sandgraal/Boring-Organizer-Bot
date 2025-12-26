"""Ask endpoint for querying the knowledge base."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from bob.api.schemas import (
    AskFooter,
    AskRequest,
    AskResponse,
)
from bob.api.utils import compute_overall_confidence, convert_result_to_source
from bob.coach.engine import generate_coach_suggestions
from bob.db.database import get_database
from bob.retrieval.search import search

router = APIRouter()


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
    projects: list[str] | None = None
    source_types = None
    date_after = None
    date_before = None
    language = None
    if request.filters:
        source_types = request.filters.types
        date_after = request.filters.date_after
        date_before = request.filters.date_before
        language = request.filters.language
        if request.filters.projects:
            candidates = [p for p in request.filters.projects if p]
            if candidates:
                projects = candidates
                project = candidates[0]

    try:
        # Perform search
        results = search(
            query=request.query,
            project=project,
            projects=projects,
            top_k=request.top_k,
            source_types=source_types,
            date_after=date_after,
            date_before=date_before,
            language=language,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}") from e

    # Convert results to sources
    sources = [convert_result_to_source(result, idx + 1) for idx, result in enumerate(results)]

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
    overall_confidence = compute_overall_confidence(sources)
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
