"""Health check endpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
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


def _format_low_volume_details(projects: list[dict[str, Any]], threshold: int) -> str:
    """Describe low document coverage by project."""
    if not projects:
        return "No projects below minimum document count."
    preview = ", ".join(
        f"{item['project'] or 'unknown'} ({item['document_count']})" for item in projects[:3]
    )
    label = "project" if len(projects) == 1 else "projects"
    return f"{len(projects)} {label} under {threshold} docs: {preview}"


def _format_low_hit_rate_details(projects: list[dict[str, Any]], threshold: float) -> str:
    """Describe low retrieval hit rates by project."""
    if not projects:
        return "No projects below hit-rate threshold."
    preview = ", ".join(
        f"{item['project']} ({item['hit_rate'] * 100:.0f}% hits)" for item in projects[:3]
    )
    label = "project" if len(projects) == 1 else "projects"
    return f"{len(projects)} {label} below {threshold * 100:.0f}% hit rate: {preview}"


def _format_metadata_offenders_details(entries: list[dict[str, Any]]) -> str:
    """Describe top metadata offenders by file count."""
    if not entries:
        return "No metadata offenders detected."
    preview = ", ".join(f"{item['project']} ({item['count']})" for item in entries[:3])
    label = "project" if len(entries) == 1 else "projects"
    return f"Top {label}: {preview}"


def _format_staleness_details(buckets: list[dict[str, Any]], label: str) -> str:
    """Describe staleness buckets for notes or decisions."""
    if not buckets:
        return f"No {label} staleness data."
    preview = ", ".join(f"{item['days']}d+: {item['count']}" for item in buckets)
    return f"{label} older than {preview}"


def _format_ingestion_error_details(metrics: dict[str, Any]) -> str:
    """Describe ingestion errors by type with recent file previews."""
    total = metrics.get("total", 0)
    if total == 0:
        return "No ingestion errors recorded."
    counts = metrics.get("counts", {})
    parts: list[str] = []
    for label in ("parse_error", "no_text", "oversize"):
        count = counts.get(label, 0)
        if count:
            parts.append(f"{label.replace('_', ' ')}: {count}")
    if not parts and counts:
        for key, count in counts.items():
            parts.append(f"{str(key).replace('_', ' ')}: {count}")
    detail = ", ".join(parts) if parts else f"{total} ingestion errors logged."
    recent = metrics.get("recent", [])
    if recent:
        preview = ", ".join(
            Path(item["source_path"]).name
            for item in recent[:3]
            if item.get("source_path")
        )
        if preview:
            detail = f"{detail}. Recent: {preview}"
    return detail


def _format_ingestion_task_reason(error_type: str, message: str | None) -> str:
    """Create a user-facing reason string for ingestion failures."""
    label = error_type.replace("_", " ")
    if message:
        trimmed = message.strip()
        if len(trimmed) > 160:
            trimmed = f"{trimmed[:157]}..."
        return f"{label} while indexing: {trimmed}"
    return f"{label} while indexing this file."


def _priority_for_ingestion_error(error_type: str | None) -> int:
    """Map ingestion error types to priority buckets."""
    if error_type == "parse_error":
        return 2
    if error_type == "no_text":
        return 3
    if error_type == "oversize":
        return 3
    return 4


def _staleness_value(buckets: list[dict[str, Any]]) -> int:
    """Use the smallest bucket (most inclusive) count as the signal value."""
    if not buckets:
        return 0
    return int(buckets[0]["count"])


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
                project=project,
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
                project=deficit.get("project") or project,
                reason=f"Missing metadata fields: {missing}",
                priority=3,
            )
        )

    for repeated in metrics.get("repeated_questions", []):
        hashed = hashlib.sha1(repeated["question"].encode("utf-8")).hexdigest()[:10]
        repeated_project = repeated.get("project") or project
        tasks.append(
            FixQueueTask(
                id=f"repeat-{hashed}",
                action="run_routine",
                target=repeated["question"],
                project=repeated_project,
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
            reason = f"Routine '{action_name}' tried to write outside allowed paths: {target_path}"
            priority = 3
        else:
            action = "review_permissions"
            target = target_path
            reason = f"Permission denial for '{action_name}' writing to {target_path}"
            priority = 3

        task_id = hashlib.sha1(f"{reason_code}:{action_name}:{target_path}".encode()).hexdigest()[
            :10
        ]
        tasks.append(
            FixQueueTask(
                id=f"permission-{task_id}",
                action=action,
                target=target,
                project=denial.get("project") or project,
                reason=reason,
                priority=priority,
            )
        )

    return tasks


def _build_lint_tasks(lint_issues: list[LintIssue]) -> list[FixQueueTask]:
    """Create Fix Queue tasks from capture lint issues."""
    tasks: list[FixQueueTask] = []
    for issue in lint_issues:
        task_hash = hashlib.sha1(f"{issue.code}:{issue.file_path}".encode()).hexdigest()[:10]
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


def _build_staleness_task(
    stale_notes: list[dict[str, Any]],
    stale_decisions: list[dict[str, Any]],
    project: str | None,
) -> FixQueueTask | None:
    """Create a Fix Queue task that prompts a weekly review for stale content."""
    notes_count = _staleness_value(stale_notes)
    decisions_count = _staleness_value(stale_decisions)
    if notes_count == 0 and decisions_count == 0:
        return None

    reasons: list[str] = []
    if notes_count:
        reasons.append(_format_staleness_details(stale_notes, "Notes"))
    if decisions_count:
        reasons.append(_format_staleness_details(stale_decisions, "Decisions"))
    reason = " | ".join(reasons) if reasons else "Stale notes or decisions detected."

    task_id = f"stale-review-{(project or 'global').replace(' ', '-')}"
    return FixQueueTask(
        id=task_id,
        action="run_routine",
        target="routines/weekly-review",
        project=project,
        reason=reason,
        priority=_priority_from_count(max(notes_count, decisions_count)),
    )


def _build_indexing_tasks(
    low_volume_projects: list[dict[str, Any]],
    low_hit_rate_projects: list[dict[str, Any]],
    *,
    low_volume_threshold: int,
    low_hit_rate_threshold: float,
) -> list[FixQueueTask]:
    """Create Fix Queue tasks that prompt indexing for low-coverage projects."""
    tasks: list[FixQueueTask] = []

    for item in low_volume_projects:
        project = item.get("project") or "unknown"
        doc_count = int(item.get("document_count", 0))
        gap = max(0, low_volume_threshold - doc_count)
        priority = _priority_from_count(gap) if gap else 5
        task_id = f"index-volume-{project.replace(' ', '-')}"
        tasks.append(
            FixQueueTask(
                id=task_id,
                action="open_indexing",
                target=project,
                project=project,
                reason=(
                    f"Project '{project}' has only {doc_count} documents "
                    f"(threshold {low_volume_threshold})."
                ),
                priority=priority,
            )
        )

    for item in low_hit_rate_projects:
        project = item.get("project") or "unknown"
        hit_rate = float(item.get("hit_rate", 0.0))
        severity = (
            max(0.0, (low_hit_rate_threshold - hit_rate) / low_hit_rate_threshold)
            if low_hit_rate_threshold > 0
            else 0.0
        )
        priority = _priority_from_ratio(severity)
        task_id = f"index-hit-rate-{project.replace(' ', '-')}"
        tasks.append(
            FixQueueTask(
                id=task_id,
                action="open_indexing",
                target=project,
                project=project,
                reason=(
                    f"Project '{project}' has {hit_rate * 100:.0f}% retrieval hit rate "
                    f"(threshold {low_hit_rate_threshold * 100:.0f}%)."
                ),
                priority=priority,
            )
        )

    return tasks


def _build_ingestion_tasks(errors: list[dict[str, Any]]) -> list[FixQueueTask]:
    """Create Fix Queue tasks from recent ingestion errors."""
    tasks: list[FixQueueTask] = []
    seen: set[tuple[str, str]] = set()
    for error in errors:
        path = error.get("source_path")
        error_type = error.get("error_type") or "ingestion_error"
        if not path:
            continue
        key = (path, error_type)
        if key in seen:
            continue
        seen.add(key)
        reason = _format_ingestion_task_reason(error_type, error.get("error_message"))
        task_hash = hashlib.sha1(f"{path}:{error_type}".encode()).hexdigest()[:10]
        tasks.append(
            FixQueueTask(
                id=f"ingest-{task_hash}",
                action="open_file",
                target=path,
                project=error.get("project"),
                reason=reason,
                priority=_priority_for_ingestion_error(error_type),
            )
        )
    return tasks


@router.get("/health/fix-queue", response_model=FixQueueResponse)
def health_fix_queue(project: str | None = None) -> FixQueueResponse:
    """Return Fix Queue signals and tasks derived from failure metrics."""
    db = get_database()
    config = get_config()
    metrics = db.get_feedback_metrics(project=project)
    metadata_deficits = db.get_documents_missing_metadata(project=project)
    metadata_total = db.get_missing_metadata_total(project=project)
    metadata_counts = db.get_missing_metadata_counts(project=project)
    permission_metrics = db.get_permission_denial_metrics(project=project)
    lint_issues = collect_capture_lint_issues(config, project=project)
    project_counts = db.get_project_document_counts(project=project)
    low_volume_threshold = config.health.low_volume_document_threshold
    low_volume_projects = [
        item for item in project_counts if item["document_count"] < low_volume_threshold
    ]
    search_stats = db.get_search_history_stats(
        window_hours=config.health.search_window_hours,
        min_count=config.health.min_searches_for_rate,
        project=project,
    )
    low_hit_rate_threshold = config.health.low_hit_rate_threshold
    low_hit_rate_projects = [
        item for item in search_stats if item["hit_rate"] < low_hit_rate_threshold
    ]
    staleness_buckets = config.health.staleness_buckets_days
    stale_notes = db.get_stale_document_buckets(
        buckets_days=staleness_buckets, source_type="markdown", project=project
    )
    stale_decisions = db.get_stale_decision_buckets(
        buckets_days=staleness_buckets, project=project
    )
    ingestion_metrics = db.get_ingestion_error_metrics(
        project=project,
        window_hours=config.health.ingestion_error_window_hours,
        limit=config.health.ingestion_error_task_limit,
    )

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
            value=metadata_total,
            details="Documents missing source_date/project/language metadata",
        ),
        FailureSignal(
            name="metadata_top_offenders",
            value=len(metadata_counts),
            details=_format_metadata_offenders_details(metadata_counts),
        ),
        FailureSignal(
            name="stale_notes",
            value=_staleness_value(stale_notes),
            details=_format_staleness_details(stale_notes, "Notes"),
        ),
        FailureSignal(
            name="stale_decisions",
            value=_staleness_value(stale_decisions),
            details=_format_staleness_details(stale_decisions, "Decisions"),
        ),
        FailureSignal(
            name="ingestion_errors",
            value=ingestion_metrics.get("total", 0),
            details=_format_ingestion_error_details(ingestion_metrics),
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
        FailureSignal(
            name="low_indexed_volume",
            value=len(low_volume_projects),
            details=_format_low_volume_details(low_volume_projects, low_volume_threshold),
        ),
        FailureSignal(
            name="low_retrieval_hit_rate",
            value=len(low_hit_rate_projects),
            details=_format_low_hit_rate_details(low_hit_rate_projects, low_hit_rate_threshold),
        ),
    ]

    tasks = _build_fix_queue_tasks(
        metrics, metadata_deficits, project, permission_metrics.get("recent", [])
    )
    tasks.extend(_build_lint_tasks(lint_issues))
    tasks.extend(_build_ingestion_tasks(ingestion_metrics.get("recent", [])))
    tasks.extend(
        _build_indexing_tasks(
            low_volume_projects,
            low_hit_rate_projects,
            low_volume_threshold=low_volume_threshold,
            low_hit_rate_threshold=low_hit_rate_threshold,
        )
    )
    staleness_task = _build_staleness_task(stale_notes, stale_decisions, project)
    if staleness_task:
        tasks.append(staleness_task)
    return FixQueueResponse(failure_signals=failure_signals, tasks=tasks)
