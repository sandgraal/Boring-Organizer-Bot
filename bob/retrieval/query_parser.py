"""Query parser for advanced search syntax.

Supports:
- Quoted phrases: "exact match"
- Term exclusion: -unwanted
- Project filter: project:name
- Combinations: "exact phrase" -exclude project:docs
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedQuery:
    """Parsed search query with extracted components."""

    # Main search text (for embedding)
    text: str

    # Exact phrases that must appear (from "quoted text")
    required_phrases: list[str] = field(default_factory=list)

    # Terms to exclude (from -term)
    excluded_terms: list[str] = field(default_factory=list)

    # Project filter (from project:name)
    project_filter: str | None = None

    # Original query for reference
    original: str = ""

    def has_filters(self) -> bool:
        """Check if query has any special filters."""
        return bool(self.required_phrases or self.excluded_terms or self.project_filter)


def parse_query(query: str) -> ParsedQuery:
    """Parse a search query into structured components.

    Syntax:
        - "phrase": Exact phrase match (content must contain this)
        - -term: Exclude results containing this term
        - project:name: Filter to specific project

    Examples:
        >>> parse_query('how to configure')
        ParsedQuery(text='how to configure', ...)

        >>> parse_query('"exact match" -exclude')
        ParsedQuery(text='exact match', required_phrases=['exact match'],
                    excluded_terms=['exclude'], ...)

        >>> parse_query('search query project:docs')
        ParsedQuery(text='search query', project_filter='docs', ...)

    Args:
        query: Raw query string.

    Returns:
        ParsedQuery with extracted components.
    """
    original = query
    required_phrases: list[str] = []
    excluded_terms: list[str] = []
    project_filter: str | None = None

    # Extract quoted phrases: "exact phrase"
    phrase_pattern = r'"([^"]+)"'
    for match in re.finditer(phrase_pattern, query):
        phrase = match.group(1).strip()
        if phrase:
            required_phrases.append(phrase)
    # Remove quoted phrases from query
    query = re.sub(phrase_pattern, " ", query)

    # Extract project filter: project:name
    project_pattern = r"\bproject:(\S+)"
    project_match = re.search(project_pattern, query, re.IGNORECASE)
    if project_match:
        project_filter = project_match.group(1)
        query = re.sub(project_pattern, " ", query, flags=re.IGNORECASE)

    # Extract excluded terms: -term
    exclude_pattern = r"(?:^|\s)-(\S+)"
    for match in re.finditer(exclude_pattern, query):
        term = match.group(1).strip()
        if term and not term.startswith("-"):  # Avoid double negatives
            excluded_terms.append(term.lower())
    # Remove exclusions from query
    query = re.sub(exclude_pattern, " ", query)

    # Clean up remaining text
    text = " ".join(query.split()).strip()

    # If only phrases were provided, use them as the search text
    if not text and required_phrases:
        text = " ".join(required_phrases)

    return ParsedQuery(
        text=text,
        required_phrases=required_phrases,
        excluded_terms=excluded_terms,
        project_filter=project_filter,
        original=original,
    )


def filter_results_by_query(
    results: list[dict[str, Any]],
    parsed: ParsedQuery,
    content_key: str = "content",
) -> list[dict[str, Any]]:
    """Filter results based on parsed query constraints.

    Applies:
    - Required phrase matching (case-insensitive)
    - Term exclusion (case-insensitive)

    Args:
        results: List of result dictionaries.
        parsed: Parsed query with filters.
        content_key: Key in result dict containing searchable text.

    Returns:
        Filtered list of results.
    """
    if not parsed.has_filters():
        return results

    filtered = []
    for result in results:
        content = result.get(content_key, "").lower()

        # Check required phrases
        if parsed.required_phrases and not all(
            phrase.lower() in content for phrase in parsed.required_phrases
        ):
            continue

        # Check excluded terms
        if parsed.excluded_terms and any(term in content for term in parsed.excluded_terms):
            continue

        filtered.append(result)

    return filtered
