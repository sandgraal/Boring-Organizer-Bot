"""Connector endpoints for local capture imports."""

from __future__ import annotations

import re
from datetime import date as DateType
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from bob.api.schemas import (
    BookmarksImportRequest,
    BookmarksImportResponse,
    HighlightCreateRequest,
    HighlightCreateResponse,
)
from bob.api.write_permissions import (
    CONNECTOR_WRITE_SCOPE,
    ensure_allowed_write_path,
    ensure_connector_enabled,
    ensure_scope_level,
)
from bob.config import get_config
from bob.ingest.bookmarks import parse_bookmarks_file

router = APIRouter()


def _slugify(value: str) -> str:
    normalized = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-") or "untitled"


def _format_date(value: DateType | datetime | None) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, DateType):
        return value.isoformat()
    return datetime.utcnow().date().isoformat()


def _frontmatter(metadata: dict[str, Any]) -> str:
    lines = ["---"]
    for key, raw_value in metadata.items():
        if raw_value is None:
            continue
        value = str(raw_value).replace('"', '\\"')
        lines.append(f'{key}: "{value}"')
    lines.append("---")
    return "\n".join(lines)


def _ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise HTTPException(status_code=500, detail="Unable to create a unique file name.")


def _render_bookmark_note(
    *,
    title: str,
    url: str,
    folder: str | None,
    project: str,
    language: str,
    entry_date: DateType | datetime | None,
) -> str:
    frontmatter = _frontmatter(
        {
            "project": project,
            "date": _format_date(entry_date),
            "language": language,
            "source": "connector/bookmarks",
            "source_url": url,
            "folder": folder,
        }
    )
    lines = [
        frontmatter,
        "",
        "# Bookmark",
        "",
        "## Title",
        title,
        "",
        "## URL",
        url,
    ]
    if folder:
        lines.extend(["", "## Folder", folder])
    lines.extend(["", "## Notes", "- "])
    return "\n".join(lines).strip() + "\n"


def _render_highlight_note(
    *,
    title: str,
    text: str,
    source_url: str | None,
    project: str,
    language: str,
    entry_date: DateType | datetime | None,
) -> str:
    frontmatter = _frontmatter(
        {
            "project": project,
            "date": _format_date(entry_date),
            "language": language,
            "source": "connector/highlight",
            "source_url": source_url,
        }
    )
    lines = [
        frontmatter,
        "",
        "# Highlight",
        "",
        "## Title",
        title,
        "",
        "## Source",
        source_url or "Unknown",
        "",
        "## Excerpt",
        text,
        "",
        "## Notes",
        "- ",
    ]
    return "\n".join(lines).strip() + "\n"


def _write_connector_note(
    *,
    action_name: str,
    project: str,
    target_path: Path,
    content: str,
) -> None:
    config = get_config()
    ensure_connector_enabled("browser_saves", action_name, project, target_path, config)
    ensure_scope_level(
        action_name,
        project,
        target_path,
        config,
        required_scope_level=CONNECTOR_WRITE_SCOPE,
    )
    ensure_allowed_write_path(
        action_name,
        project,
        target_path,
        config,
        required_scope_level=CONNECTOR_WRITE_SCOPE,
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")


@router.post("/connectors/bookmarks/import", response_model=BookmarksImportResponse)
def import_bookmarks(request: BookmarksImportRequest) -> BookmarksImportResponse:
    """Import browser bookmarks HTML export into vault notes."""
    source_path = Path(request.source_path).expanduser()
    if not source_path.exists() or not source_path.is_file():
        raise HTTPException(status_code=400, detail="Bookmarks file not found.")

    config = get_config()
    project = request.project or config.defaults.project
    language = request.language or config.defaults.language

    try:
        entries = parse_bookmarks_file(source_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    vault_root = config.paths.vault
    base_dir = vault_root / "manual-saves" / "bookmarks" / _slugify(project)

    created: list[str] = []
    warnings: list[str] = []

    for entry in entries:
        slug = _slugify(entry.title or entry.url)
        filename = f"bookmark-{slug}.md"
        target_path = _ensure_unique_path(base_dir / filename)
        if target_path.name != filename:
            warnings.append(f"Duplicate bookmark name; wrote {target_path.name}.")

        folder_label = " / ".join(entry.folder) if entry.folder else None
        content = _render_bookmark_note(
            title=entry.title or entry.url,
            url=entry.url,
            folder=folder_label,
            project=project,
            language=language,
            entry_date=entry.added_at,
        )
        _write_connector_note(
            action_name="connector/bookmarks",
            project=project,
            target_path=target_path,
            content=content,
        )
        created.append(str(target_path))

    return BookmarksImportResponse(
        success=True, imported=len(created), created_paths=created, warnings=warnings
    )


@router.post("/connectors/highlights", response_model=HighlightCreateResponse)
def create_highlight(request: HighlightCreateRequest) -> HighlightCreateResponse:
    """Create a manual highlight note in the vault."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Highlight text is required.")

    config = get_config()
    project = request.project or config.defaults.project
    language = request.language or config.defaults.language
    title = request.title or request.text.strip().splitlines()[0][:60] or "Highlight"

    vault_root = config.paths.vault
    base_dir = vault_root / "manual-saves" / "highlights" / _slugify(project)
    slug = _slugify(title)
    filename = f"highlight-{slug}.md"
    target_path = _ensure_unique_path(base_dir / filename)

    content = _render_highlight_note(
        title=title,
        text=request.text.strip(),
        source_url=request.source_url,
        project=project,
        language=language,
        entry_date=request.date,
    )

    _write_connector_note(
        action_name="connector/highlights",
        project=project,
        target_path=target_path,
        content=content,
    )

    return HighlightCreateResponse(success=True, file_path=str(target_path), warnings=[])
