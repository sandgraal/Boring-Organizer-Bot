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
from bob.config import Config, get_config
from bob.retrieval.search import search

router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = ROOT_DIR / "docs" / "templates"
DAILY_TEMPLATE = TEMPLATES_DIR / "daily.md"
DAILY_DEBRIEF_TEMPLATE = TEMPLATES_DIR / "daily-debrief.md"
WEEKLY_TEMPLATE = TEMPLATES_DIR / "weekly.md"
MEETING_TEMPLATE = TEMPLATES_DIR / "meeting.md"
DECISION_TEMPLATE = TEMPLATES_DIR / "decision.md"
TRIP_TEMPLATE = TEMPLATES_DIR / "trip.md"
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([\w-]+)\s*}}")
SOURCE_PATTERN = re.compile(r'(source:\s*")[^"]+(")')

TargetPathFn = Callable[[date, Path, RoutineRequest, str], Path]
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


def _slugify_component(value: str) -> str:
    """Normalize a string into a filesystem-safe slug."""
    normalized = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")


def _derive_slug(candidate: str | None, fallback: str) -> str:
    """Choose the sanitized slug candidate or fallback when empty."""
    base = (candidate or fallback or "").strip()
    slug = _slugify_component(base)
    if slug:
        return slug
    return _slugify_component(fallback)


def _normalize_project_segment(project: str) -> str:
    """Generate a filesystem-safe directory name for a project."""
    segment = _slugify_component(project)
    return segment or "project"


def _meeting_placeholders(target_date: date, request: RoutineRequest) -> dict[str, str]:
    """Provide meeting-specific placeholder values for the template."""
    meeting_date = request.meeting_date or target_date
    formatted_date = meeting_date.isoformat()
    participants = request.participants or []

    values = {"meeting_date": formatted_date}
    if participants:
        for index, participant in enumerate(participants, start=1):
            values[f"participant_{index}"] = participant
    else:
        values["participant_1"] = ""

    return values


def _trip_placeholders(_target_date: date, request: RoutineRequest) -> dict[str, str]:
    """Provide trip name placeholder for the trip template."""
    trip_name = request.trip_name or request.slug or request.trip_slug or ""
    return {"trip_name": trip_name}


def _meeting_target_factory(suffix: str) -> TargetPathFn:
    """Build a target path function for meeting prep/debrief notes."""

    def _target_path(
        target_date: date, vault_root: Path, request: RoutineRequest, project: str
    ) -> Path:
        base_slug = request.meeting_slug or request.slug
        fallback = f"meeting-{target_date.isoformat()}"
        slug = _derive_slug(base_slug, fallback)
        project_segment = _normalize_project_segment(project)
        return vault_root / "meetings" / project_segment / f"{slug}-{suffix}.md"

    return _target_path


def _decision_target_path(
    target_date: date, vault_root: Path, request: RoutineRequest, _project: str
) -> Path:
    """Build the vault path for a decision note."""
    base_slug = request.decision_slug or request.slug
    fallback = request.title or f"decision-{target_date.isoformat()}"
    slug = _derive_slug(base_slug, fallback)
    filename = slug if slug.startswith("decision-") else f"decision-{slug}"
    return vault_root / "decisions" / f"{filename}.md"


def _trip_target_path(
    target_date: date, vault_root: Path, request: RoutineRequest, _project: str
) -> Path:
    """Build the vault path for a trip debrief note."""
    base_slug = request.trip_slug or request.slug
    fallback = request.trip_name or f"trip-{target_date.isoformat()}"
    slug = _derive_slug(base_slug, fallback)
    return vault_root / "trips" / slug / "debrief.md"


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


def _daily_target_path(
    target_date: date, vault_root: Path, _request: RoutineRequest, _project: str
) -> Path:
    """Build the vault path for the daily check-in note."""
    return vault_root / "routines" / "daily" / f"{target_date.isoformat()}.md"


def _weekly_target_path(
    target_date: date, vault_root: Path, _request: RoutineRequest, _project: str
) -> Path:
    """Build the vault path for the weekly review note."""
    iso_year, iso_week, _ = target_date.isocalendar()
    filename = f"{iso_year}-W{iso_week:02d}.md"
    return vault_root / "routines" / "weekly" / filename


