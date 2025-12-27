"""Text utilities for B.O.B."""

from __future__ import annotations

import re


def slugify(value: str, fallback: str = "") -> str:
    """Normalize a string into a filesystem-safe slug.

    Converts text to lowercase, replaces non-alphanumeric characters with
    hyphens, and collapses multiple hyphens into single ones.

    Args:
        value: Text to slugify.
        fallback: Value to return if result would be empty.

    Returns:
        Slugified string or fallback if empty.

    Examples:
        >>> slugify("Hello World!")
        'hello-world'
        >>> slugify("API v2.0 -- Beta")
        'api-v2-0-beta'
        >>> slugify("   ")
        ''
        >>> slugify("   ", fallback="untitled")
        'untitled'
    """
    normalized = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized)
    slug = re.sub(r"-{2,}", "-", slug)
    result = slug.strip("-")
    return result or fallback
