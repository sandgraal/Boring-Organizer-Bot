"""Template utilities for note and routine writes."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException

ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT_DIR / "docs" / "templates"
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([\w-]+)\s*}}")
SOURCE_PATTERN = re.compile(r'(source:\s*")[^"]+(")')


def resolve_template_path(template: str) -> Path:
    """Resolve a template identifier to a file path."""
    name = template.strip()
    if not name:
        raise HTTPException(status_code=400, detail="template is required")
    if name in {".", ".."} or Path(name).name != name:
        raise HTTPException(status_code=400, detail="template must be a filename")

    if name.endswith(".md"):
        name = name[: -len(".md")]

    path = TEMPLATES_DIR / f"{name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return path


def render_template(template_path: Path, values: dict[str, str], source_tag: str | None) -> str:
    """Render a template with placeholder values and optional source override."""
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Template not found")

    raw = template_path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, "")

    rendered = PLACEHOLDER_PATTERN.sub(replace, raw)
    if source_tag is not None:
        rendered = SOURCE_PATTERN.sub(rf"\1{source_tag}\2", rendered, count=1)
    return rendered