def _daily_debrief_target_path(
    target_date: date,
    vault_root: Path,
    _request: RoutineRequest,
    _project: str,
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
    "meeting-prep": RoutineAction(
        name="meeting-prep",
        template=MEETING_TEMPLATE,
        source_tag="routine/meeting-prep",
        queries=(
            RoutineQuery(name="recent_decisions", query="recent decisions"),
            RoutineQuery(name="unresolved_questions", query="unresolved questions"),
            RoutineQuery(
                name="recent_notes",
                query="recent notes",
                date_after_offset=timedelta(days=7),
                date_before_offset=timedelta(days=0),
            ),
        ),
        target_path_fn=_meeting_target_factory("prep"),
        overwrite_warning="Existing meeting prep note was overwritten.",
        placeholder_fn=_meeting_placeholders,
    ),
    "meeting-debrief": RoutineAction(
        name="meeting-debrief",
        template=MEETING_TEMPLATE,
        source_tag="routine/meeting-debrief",
        queries=(
            RoutineQuery(
                name="meeting_notes",
                query="meeting notes",
                date_after_offset=timedelta(days=1),
                date_before_offset=timedelta(days=0),
            ),
            RoutineQuery(name="open_decisions", query="open decisions"),
        ),
        target_path_fn=_meeting_target_factory("debrief"),
        overwrite_warning="Existing meeting debrief note was overwritten.",
        placeholder_fn=_meeting_placeholders,
    ),
    "new-decision": RoutineAction(
        name="new-decision",
        template=DECISION_TEMPLATE,
        source_tag="routine/new-decision",
        queries=(
            RoutineQuery(name="related_sources", query="related decision sources"),
            RoutineQuery(name="conflicting_decisions", query="conflicting decisions"),
        ),
        target_path_fn=_decision_target_path,
        overwrite_warning="Existing decision note was overwritten.",
    ),
    "trip-debrief": RoutineAction(
        name="trip-debrief",
        template=TRIP_TEMPLATE,
        source_tag="routine/trip-debrief",
        queries=(
            RoutineQuery(
                name="trip_notes",
                query="trip notes",
                date_after_offset=timedelta(days=30),
                date_before_offset=timedelta(days=0),
            ),
            RoutineQuery(name="trip_recipes", query="trip recipes"),
            RoutineQuery(name="trip_open_loops", query="trip open loops"),
        ),
        target_path_fn=_trip_target_path,
        overwrite_warning="Existing trip debrief note was overwritten.",
        placeholder_fn=_trip_placeholders,
    ),
}


TEMPLATE_WRITE_SCOPE = 3


def _resolve_allowed_directories(config: Config) -> list[Path]:
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


def _ensure_allowed_write_path(target_path: Path, config: Config) -> None:
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


def _ensure_scope_level(action_name: str, target_path: Path, config: Config) -> None:
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
    target_path = action.target_path_fn(target_date, vault_root, request, project)

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


@router.post("/routines/meeting-prep", response_model=RoutineResponse)
def meeting_prep(request: RoutineRequest) -> RoutineResponse:
    """Generate a meeting prep note with retrieval-backed context."""
    return _run_routine(ROUTINE_ACTIONS["meeting-prep"], request)


@router.post("/routines/meeting-debrief", response_model=RoutineResponse)
def meeting_debrief(request: RoutineRequest) -> RoutineResponse:
    """Generate a meeting debrief note with open decisions highlighted."""
    return _run_routine(ROUTINE_ACTIONS["meeting-debrief"], request)


@router.post("/routines/new-decision", response_model=RoutineResponse)
def new_decision(request: RoutineRequest) -> RoutineResponse:
    """Capture a new decision note with evidence and conflicting decisions."""
    return _run_routine(ROUTINE_ACTIONS["new-decision"], request)


@router.post("/routines/trip-debrief", response_model=RoutineResponse)
def trip_debrief(request: RoutineRequest) -> RoutineResponse:
    """Write a trip debrief note seeded from trip-related context."""
    return _run_routine(ROUTINE_ACTIONS["trip-debrief"], request)
