"""Routine action endpoints that write template-driven notes."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException

from bob.api.schemas import RoutineRequest, RoutineResponse, RoutineRetrieval
from bob.api.utils import convert_result_to_source
from bob.config import get_config
from bob.retrieval.search import search

router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = ROOT_DIR / "docs" / "templates"
DAILY_TEMPLATE = TEMPLATES_DIR / "daily.md"
DAILY_DEBRIEF_TEMPLATE = TEMPLATES_DIR / "daily-debrief.md"
WEEKLY_TEMPLATE = TEMPLATES_DIR / "weekly.md"
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([\w-]+)\s*}}")
SOURCE_PATTERN = re.compile(r'(source:\s*")[^"]+(")')

TargetPathFn = Callable[[date, Path, RoutineRequest], Path]
PlaceholderFn = Callable[[date, RoutineRequest], dict[str, str]]


@dataclass(frozen=True)
class RoutineQuery:
    """Query configuration for a routine retrieval bucket."""

    name: str
    query: str
    date_after_offset: timedelta | None = None
    date_before_offset: timedelta | None = None


@dataclass(frozen=True)
class RoutineAction:
    """Configuration describing how a routine renders and writes notes."""

    name: str
    template: Path
    source_tag: str
    queries: tuple[RoutineQuery, ...]
    target_path_fn: TargetPathFn
    overwrite_warning: str
    placeholder_fn: PlaceholderFn | None = None


def _render_template(template_path: Path, values: dict[str, str], source_tag: str) -> str:
    """Render the template with the provided values and rewrite the source tag."""
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Template not found")

    raw = template_path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, "")

    rendered = PLACEHOLDER_PATTERN.sub(replace, raw)
    rendered = SOURCE_PATTERN.sub(rf"\1{source_tag}\2", rendered, count=1)
    return rendered


def _resolve_date_after(target_date: date, offset: timedelta | None) -> datetime | None:
    """Return the lower datetime bound relative to the target date."""
    if offset is None:
        return None
    bound_date = target_date - offset
    return datetime.combine(bound_date, time.min)


def _resolve_date_before(target_date: date, offset: timedelta | None) -> datetime | None:
    """Return the upper datetime bound relative to the target date."""
    if offset is None:
        return None
    bound_date = target_date + offset
    return datetime.combine(bound_date, time.max)


def _collect_retrieval(
    name: str,
    query: str,
    project: str | None,
    top_k: int,
    *,
    date_after: datetime | None = None,
    date_before: datetime | None = None,
) -> RoutineRetrieval:
    """Perform a search query and convert the results to sources."""
    try:
        results = search(
            query=query,
            project=project,
            top_k=top_k,
            date_after=date_after,
            date_before=date_before,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed for {name}: {exc}") from exc

    sources = [convert_result_to_source(result, idx + 1) for idx, result in enumerate(results)]

    return RoutineRetrieval(name=name, query=query, sources=sources)


def _daily_target_path(target_date: date, vault_root: Path, _request: RoutineRequest) -> Path:
    """Build the vault path for the daily check-in note."""
    return vault_root / "routines" / "daily" / f"{target_date.isoformat()}.md"


def _weekly_target_path(target_date: date, vault_root: Path, _request: RoutineRequest) -> Path:
    """Build the vault path for the weekly review note."""
    iso_year, iso_week, _ = target_date.isocalendar()
    filename = f"{iso_year}-W{iso_week:02d}.md"
    return vault_root / "routines" / "weekly" / filename


def _daily_debrief_target_path(
    target_date: date, vault_root: Path, _request: RoutineRequest
) -> Path:
    """Build the vault path for the end-of-day debrief note."""
    filename = f"{target_date.isoformat()}-debrief.md"
    return vault_root / "routines" / "daily" / filename


def _weekly_placeholders(target_date: date, _request: RoutineRequest) -> dict[str, str]:
    """Provide week-specific placeholders for the weekly template."""
    week_start = target_date - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=6)
    return {
        "week_range": f"{week_start.isoformat()} - {week_end.isoformat()}",
    }


ROUTINE_ACTIONS: dict[str, RoutineAction] = {
    "daily-checkin": RoutineAction(
        name="daily-checkin",
        template=DAILY_TEMPLATE,
        source_tag="routine/daily-checkin",
        queries=(
            RoutineQuery(name="open_loops", query="open loop"),
            RoutineQuery(
                name="recent_context",
                query="recent context",
                date_after_offset=timedelta(days=3),
                date_before_offset=timedelta(days=0),
            ),
        ),
        target_path_fn=_daily_target_path,
        overwrite_warning="Existing daily check-in note was overwritten.",
    ),
    "daily-debrief": RoutineAction(
        name="daily-debrief",
        template=DAILY_DEBRIEF_TEMPLATE,
        source_tag="routine/daily-debrief",
        queries=(
            RoutineQuery(
                name="recent_context",
                query="recent context",
                date_after_offset=timedelta(days=1),
                date_before_offset=timedelta(days=0),
            ),
            RoutineQuery(
                name="decisions_today",
                query="decisions decided today",
                date_after_offset=timedelta(days=1),
                date_before_offset=timedelta(days=0),
            ),
        ),
        target_path_fn=_daily_debrief_target_path,
        overwrite_warning="Existing end-of-day debrief note was overwritten.",
    ),
    "weekly-review": RoutineAction(
        name="weekly-review",
        template=WEEKLY_TEMPLATE,
        source_tag="routine/weekly-review",
        queries=(
            RoutineQuery(name="weekly_highlights", query="weekly highlights"),
            RoutineQuery(name="stale_decisions", query="stale decisions"),
            RoutineQuery(name="metadata_gaps", query="missing metadata"),
        ),
        target_path_fn=_weekly_target_path,
        overwrite_warning="Existing weekly review note was overwritten.",
        placeholder_fn=_weekly_placeholders,
    ),
}


TEMPLATE_WRITE_SCOPE = 3


def _resolve_allowed_directories(config) -> list[Path]:
    """Resolve configured allowed vault paths into absolute directories."""
    cwd = Path.cwd()
    vault_root = config.paths.vault.resolve()
    allowed_dirs: set[Path] = set()

    for entry in config.permissions.allowed_vault_paths:
        candidate = Path(entry)
        if candidate.is_absolute():
            allowed_dirs.add(candidate.resolve())
            continue

        parts = list(candidate.parts)
        if parts and parts[0] in {vault_root.name, "vault"}:
            parts = parts[1:]

        relative = Path(*parts) if parts else Path(".")
        allowed_dirs.add((vault_root / relative).resolve())
        allowed_dirs.add((cwd / candidate).resolve())

    return list(allowed_dirs)


def _ensure_allowed_write_path(target_path: Path, config) -> None:
    """Validate that the routine is writing into an allowed vault directory."""
    resolved_target = target_path.resolve()
    allowed_dirs = _resolve_allowed_directories(config)
    if any(resolved_target.is_relative_to(dir_path) for dir_path in allowed_dirs):
        return

    raise HTTPException(
        status_code=403,
        detail={
            "code": "PERMISSION_DENIED",
            "message": "Target path is outside allowed vault directories.",
            "target_path": str(target_path),
            "allowed_paths": [str(dir_path) for dir_path in allowed_dirs],
        },
    )


def _ensure_scope_level(action_name: str, target_path: Path, config) -> None:
    """Ensure the configured scope level permits template writes."""
    current = config.permissions.default_scope
    if current >= TEMPLATE_WRITE_SCOPE:
        return

    raise HTTPException(
        status_code=403,
        detail={
            "code": "PERMISSION_DENIED",
            "message": f"Permission level {TEMPLATE_WRITE_SCOPE} required for {action_name}.",
            "scope_level": current,
            "required_scope_level": TEMPLATE_WRITE_SCOPE,
            "target_path": str(target_path),
        },
    )


def _run_routine(action: RoutineAction, request: RoutineRequest) -> RoutineResponse:
    """Execute the retrieval + templating + write cycle for a routine."""
    config = get_config()
    project = request.project or config.defaults.project
    language = request.language or config.defaults.language
    target_date = request.date or date.today()
    top_k = request.top_k

    warnings: list[str] = []

    values = {
        "project": project,
        "date": target_date.isoformat(),
        "language": language,
    }
    if action.placeholder_fn:
        values.update(action.placeholder_fn(target_date, request))

    vault_root = config.paths.vault
    target_path = action.target_path_fn(target_date, vault_root, request)

    _ensure_allowed_write_path(target_path, config)
    _ensure_scope_level(action.name, target_path, config)

    retrievals: list[RoutineRetrieval] = []
    for query in action.queries:
        date_after = _resolve_date_after(target_date, query.date_after_offset)
        date_before = _resolve_date_before(target_date, query.date_before_offset)

        retrieval = _collect_retrieval(
            name=query.name,
            query=query.query,
            project=project,
            top_k=top_k,
            date_after=date_after,
            date_before=date_before,
        )
        if not retrieval.sources:
            warnings.append(f"No citations found for {query.name}; manual entry recommended.")
        retrievals.append(retrieval)

    content = _render_template(
        template_path=action.template,
        values=values,
        source_tag=action.source_tag,
    )

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        warnings.append(action.overwrite_warning)

    try:
        target_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write {action.name} note: {exc}",
        ) from exc

    return RoutineResponse(
        routine=action.name,
        file_path=str(target_path),
        template=str(action.template),
        content=content,
        retrievals=retrievals,
        warnings=warnings,
    )


@router.post("/routines/daily-checkin", response_model=RoutineResponse)
def daily_checkin(request: RoutineRequest) -> RoutineResponse:
    """Generate the daily check-in note with citations."""
    return _run_routine(ROUTINE_ACTIONS["daily-checkin"], request)


@router.post("/routines/weekly-review", response_model=RoutineResponse)
def weekly_review(request: RoutineRequest) -> RoutineResponse:
    """Generate the weekly review note with citations."""
    return _run_routine(ROUTINE_ACTIONS["weekly-review"], request)


@router.post("/routines/daily-debrief", response_model=RoutineResponse)
def daily_debrief(request: RoutineRequest) -> RoutineResponse:
    """Generate the end-of-day debrief note with citations."""
    return _run_routine(ROUTINE_ACTIONS["daily-debrief"], request)
