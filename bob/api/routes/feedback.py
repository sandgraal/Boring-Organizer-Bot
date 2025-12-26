"""Feedback endpoint for capturing user signals."""

from __future__ import annotations

from fastapi import APIRouter

from bob.api.schemas import FeedbackRequest, FeedbackResponse
from bob.db.database import get_database

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Log feedback so Fix Queue metrics can prioritize tasks."""
    db = get_database()
    db.log_feedback(
        question=request.question,
        project=request.project,
        answer_id=request.answer_id,
        feedback_reason=request.feedback_reason,
        retrieved_source_ids=request.retrieved_source_ids,
    )
    return FeedbackResponse(success=True)
