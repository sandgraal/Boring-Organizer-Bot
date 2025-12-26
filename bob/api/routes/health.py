"""Health check endpoint."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter

from bob.api.schemas import FailureSignal, FixQueueResponse, FixQueueTask
from bob.db.database import get_database

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str | int]:
    """Health check endpoint.

    Returns server status, version, and basic database stats.
    """
    try:
        db = get_database()
        stats = db.get_stats()
        db_status = "connected"
    except Exception:
        db_status = "error"
        stats = {"document_count": 0}

    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": db_status,
        "indexed_documents": stats.get("document_count", 0),
    }


def _priority_from_ratio(value: float, scale: int = 10, *, min_value: int = 1) -> int:
    """Turn a ratio into a 1-5 priority bucket."""
    bucket = max(min_value, min(5, int(value * scale) or min_value))
    return bucket


def _build_fix_queue_tasks(
    metrics: dict[str, Any],
    metadata_deficits: list[dict[str, Any]],
    project: str | None,
) -> list[FixQueueTask]:
    """Create Fix Queue tasks from health signals."""
    tasks: list[FixQueueTask] = []
    freq = metrics.get("not_found_frequency", 0.0)
    total_feedback = metrics.get("total", 0)
    if freq > 0 and total_feedback > 0:
        project_label = project or "all projects"
        id_label = (project or "global").replace(" ", "-")
        task_id = f"not-found-{id_label}"
        tasks.append(
            FixQueueTask(
                id=task_id,
                action="run_routine",
                target="routines/daily-checkin",
                reason=(
                    f"{freq * 100:.1f}% of feedback entries "
                    f"from {project_label} were 'didn't answer'"
                ),
                priority=_priority_from_ratio(freq),
            )
        )

    for idx, deficit in enumerate(metadata_deficits, start=1):
        missing = ", ".join(deficit.get("missing_fields", [])) or "metadata"
        tasks.append(
            FixQueueTask(
                id=f"metadata-{deficit['document_id']}-{idx}",
                action="fix_metadata",
                target=deficit["source_path"],
                reason=f"Missing metadata fields: {missing}",
                priority=3,
            )
        )

    for repeated in metrics.get("repeated_questions", []):
        hashed = hashlib.sha1(repeated["question"].encode("utf-8")).hexdigest()[:10]
        tasks.append(
            FixQueueTask(
                id=f"repeat-{hashed}",
                action="run_routine",
                target=repeated["question"],
                reason=f"Question repeated {repeated['count']} times in the last 48h",
                priority=max(1, min(5, repeated["count"])),
            )
        )

    return tasks


@router.get("/health/fix-queue", response_model=FixQueueResponse)
def health_fix_queue(project: str | None = None) -> FixQueueResponse:
    """Return Fix Queue signals and tasks derived from failure metrics."""
    db = get_database()
    metrics = db.get_feedback_metrics(project=project)
    metadata_deficits = db.get_documents_missing_metadata()

    failure_signals = [
        FailureSignal(
            name="not_found_frequency",
            value=metrics.get("not_found_frequency", 0.0),
            details=(
                f"{metrics.get('counts', {}).get('didnt_answer', 0)} of "
                f"{metrics.get('total', 0)} feedback entries were 'didn't answer'"
            ),
        ),
        FailureSignal(
            name="metadata_deficits",
            value=len(metadata_deficits),
            details="Documents missing source_date/project/language metadata",
        ),
        FailureSignal(
            name="repeated_questions",
            value=len(metrics.get("repeated_questions", [])),
            details="Repeated queries observed over the past 48 hours",
        ),
    ]

    tasks = _build_fix_queue_tasks(metrics, metadata_deficits, project)
    return FixQueueResponse(failure_signals=failure_signals, tasks=tasks)
