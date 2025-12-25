"""Routine action endpoints that write template-driven notes."""

from __future__ import annotations

import re
from datetime import date
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
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([\w-]+)\s*}}")
SOURCE_PATTERN = re.compile(r'(source:\s*")[^"]+(")')


def _render_template(template_path: Path, values: dict[str, str], source_tag: str) -> str:
    """Render the template with the provided values and rewrite the source tag."""
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Daily template not found")

    raw = template_path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, "")

    rendered = PLACEHOLDER_PATTERN.sub(replace, raw)
    rendered = SOURCE_PATTERN.sub(rf'\1{source_tag}\2', rendered, count=1)
    return rendered


def _collect_retrieval(name: str, query: str, project: str | None, top_k: int) -> RoutineRetrieval:
    """Perform a search query and convert the results to sources."""
    try:
        results = search(query=query, project=project, top_k=top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed for {name}: {exc}") from exc

    sources = [
        convert_result_to_source(result, idx + 1)
        for idx, result in enumerate(results)
    ]

    return RoutineRetrieval(name=name, query=query, sources=sources)


def _point_to_daily_note(target_date: date, vault_root: Path) -> Path:
    """Build the vault path for the daily check-in note."""
    return vault_root / "routines" / "daily" / f"{target_date.isoformat()}.md"


@router.post("/routines/daily-checkin", response_model=RoutineResponse)
def daily_checkin(request: RoutineRequest) -> RoutineResponse:
    """Generate the daily check-in note with citations."""
    config = get_config()
    project = request.project or config.defaults.project
    language = request.language or config.defaults.language
    target_date = request.date or date.today()
    top_k = request.top_k

    retrievals: list[RoutineRetrieval] = []
    warnings: list[str] = []

    for name, query in (("open_loops", "open loop"), ("recent_context", "recent context")):
        retrieval = _collect_retrieval(name, query, project, top_k)
        if not retrieval.sources:
            warnings.append(f"No citations found for {name}; manual entry recommended.")
        retrievals.append(retrieval)

    values = {
        "project": project,
        "date": target_date.isoformat(),
        "language": language,
    }
    content = _render_template(
        template_path=DAILY_TEMPLATE,
        values=values,
        source_tag="routine/daily-checkin",
    )

    vault_root = config.paths.vault
    target_path = _point_to_daily_note(target_date, vault_root)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        warnings.append("Existing daily check-in note was overwritten.")

    try:
        target_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write daily note: {exc}") from exc

    return RoutineResponse(
        routine="daily-checkin",
        file_path=str(target_path),
        template=str(DAILY_TEMPLATE),
        content=content,
        retrievals=retrievals,
        warnings=warnings,
    )
