"""Answer formatting with citations and date confidence."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from rich.text import Text

from bob.config import get_config

if TYPE_CHECKING:
    from rich.console import RenderableType

    from bob.retrieval import SearchResult


class DateConfidence(Enum):
    """Confidence level based on document age."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


def get_date_confidence(source_date: datetime | None) -> DateConfidence:
    """Determine confidence level based on document age.

    Args:
        source_date: Document date.

    Returns:
        DateConfidence level.
    """
    if source_date is None:
        return DateConfidence.UNKNOWN

    config = get_config().date_confidence
    now = datetime.now()
    age = now - source_date

    if age <= timedelta(days=config.high_max_days):
        return DateConfidence.HIGH
    elif age <= timedelta(days=config.medium_max_days):
        return DateConfidence.MEDIUM
    else:
        return DateConfidence.LOW


def is_outdated(source_date: datetime | None) -> bool:
    """Check if a document may be outdated.

    Args:
        source_date: Document date.

    Returns:
        True if document may be outdated.
    """
    if source_date is None:
        return False

    config = get_config().date_confidence
    now = datetime.now()
    age = now - source_date

    return age > timedelta(days=config.outdated_threshold_days)


def format_locator(result: SearchResult) -> str:
    """Format a locator for display.

    Args:
        result: Search result with locator information.

    Returns:
        Human-readable locator string.
    """
    locator = result.locator_value
    loc_type = result.locator_type

    if loc_type == "heading":
        heading = locator.get("heading", "")
        start = locator.get("start_line", 0)
        end = locator.get("end_line", 0)

        if locator.get("git_file"):
            return f'{locator["git_file"]}:{locator.get("git_commit", "")} heading: "{heading}" (lines {start}-{end})'
        return f'heading: "{heading}" (lines {start}-{end})'

    elif loc_type == "page":
        page = locator.get("page", 0)
        total = locator.get("total_pages", 0)
        return f"page {page}/{total}"

    elif loc_type == "paragraph":
        idx = locator.get("paragraph_index", 0)
        heading = locator.get("parent_heading") or locator.get("heading", "")
        if heading:
            return f'paragraph {idx} under "{heading}"'
        return f"paragraph {idx}"

    elif loc_type == "sheet":
        sheet = locator.get("sheet_name", "")
        rows = locator.get("row_count", 0)
        return f'sheet "{sheet}" ({rows} rows)'

    elif loc_type == "section":
        return f"section: {locator.get('section', '')}"

    elif loc_type == "line":
        start = locator.get("start_line") or locator.get("line")
        end = locator.get("end_line")
        line_label = f"{start}-{end}" if end else f"{start}"
        git_file = locator.get("git_file")
        git_commit = locator.get("git_commit")
        if git_file:
            commit_label = f":{git_commit}" if git_commit else ""
            return f"{git_file}{commit_label} lines {line_label}"
        return f"lines {line_label}"

    else:
        return str(locator)


def format_citation(result: SearchResult, index: int) -> Text:
    """Format a single citation.

    Args:
        result: Search result.
        index: Citation number (1-based).

    Returns:
        Rich Text object with formatted citation.
    """
    text = Text()

    # Citation number and path
    text.append(f"  {index}. ", style="bold cyan")
    text.append(f"[{result.source_path}]", style="blue")
    text.append(" ")

    # Locator
    locator_str = format_locator(result)
    text.append(locator_str, style="dim")
    text.append("\n")

    # Date and confidence
    text.append("     ", style="")

    if result.source_date:
        date_str = result.source_date.strftime("%Y-%m-%d")
        text.append(f"Date: {date_str}", style="")
    else:
        text.append("Date: unknown", style="dim")

    text.append(" | ", style="dim")

    confidence = get_date_confidence(result.source_date)
    conf_style = {
        DateConfidence.HIGH: "green",
        DateConfidence.MEDIUM: "yellow",
        DateConfidence.LOW: "red",
        DateConfidence.UNKNOWN: "dim",
    }[confidence]
    text.append(f"Confidence: {confidence.value}", style=conf_style)

    # Outdated warning
    if is_outdated(result.source_date):
        text.append("\n     ", style="")
        text.append("⚠️  This may be outdated", style="yellow italic")

    text.append("\n")

    return text


def format_answer(query: str, results: list[SearchResult]) -> RenderableType:
    """Format an answer with citations.

    This function enforces the "no citation => no claim" rule by only
    returning retrieved passages with citations, not generating claims.

    Args:
        query: Original query.
        results: Search results.

    Returns:
        Rich console group for display.
    """
    from rich.console import Group
    from rich.rule import Rule

    config = get_config()
    renderables: list[RenderableType] = []

    # Header
    header = Text("Answer based on retrieved documents:", style="bold")
    renderables.append(header)
    if query:
        renderables.append(Text(f"Query: {query}", style="dim"))

    # Note about generation
    if not config.llm.enabled:
        note = Text("(LLM generation disabled - showing retrieved passages)", style="dim")
        renderables.append(note)
        renderables.append(Text())

    # Top result as primary answer
    if results:
        top = results[0]
        renderables.append(Text("Most Relevant:", style="bold cyan"))
        content_preview = top.content[:500] + ("..." if len(top.content) > 500 else "")
        renderables.append(Text(content_preview, style="italic"))
        renderables.append(Text())

    # Sources section
    renderables.append(Text("Sources:", style="bold"))

    for i, result in enumerate(results, start=1):
        citation = format_citation(result, i)
        renderables.append(citation)

    # Quality gate: remind about citation requirement
    renderables.append(Rule(style="dim"))
    renderables.append(
        Text("All claims above are grounded in the cited sources.", style="dim italic")
    )

    return Group(*renderables)


