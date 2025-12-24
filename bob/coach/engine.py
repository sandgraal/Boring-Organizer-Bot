"""Deterministic Coach Mode suggestion engine."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from bob.api.schemas import CoachSuggestion, Source
from bob.db.database import Database

MIN_CITED_CHUNKS = 2
MAX_SUGGESTIONS = 3


@dataclass(frozen=True)
class SuggestionCandidate:
    """Internal candidate suggestion."""

    suggestion_type: str
    text: str
    why: str
    hypothesis: bool
    citations: list[Source] | None = None


def _normalize_text(text: str) -> str:
    """Normalize text for fingerprinting."""
    return " ".join(text.lower().split())


def _fingerprint(suggestion_type: str, text: str) -> str:
    """Hash suggestion type + normalized text."""
    base = f"{suggestion_type}:{_normalize_text(text)}"
    return hashlib.sha256(base.encode()).hexdigest()


def _coverage_suggestion(project: str | None, why: str) -> SuggestionCandidate:
    if project:
        text = (
            f"Add or index documents for this topic under project \"{project}\" "
            "so future answers can be grounded."
        )
    else:
        text = (
            "Add or index documents for this topic under the appropriate project tag "
            "so future answers can be grounded."
        )
    return SuggestionCandidate(
        suggestion_type="coverage_gaps",
        text=text,
        why=why,
        hypothesis=True,
        citations=None,
    )


def _select_staleness_citations(sources: Iterable[Source]) -> list[Source]:
    outdated = [source for source in sources if source.may_be_outdated]
    if outdated:
        return outdated[:2]
    return list(sources)[:1]


def _staleness_suggestion(sources: list[Source]) -> SuggestionCandidate:
    return SuggestionCandidate(
        suggestion_type="staleness",
        text="Consider re-checking this topic before acting on the answer.",
        why="Date confidence is LOW based on older source dates.",
        hypothesis=False,
        citations=_select_staleness_citations(sources),
    )


def generate_coach_suggestions(
    *,
    sources: list[Source],
    overall_confidence: str | None,
    not_found: bool,
    project: str | None,
    coach_enabled: bool,
    cooldown_days: int,
    db: Database,
    override_cooldown: bool = False,
) -> list[CoachSuggestion]:
    """Generate deterministic Coach Mode suggestions."""
    if not coach_enabled:
        return []

    project_key = project or "all"
    candidates: list[SuggestionCandidate] = []

    if not_found:
        candidates.append(_coverage_suggestion(project, "No sources matched this query."))
    else:
        if len(sources) < MIN_CITED_CHUNKS:
            candidates.append(
                _coverage_suggestion(
                    project, f"Fewer than {MIN_CITED_CHUNKS} sources were cited."
                )
            )
        if overall_confidence == "LOW":
            candidates.append(_staleness_suggestion(sources))

    # Gate: only coverage suggestions when evidence is thin or not found.
    if not_found or len(sources) < MIN_CITED_CHUNKS:
        candidates = [c for c in candidates if c.suggestion_type == "coverage_gaps"]

    # Gate: LOW confidence => at most one suggestion.
    if overall_confidence == "LOW" and candidates:
        staleness = [c for c in candidates if c.suggestion_type == "staleness"]
        candidates = staleness[:1] if staleness else candidates[:1]

    # Apply cooldown and dedupe by fingerprint.
    suggestions: list[CoachSuggestion] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not override_cooldown and db.is_suggestion_type_in_cooldown(
            project=project_key,
            suggestion_type=candidate.suggestion_type,
            cooldown_days=cooldown_days,
        ):
            continue

        suggestion_id = _fingerprint(candidate.suggestion_type, candidate.text)
        if suggestion_id in seen:
            continue
        seen.add(suggestion_id)

        suggestions.append(
            CoachSuggestion(
                id=suggestion_id,
                type=candidate.suggestion_type,
                text=candidate.text,
                why=candidate.why,
                hypothesis=candidate.hypothesis,
                citations=candidate.citations,
            )
        )
        if len(suggestions) >= MAX_SUGGESTIONS:
            break

    return suggestions
