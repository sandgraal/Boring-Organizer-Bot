"""Helpers for extracting dates from document content."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import yaml

FRONTMATTER_KEYS = ("date", "updated", "last_updated", "last_modified", "modified")
DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)
MONTHS = (
    "jan",
    "january",
    "feb",
    "february",
    "mar",
    "march",
    "apr",
    "april",
    "may",
    "jun",
    "june",
    "jul",
    "july",
    "aug",
    "august",
    "sep",
    "sept",
    "september",
    "oct",
    "october",
    "nov",
    "november",
    "dec",
    "december",
)

CONTEXT_KEYWORDS = (
    "as of",
    "updated",
    "last updated",
    "last modified",
    "modified",
    "dated",
    "date",
    "published",
)

ISO_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?\b"
)
SLASH_DATE_RE = re.compile(r"\b\d{4}/\d{2}/\d{2}\b")
DOT_DATE_RE = re.compile(r"\b\d{4}\.\d{2}\.\d{2}\b")
MONTH_NAME_RE = re.compile(
    rf"\b(?:{'|'.join(MONTHS)})\s+\d{{1,2}},\s+\d{{4}}\b", re.IGNORECASE
)
DAY_MONTH_RE = re.compile(
    rf"\b\d{{1,2}}\s+(?:{'|'.join(MONTHS)})\s+\d{{4}}\b", re.IGNORECASE
)


def extract_date_from_content(content: str) -> datetime | None:
    """Extract a document date from content if possible."""
    if not content:
        return None

    frontmatter = _parse_frontmatter(content)
    for key in FRONTMATTER_KEYS:
        if key in frontmatter:
            candidate = frontmatter[key]
            parsed = parse_date_hint(str(candidate))
            if parsed:
                return parsed

    snippet = "\n".join(content.splitlines()[:40])
    return parse_date_hint(snippet)


def parse_date_hint(text: str) -> datetime | None:
    """Parse the first supported date found within a text block."""
    if not text:
        return None

    contextual = _parse_contextual_date(text)
    if contextual:
        return contextual

    return _find_first_date(text)


def _parse_contextual_date(text: str) -> datetime | None:
    """Prefer dates on lines with explicit update/as-of markers."""
    for line in text.splitlines():
        lowered = line.lower()
        if not any(keyword in lowered for keyword in CONTEXT_KEYWORDS):
            continue
        parsed = _find_first_date(line)
        if parsed:
            return parsed
    return None


def _find_first_date(text: str) -> datetime | None:
    """Find and parse the first supported date in text."""
    for pattern in (ISO_DATE_RE, SLASH_DATE_RE, DOT_DATE_RE, MONTH_NAME_RE, DAY_MONTH_RE):
        match = pattern.search(text)
        if not match:
            continue
        parsed = _parse_date_string(match.group(0))
        if parsed:
            return parsed

    return None


def _parse_date_string(value: str) -> datetime | None:
    """Parse supported date string formats."""
    candidate = value.strip()
    parsed = _parse_iso(candidate)
    if parsed:
        return parsed

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def _parse_iso(value: str) -> datetime | None:
    """Parse ISO-8601-ish strings with optional Z suffix."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1]
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML front matter at the top of a markdown document."""
    lines = content.splitlines()
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
