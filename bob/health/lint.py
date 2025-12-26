"""Capture hygiene linting for vault notes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from bob.config import Config


REQUIRED_METADATA_FIELDS = ("project", "date", "language", "source")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class LintIssue:
    """Represents a capture hygiene issue in a vault note."""

    code: str
    file_path: Path
    message: str
    priority: int


def collect_capture_lint_issues(config: Config, *, limit: int = 10) -> list[LintIssue]:
    """Scan allowed vault paths for capture hygiene issues."""
    vault_root = config.paths.vault.resolve()
    allowed_dirs = _resolve_allowed_directories(
        vault_root, config.permissions.allowed_vault_paths
    )

    issues: list[LintIssue] = []
    for path in _collect_markdown_files(allowed_dirs):
        issues.extend(_lint_file(path))
        if len(issues) >= limit:
            return issues[:limit]
    return issues


def _resolve_allowed_directories(vault_root: Path, entries: list[str]) -> list[Path]:
    """Resolve allowed vault paths into absolute directories.

    Mirrors the routine write-path resolution so lint only scans expected vault roots.
    """
    cwd = Path.cwd()
    allowed_dirs: set[Path] = set()

    for entry in entries:
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


def _collect_markdown_files(allowed_dirs: list[Path]) -> list[Path]:
    """Return a deterministic list of markdown files under allowed directories."""
    files: set[Path] = set()
    for directory in allowed_dirs:
        if not directory.exists():
            continue
        for path in directory.rglob("*.md"):
            if path.is_file():
                files.add(path.resolve())
    return sorted(files)


def _lint_file(path: Path) -> list[LintIssue]:
    """Lint a single markdown file for missing metadata and sections."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []

    lines = content.splitlines()
    frontmatter = _parse_frontmatter(lines)
    headings = _collect_headings(lines)
    issues: list[LintIssue] = []

    missing_fields = _missing_metadata_fields(frontmatter)
    if missing_fields:
        issues.append(
            LintIssue(
                code="missing_metadata",
                file_path=path,
                message=f"Missing metadata fields: {', '.join(missing_fields)}",
                priority=3,
            )
        )

    if _is_path_segment(path, "decisions"):
        missing_rationale = []
        if "context" not in headings:
            missing_rationale.append("Context")
        if "evidence" not in headings:
            missing_rationale.append("Evidence")
        if missing_rationale:
            issues.append(
                LintIssue(
                    code="missing_rationale",
                    file_path=path,
                    message=(
                        "Decision capture missing "
                        + " / ".join(missing_rationale)
                        + " section(s)."
                    ),
                    priority=2,
                )
            )
        if "rejected options" not in headings:
            issues.append(
                LintIssue(
                    code="missing_rejected_options",
                    file_path=path,
                    message="Decision capture missing Rejected Options section.",
                    priority=2,
                )
            )

    if _is_path_segment(path, "meetings"):
        if "next actions" not in headings:
            issues.append(
                LintIssue(
                    code="missing_next_actions",
                    file_path=path,
                    message="Meeting capture missing Next Actions section.",
                    priority=3,
                )
            )

    if _is_path_segment(path, "trips"):
        if "checklist seeds" not in headings:
            issues.append(
                LintIssue(
                    code="missing_next_actions",
                    file_path=path,
                    message="Trip debrief missing Checklist Seeds section.",
                    priority=3,
                )
            )

    return issues


def _parse_frontmatter(lines: list[str]) -> dict[str, Any]:
    """Parse YAML front matter from markdown lines."""
    if not lines or lines[0].strip() != "---":
        return {}

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw = "\n".join(lines[1:index])
            try:
                parsed = yaml.safe_load(raw) or {}
            except yaml.YAMLError:
                return {}
            return parsed if isinstance(parsed, dict) else {}

    return {}


def _collect_headings(lines: list[str]) -> dict[str, int]:
    """Collect markdown headings and their line numbers."""
    headings: dict[str, int] = {}
    for index, line in enumerate(lines, start=1):
        match = HEADING_PATTERN.match(line)
        if not match:
            continue
        headings[_normalize_heading(match.group(2))] = index
    return headings


def _normalize_heading(text: str) -> str:
    """Normalize a heading for comparisons."""
    cleaned = text.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip(":")


def _missing_metadata_fields(frontmatter: dict[str, Any]) -> list[str]:
    """Return required metadata field names that are missing or blank."""
    missing: list[str] = []
    for key in REQUIRED_METADATA_FIELDS:
        value = frontmatter.get(key)
        if value is None:
            missing.append(key)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(key)
    return missing


def _is_path_segment(path: Path, segment: str) -> bool:
    """Check if a path contains the given segment (case-insensitive)."""
    segment_lower = segment.lower()
    return any(part.lower() == segment_lower for part in path.parts)
