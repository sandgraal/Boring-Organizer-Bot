"""Decision extraction from documents.

TODO: Implement decision extraction logic.

This module should:
1. Define patterns that identify decisions
2. Extract decision text and context from chunks
3. Classify decision types
4. Handle superseded decisions

Example patterns to detect:
- "We decided to..."
- "The decision was made to..."
- "ADR: ..."
- "Decision: ..."
- "Agreed: ..."

Next file to create: bob/extract/patterns.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ExtractedDecision:
    """A decision extracted from a document chunk."""

    chunk_id: int
    decision_text: str
    context: str
    decision_type: str | None
    decision_date: datetime | None
    confidence: float


def extract_decisions_from_chunk(
    chunk_id: int,
    content: str,
    metadata: dict[str, Any],
) -> list[ExtractedDecision]:
    """Extract decisions from a single chunk.

    Args:
        chunk_id: The chunk ID in the database.
        content: The chunk text content.
        metadata: Chunk metadata.

    Returns:
        List of extracted decisions.

    TODO: Implement decision extraction logic.
    """
    # Placeholder implementation
    # Real implementation should:
    # 1. Apply decision patterns to content
    # 2. Extract decision text and surrounding context
    # 3. Classify decision type
    # 4. Estimate confidence

    raise NotImplementedError(
        "Decision extraction not yet implemented. See bob/extract/patterns.py for next steps."
    )


def extract_decisions_from_project(
    project: str,
) -> list[ExtractedDecision]:
    """Extract all decisions from a project's indexed chunks.

    Args:
        project: Project name.

    Returns:
        List of extracted decisions.

    TODO: Implement batch extraction.
    """
    raise NotImplementedError("Decision extraction not yet implemented.")
