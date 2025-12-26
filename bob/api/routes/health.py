"""Health check endpoint."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter

from bob.api.schemas import FailureSignal, FixQueueResponse, FixQueueTask
from bob.config import get_config
from bob.db.database import get_database
from bob.health.lint import LintIssue, collect_capture_lint_issues

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


def _invert_priority(bucket: int, *, min_value: int = 1, max_value: int = 5) -> int:
    """Invert a priority bucket so higher severity yields lower priority numbers."""
    return max_value + min_value - bucket


def _priority_from_ratio(value: float, scale: int = 10, *, min_value: int = 1) -> int:
    """Turn a ratio into a 1-5 priority bucket (1 is highest)."""
    normalized = max(0.0, min(1.0, value))
    bucket = max(min_value, min(5, int(normalized * scale) or min_value))
    return _invert_priority(bucket, min_value=min_value, max_value=5)


def _priority_from_count(value: int, *, min_value: int = 1, max_value: int = 5) -> int:
    """Turn a count into a 1-5 priority bucket (1 is highest)."""
    bucket = max(min_value, min(max_value, value))
    return _invert_priority(bucket, min_value=min_value, max_value=max_value)


def _format_permission_denial_details(metrics: dict[str, Any]) -> str:
    """Describe permission denials in a compact sentence."""
    total = metrics.get("total", 0)
    if total == 0:
        return "No permission denials recorded."

    counts = metrics.get("counts", {})
    window_hours = metrics.get("window_hours")
    scope_count = counts.get("scope", 0)
    path_count = counts.get("path", 0)
    parts = []
    if scope_count:
        parts.append(f"{scope_count} scope")
    if path_count:
        parts.append(f"{path_count} path")
    if not parts:
        parts.append("unknown")

    window_note = ""
    if window_hours is not None:
        window_note = f" in the last {window_hours}h"

    label = "denial" if total == 1 else "denials"
    return f"{', '.join(parts)} {label}{window_note}"


def _build_fix_queue_tasks(
    metrics: dict[str, Any],
    metadata_deficits: list[dict[str, Any]],
    project: str | None,
    permission_denials: list[dict[str, Any]],
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
                priority=_priority_from_count(repeated["count"]),
            )
        )

    seen_permission_tasks: set[tuple[str, str, str]] = set()
    for denial in permission_denials:
        reason_code = denial.get("reason_code", "unknown")
        target_path = denial.get("target_path", "unknown")
        action_name = denial.get("action_name", "routine")
        scope_level = denial.get("scope_level")
        required_scope = denial.get("required_scope_level")
        task_key = (reason_code, action_name, target_path)
        if task_key in seen_permission_tasks:
            continue
        seen_permission_tasks.add(task_key)

        if reason_code == "scope":
            action = "raise_scope"
            target = "permissions.default_scope"
            reason = (
                f"Routine '{action_name}' blocked at scope {scope_level}; "
                f"requires {required_scope} for {target_path}"
            )
            priority = 2
        elif reason_code == "path":
            action = "allow_path"
            target = target_path
            reason = (
                f"Routine '{action_name}' tried to write outside allowed paths: "
                f"{target_path}"
            )
            priority = 3
        else:
            action = "review_permissions"
            target = target_path
            reason = f"Permission denial for '{action_name}' writing to {target_path}"
            priority = 3

        task_id = hashlib.sha1(
            f"{reason_code}:{action_name}:{target_path}".encode("utf-8")
        ).hexdigest()[:10]
        tasks.append(
            FixQueueTask(
                id=f"permission-{task_id}",
                action=action,
                target=target,
                reason=reason,
                priority=priority,
            )
        )

    return tasks


def _build_lint_tasks(lint_issues: list[LintIssue]) -> list[FixQueueTask]:
    """Create Fix Queue tasks from capture lint issues."""
    tasks: list[FixQueueTask] = []
    for issue in lint_issues:
        task_hash = hashlib.sha1(
            f"{issue.code}:{issue.file_path}".encode("utf-8")
        ).hexdigest()[:10]
        action = "fix_metadata" if issue.code == "missing_metadata" else "fix_capture"
        tasks.append(
            FixQueueTask(
                id=f"lint-{issue.code}-{task_hash}",
                action=action,
                target=str(issue.file_path),
                reason=issue.message,
                priority=issue.priority,
            )
        )
    return tasks


@router.get("/health/fix-queue", response_model=FixQueueResponse)
def health_fix_queue(project: str | None = None) -> FixQueueResponse:
    """Return Fix Queue signals and tasks derived from failure metrics."""
    db = get_database()
    metrics = db.get_feedback_metrics(project=project)
    metadata_deficits = db.get_documents_missing_metadata()
    permission_metrics = db.get_permission_denial_metrics(project=project)
    lint_issues = collect_capture_lint_issues(get_config())

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
        FailureSignal(
            name="permission_denials",
            value=permission_metrics.get("total", 0),
            details=_format_permission_denial_details(permission_metrics),
        ),
    ]

    tasks = _build_fix_queue_tasks(
        metrics, metadata_deficits, project, permission_metrics.get("recent", [])
    )
    tasks.extend(_build_lint_tasks(lint_issues))
    return FixQueueResponse(failure_signals=failure_signals, tasks=tasks)
