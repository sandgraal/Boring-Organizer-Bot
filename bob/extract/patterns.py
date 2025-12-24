"""Decision patterns for extraction.

This module defines patterns that identify decisions in document text.
Patterns are ranked by confidence based on how explicit they are.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


@dataclass
class DecisionPattern:
    """A pattern for detecting decisions in text."""

    name: str
    pattern: Pattern[str]
    confidence: float  # 0-1, how likely this is a real decision
    decision_type: str | None  # Suggested type if detected


# High-confidence patterns: explicit decision markers
HIGH_CONFIDENCE_PATTERNS = [
    DecisionPattern(
        name="adr_decision",
        pattern=re.compile(
            r"(?:^|\n)##?\s*Decision\s*\n+(.+?)(?=\n##|\n\*\*Status|\Z)",
            re.IGNORECASE | re.DOTALL,
        ),
        confidence=0.95,
        decision_type="architecture",
    ),
    DecisionPattern(
        name="adr_header",
        pattern=re.compile(
            r"(?:^|\n)#\s*ADR[- ]?\d*[:\s]+(.+?)(?=\n#|\Z)",
            re.IGNORECASE | re.DOTALL,
        ),
        confidence=0.95,
        decision_type="architecture",
    ),
    DecisionPattern(
        name="explicit_decision",
        pattern=re.compile(
            r"(?:^|\n)\s*\*?\*?Decision[:\s]*\*?\*?\s*(.+?)(?=\n\n|\n\s*\*\*|\Z)",
            re.IGNORECASE | re.DOTALL,
        ),
        confidence=0.90,
        decision_type=None,
    ),
    DecisionPattern(
        name="agreed_statement",
        pattern=re.compile(
            r"(?:^|\n)\s*\*?\*?Agreed[:\s]*\*?\*?\s*(.+?)(?=\n\n|\Z)",
            re.IGNORECASE | re.DOTALL,
        ),
        confidence=0.85,
        decision_type=None,
    ),
]

# Medium-confidence patterns: common decision language
MEDIUM_CONFIDENCE_PATTERNS = [
    DecisionPattern(
        name="we_decided",
        pattern=re.compile(
            r"[Ww]e (?:have )?decided (?:to |that )(.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.80,
        decision_type=None,
    ),
    DecisionPattern(
        name="decision_was_made",
        pattern=re.compile(
            r"[Tt]he decision (?:was|has been) made (?:to |that )(.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.80,
        decision_type=None,
    ),
    DecisionPattern(
        name="decided_on",
        pattern=re.compile(
            r"[Dd]ecided (?:on|upon)[:\s]+(.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.75,
        decision_type=None,
    ),
    DecisionPattern(
        name="we_agreed",
        pattern=re.compile(
            r"[Ww]e (?:have )?agreed (?:to |that |on )(.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.75,
        decision_type=None,
    ),
    DecisionPattern(
        name="will_use",
        pattern=re.compile(
            r"[Ww]e (?:will|shall|are going to) use (.+?) (?:for|as|because|since)",
            re.DOTALL,
        ),
        confidence=0.70,
        decision_type=None,
    ),
    DecisionPattern(
        name="team_chose",
        pattern=re.compile(
            r"(?:[Tt]he team|[Ww]e) (?:chose|choose|have chosen|has chosen) (.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.70,
        decision_type=None,
    ),
    DecisionPattern(
        name="chose_to",
        pattern=re.compile(
            r"[Ww]e (?:chose|choose|have chosen) (?:to )(.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.70,
        decision_type=None,
    ),
]

# Lower-confidence patterns: implicit decisions
LOW_CONFIDENCE_PATTERNS = [
    DecisionPattern(
        name="going_forward",
        pattern=re.compile(
            r"[Gg]oing forward,? (?:we (?:will|shall) )?(.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.60,
        decision_type=None,
    ),
    DecisionPattern(
        name="from_now_on",
        pattern=re.compile(
            r"[Ff]rom now on,? (?:we (?:will|shall) )?(.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.60,
        decision_type=None,
    ),
    DecisionPattern(
        name="selected",
        pattern=re.compile(
            r"[Ss]elected (.+?) (?:for|as|over|instead)",
            re.DOTALL,
        ),
        confidence=0.55,
        decision_type=None,
    ),
]

# Rejected alternative patterns
REJECTED_PATTERNS = [
    DecisionPattern(
        name="rejected",
        pattern=re.compile(
            r"[Rr]ejected[:\s]+(.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.85,
        decision_type=None,
    ),
    DecisionPattern(
        name="considered_but",
        pattern=re.compile(
            r"[Cc]onsidered (.+?) but (?:decided against|rejected|chose not to)",
            re.DOTALL,
        ),
        confidence=0.80,
        decision_type=None,
    ),
    DecisionPattern(
        name="instead_of",
        pattern=re.compile(
            r"(?:chose|selected|decided on|use) .+? instead of (.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.75,
        decision_type=None,
    ),
    DecisionPattern(
        name="rather_than",
        pattern=re.compile(
            r"(?:use|chose|selected|prefer) .+? rather than (.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.75,
        decision_type=None,
    ),
    DecisionPattern(
        name="not_alternative",
        pattern=re.compile(
            r"(?:use|chose|decided to|selected) .+?, not (.+?)(?:\.|$)",
            re.DOTALL,
        ),
        confidence=0.70,
        decision_type=None,
    ),
]

# All patterns grouped by confidence level
ALL_PATTERNS = HIGH_CONFIDENCE_PATTERNS + MEDIUM_CONFIDENCE_PATTERNS + LOW_CONFIDENCE_PATTERNS

# Decision type detection patterns
TYPE_PATTERNS = {
    "architecture": re.compile(
        r"(?:architecture|design|system|infrastructure|database|api|schema)",
        re.IGNORECASE,
    ),
    "process": re.compile(
        r"(?:process|workflow|procedure|methodology|approach)",
        re.IGNORECASE,
    ),
    "technology": re.compile(
        r"(?:framework|library|tool|language|stack|platform)",
        re.IGNORECASE,
    ),
    "feature": re.compile(
        r"(?:feature|functionality|capability|requirement)",
        re.IGNORECASE,
    ),
    "policy": re.compile(
        r"(?:policy|rule|guideline|standard|convention)",
        re.IGNORECASE,
    ),
}


def detect_decision_type(text: str) -> str | None:
    """Detect the type of decision based on content.

    Args:
        text: Decision text.

    Returns:
        Detected type or None.
    """
    for decision_type, pattern in TYPE_PATTERNS.items():
        if pattern.search(text):
            return decision_type
    return None


@dataclass
class PatternMatch:
    """A matched decision pattern."""

    pattern_name: str
    matched_text: str
    full_match: str
    confidence: float
    decision_type: str | None
    start_pos: int
    end_pos: int


def find_decisions(text: str, min_confidence: float = 0.5) -> list[PatternMatch]:
    """Find potential decisions in text using patterns.

    Args:
        text: Text to search.
        min_confidence: Minimum pattern confidence to include.

    Returns:
        List of pattern matches sorted by confidence.
    """
    matches: list[PatternMatch] = []

    for pattern in ALL_PATTERNS:
        if pattern.confidence < min_confidence:
            continue

        for match in pattern.pattern.finditer(text):
            # Get the captured group (the decision text)
            decision_text = match.group(1).strip() if match.groups() else match.group(0).strip()

            # Skip very short matches
            if len(decision_text) < 10:
                continue

            # Detect type if not specified by pattern
            decision_type = pattern.decision_type or detect_decision_type(decision_text)

            matches.append(
                PatternMatch(
                    pattern_name=pattern.name,
                    matched_text=decision_text,
                    full_match=match.group(0),
                    confidence=pattern.confidence,
                    decision_type=decision_type,
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )

    # Sort by confidence (highest first)
    matches.sort(key=lambda m: m.confidence, reverse=True)

    # Remove overlapping matches (keep highest confidence)
    filtered: list[PatternMatch] = []
    for pm in matches:
        overlaps = False
        for existing in filtered:
            if (
                pm.start_pos < existing.end_pos
                and pm.end_pos > existing.start_pos
            ):
                overlaps = True
                break
        if not overlaps:
            filtered.append(pm)

    return filtered


def find_rejected_alternatives(text: str) -> list[str]:
    """Find rejected alternatives mentioned in text.

    Args:
        text: Text to search.

    Returns:
        List of rejected alternative descriptions.
    """
    alternatives: list[str] = []

    for pattern in REJECTED_PATTERNS:
        for match in pattern.pattern.finditer(text):
            alt_text = match.group(1).strip() if match.groups() else match.group(0).strip()
            if len(alt_text) >= 5:
                alternatives.append(alt_text)

    return alternatives
