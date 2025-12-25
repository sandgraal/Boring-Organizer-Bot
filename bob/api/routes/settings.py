"""Settings endpoints for Coach Mode preferences."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from bob.api.schemas import (
    CoachSettings,
    SettingsUpdateResponse,
    SuggestionDismissRequest,
    SuggestionDismissResponse,
)
from bob.db.database import get_database

router = APIRouter()


@router.get("/settings", response_model=CoachSettings)
def get_settings() -> CoachSettings:
    """Get persisted Coach Mode settings."""
    db = get_database()
    settings = db.get_user_settings()
    return CoachSettings(**settings)


@router.put("/settings", response_model=SettingsUpdateResponse)
def update_settings(request: CoachSettings) -> SettingsUpdateResponse:
    """Update persisted Coach Mode settings."""
    db = get_database()
    db.update_user_settings(
        global_mode_default=request.coach_mode_default,
        per_project_mode=request.per_project_mode,
        coach_cooldown_days=request.coach_cooldown_days,
    )
    return SettingsUpdateResponse(success=True)


@router.post("/suggestions/{suggestion_id}/dismiss", response_model=SuggestionDismissResponse)
def dismiss_suggestion(
    suggestion_id: str, request: SuggestionDismissRequest | None = None
) -> SuggestionDismissResponse:
    """Record a dismissal to enforce cooldown rules."""
    db = get_database()
    settings = db.get_user_settings()
    cooldown_days = int(settings.get("coach_cooldown_days", 7))

    suggestion_type = request.suggestion_type if request else None
    project = request.project if request else None

    if not suggestion_type or not project:
        context = db.get_suggestion_context(suggestion_id)
        if context:
            suggestion_type = suggestion_type or context.get("suggestion_type")
            project = project or context.get("project")

    if not suggestion_type:
        raise HTTPException(status_code=400, detail="suggestion_type is required")

    project_key = project or "all"
    db.log_coach_suggestion(
        project=project_key,
        suggestion_type=suggestion_type,
        suggestion_fingerprint=suggestion_id,
        was_shown=False,
    )

    cooldown_until = datetime.utcnow() + timedelta(days=cooldown_days)
    return SuggestionDismissResponse(success=True, cooldown_until=cooldown_until)
