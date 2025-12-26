"""Template-driven note creation endpoint."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException

from bob.api.schemas import NoteCreateRequest, NoteCreateResponse
from bob.api.templates import render_template, resolve_template_path
from bob.api.write_permissions import ensure_allowed_write_path, ensure_scope_level
from bob.config import get_config

router = APIRouter()


def _resolve_target_path(target_path: str, vault_root: Path) -> Path:
    """Resolve the target path relative to the vault when needed."""
    raw = target_path.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="target_path is required")
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    return vault_root / candidate


@router.post("/notes/create", response_model=NoteCreateResponse)
def create_note(request: NoteCreateRequest) -> NoteCreateResponse:
    """Create a note from a canonical template."""
    config = get_config()
    project = request.project or config.defaults.project
    language = request.language or config.defaults.language
    note_date = request.date or date.today()

    template_path = resolve_template_path(request.template)
    target_path = _resolve_target_path(request.target_path, config.paths.vault)

    ensure_allowed_write_path("notes-create", project, target_path, config)
    ensure_scope_level("notes-create", project, target_path, config)

    values = {
        "project": project,
        "date": note_date.isoformat(),
        "language": language,
    }
    for key, value in request.values.items():
        if value is None:
            continue
        values[str(key)] = str(value)

    content = render_template(template_path, values, source_tag=None)

    warnings: list[str] = []
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        warnings.append("Existing note was overwritten.")

    try:
        target_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write note: {exc}") from exc

    return NoteCreateResponse(
        file_path=str(target_path),
        template=str(template_path),
        content=content,
        warnings=warnings,
    )