def format_answer_plain(query: str, results: list[SearchResult]) -> str:
    """Format an answer without Rich markup (for testing/logging).

    Args:
        query: Original query.
        results: Search results.

    Returns:
        Plain text formatted answer.
    """
    lines = []
    lines.append("Answer based on retrieved documents:\n")
    if query:
        lines.append(f"Query: {query}")
        lines.append("")

    if results:
        top = results[0]
        lines.append("Most Relevant:")
        lines.append(f"{top.content[:500]}{'...' if len(top.content) > 500 else ''}\n")

    lines.append("Sources:")

    for i, result in enumerate(results, start=1):
        lines.append(f"  {i}. [{result.source_path}] {format_locator(result)}")

        if result.source_date:
            date_str = result.source_date.strftime("%Y-%m-%d")
            confidence = get_date_confidence(result.source_date)
            lines.append(f"     Date: {date_str} | Confidence: {confidence.value}")
        else:
            lines.append("     Date: unknown | Confidence: UNKNOWN")

        if is_outdated(result.source_date):
            lines.append("     ⚠️  This may be outdated")

    lines.append("")
    lines.append("────────────────────────────────────────")
    lines.append("All claims above are grounded in the cited sources.")

    return "\n".join(lines)


def highlight_terms(text: str, query: str, style: str = "bold yellow") -> Text:
    """Highlight query terms in a text snippet.

    Args:
        text: Text to highlight.
        query: Original query (terms will be extracted).
        style: Rich style for highlighted terms.

    Returns:
        Rich Text object with highlighted terms.
    """
    # Extract meaningful terms from query (skip syntax markers)
    terms = []
    # Remove quoted phrases and special syntax for term extraction
    clean_query = re.sub(r'"[^"]*"', " ", query)  # Remove quoted phrases
    clean_query = re.sub(r"project:\S+", " ", clean_query)  # Remove project filter
    clean_query = re.sub(r"-\S+", " ", clean_query)  # Remove exclusions

    for word in clean_query.lower().split():
        # Skip short words and common terms
        if len(word) >= 3 and word not in {"the", "and", "for", "with", "how", "what", "why"}:
            terms.append(word)

    if not terms:
        return Text(text, style="dim")

    # Build regex pattern for case-insensitive matching
    pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE)

    # Build Rich Text with highlights
    result = Text()
    last_end = 0

    for match in pattern.finditer(text):
        # Add text before match
        if match.start() > last_end:
            result.append(text[last_end : match.start()], style="dim")
        # Add highlighted match
        result.append(match.group(), style=style)
        last_end = match.end()

    # Add remaining text
    if last_end < len(text):
        result.append(text[last_end:], style="dim")

    return result


def format_decision_badge(result: SearchResult) -> Text | None:
    """Format decision badges for a search result.

    Shows if the result contains decisions and their status.

    Args:
        result: Search result with potential decisions.

    Returns:
        Rich Text with decision badges, or None if no decisions.
    """
    if not result.decisions:
        return None

    text = Text()
    active_count = sum(1 for d in result.decisions if d.status == "active")
    superseded_count = sum(1 for d in result.decisions if d.status == "superseded")

    if active_count > 0:
        text.append(" [", style="dim")
        text.append(f"📋 {active_count} decision{'s' if active_count > 1 else ''}", style="green")
        text.append("]", style="dim")

    if superseded_count > 0:
        text.append(" [", style="dim")
        text.append(f"⚠️ {superseded_count} superseded", style="yellow")
        text.append("]", style="dim")

    return text if text.plain else None


def format_superseded_warning(results: list[SearchResult]) -> Text | None:
    """Format a warning if results contain superseded decisions.

    Args:
        results: Search results.

    Returns:
        Warning text or None if no superseded decisions.
    """
    superseded = []
    for result in results:
        for decision in result.decisions:
            if decision.status == "superseded":
                superseded.append(decision)

    if not superseded:
        return None

    text = Text()
    text.append("\n⚠️  Warning: ", style="bold yellow")
    text.append(
        f"{len(superseded)} superseded decision{'s' if len(superseded) > 1 else ''} found in results.\n",
        style="yellow",
    )
    text.append("   These decisions may have been replaced by newer ones.\n", style="dim")

    for d in superseded[:3]:  # Show up to 3
        preview = d.decision_text[:50] + "..." if len(d.decision_text) > 50 else d.decision_text
        preview = preview.replace("\n", " ")
        text.append("   • ", style="dim")
        text.append(f"#{d.decision_id}: ", style="yellow")
        text.append(preview, style="dim")
        if d.superseded_by:
            text.append(f" → replaced by #{d.superseded_by}", style="cyan")
        text.append("\n")

    if len(superseded) > 3:
        text.append(f"   ... and {len(superseded) - 3} more\n", style="dim")

    return text
