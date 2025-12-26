"""Decision extraction from documents.

This module extracts decisions from indexed document chunks using
pattern matching and stores them in the decisions table.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from bob.db import get_database
from bob.extract.patterns import find_decisions, find_rejected_alternatives


@dataclass
class ExtractedDecision:
    """A decision extracted from a document chunk."""

    chunk_id: int
    decision_text: str
    context: str
    decision_type: str | None
    decision_date: datetime | None
    confidence: float
    rejected_alternatives: list[str]


@dataclass
class StoredDecision:
    """A decision stored in the database."""

    id: int
    chunk_id: int
    decision_text: str
    context: str | None
    decision_type: str | None
    status: str
    superseded_by: int | None
    decision_date: datetime | None
    confidence: float
    extracted_at: datetime
    # Joined fields
    source_path: str | None = None
    project: str | None = None


def extract_decisions_from_chunk(
    chunk_id: int,
    content: str,
    metadata: dict[str, Any],
    min_confidence: float = 0.6,
) -> list[ExtractedDecision]:
    """Extract decisions from a single chunk.

    Args:
        chunk_id: The chunk ID in the database.
        content: The chunk text content.
        metadata: Chunk metadata.
        min_confidence: Minimum confidence threshold.

    Returns:
        List of extracted decisions.
    """
    decisions: list[ExtractedDecision] = []

    # Find decision patterns in content
    matches = find_decisions(content, min_confidence=min_confidence)

    for match in matches:
        # Extract context (text around the match)
        start = max(0, match.start_pos - 100)
        end = min(len(content), match.end_pos + 100)
        context = content[start:end].strip()

        # Try to parse date from metadata
        decision_date = None
        if metadata.get("source_date"):
            with contextlib.suppress(ValueError, TypeError):
                decision_date = datetime.fromisoformat(metadata["source_date"])

        # Find any rejected alternatives
        rejected = find_rejected_alternatives(content)

        decisions.append(
            ExtractedDecision(
                chunk_id=chunk_id,
                decision_text=match.matched_text,
                context=context,
                decision_type=match.decision_type,
                decision_date=decision_date,
                confidence=match.confidence,
                rejected_alternatives=rejected,
            )
        )

    return decisions


def extract_decisions_from_project(
    project: str | None = None,
    min_confidence: float = 0.6,
) -> list[ExtractedDecision]:
    """Extract all decisions from a project's indexed chunks.

    Args:
        project: Project name (None for all projects).
        min_confidence: Minimum confidence threshold.

    Returns:
        List of extracted decisions.
    """
    db = get_database()

    # Query chunks with their document metadata
    query = """
        SELECT
            c.id as chunk_id,
            c.content,
            d.source_path,
            d.source_date,
            d.project
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
    """
    params: list[Any] = []

    if project:
        query += " WHERE d.project = ?"
        params.append(project)

    cursor = db.conn.execute(query, params)
    rows = cursor.fetchall()

    all_decisions: list[ExtractedDecision] = []

    for row in rows:
        metadata = {
            "source_path": row["source_path"],
            "source_date": row["source_date"],
            "project": row["project"],
        }

        chunk_decisions = extract_decisions_from_chunk(
            chunk_id=row["chunk_id"],
            content=row["content"],
            metadata=metadata,
            min_confidence=min_confidence,
        )
        all_decisions.extend(chunk_decisions)

    return all_decisions


def save_decision(decision: ExtractedDecision) -> int:
    """Save an extracted decision to the database.

    Args:
        decision: Extracted decision to save.

    Returns:
        ID of the saved decision.
    """
    db = get_database()

    cursor = db.conn.execute(
        """
        INSERT INTO decisions (
            chunk_id,
            decision_text,
            context,
            decision_type,
            status,
            decision_date,
            confidence
        ) VALUES (?, ?, ?, ?, 'active', ?, ?)
        """,
        (
            decision.chunk_id,
            decision.decision_text,
            decision.context,
            decision.decision_type,
            decision.decision_date.isoformat() if decision.decision_date else None,
            decision.confidence,
        ),
    )
    db.conn.commit()

    return cursor.lastrowid or 0


def save_decisions(decisions: list[ExtractedDecision]) -> int:
    """Save multiple decisions to the database.

    Args:
        decisions: List of extracted decisions.

    Returns:
        Number of decisions saved.
    """
    count = 0
    for decision in decisions:
        save_decision(decision)
        count += 1
    return count


def get_decisions(
    project: str | None = None,
    status: str | None = None,
    older_than_days: int | None = None,
    limit: int = 100,
) -> list[StoredDecision]:
    """Get decisions from the database.

    Args:
        project: Filter by project.
        status: Filter by status ('active', 'superseded', 'deprecated').
        older_than_days: Filter decisions older than this many days.
        limit: Maximum results.

    Returns:
        List of stored decisions.
    """
    db = get_database()

    query = """
        SELECT
            dec.id,
            dec.chunk_id,
            dec.decision_text,
            dec.context,
            dec.decision_type,
            dec.status,
            dec.superseded_by,
            dec.decision_date,
            dec.confidence,
            dec.extracted_at,
            d.source_path,
            d.project
        FROM decisions dec
        JOIN chunks c ON dec.chunk_id = c.id
        JOIN documents d ON c.document_id = d.id
        WHERE 1=1
    """
    params: list[Any] = []

    if project:
        query += " AND d.project = ?"
        params.append(project)

    if status:
        query += " AND dec.status = ?"
        params.append(status)

    if older_than_days is not None:
        cutoff = datetime.now() - timedelta(days=older_than_days)
        query += " AND COALESCE(dec.decision_date, dec.extracted_at) <= ?"
        params.append(cutoff.isoformat())

    query += " ORDER BY dec.confidence DESC, dec.extracted_at DESC LIMIT ?"
    params.append(limit)

    cursor = db.conn.execute(query, params)

    decisions: list[StoredDecision] = []
    for row in cursor.fetchall():
        decision_date = None
        if row["decision_date"]:
            with contextlib.suppress(ValueError):
                decision_date = datetime.fromisoformat(row["decision_date"])

        extracted_at = datetime.fromisoformat(row["extracted_at"])

        decisions.append(
            StoredDecision(
                id=row["id"],
                chunk_id=row["chunk_id"],
                decision_text=row["decision_text"],
                context=row["context"],
                decision_type=row["decision_type"],
                status=row["status"],
                superseded_by=row["superseded_by"],
                decision_date=decision_date,
                confidence=row["confidence"],
                extracted_at=extracted_at,
                source_path=row["source_path"],
                project=row["project"],
            )
        )

    return decisions


def get_decision(decision_id: int) -> StoredDecision | None:
    """Get a single decision by ID.

    Args:
        decision_id: Decision ID.

    Returns:
        Decision or None if not found.
    """
    db = get_database()

    cursor = db.conn.execute(
        """
        SELECT
            dec.id,
            dec.chunk_id,
            dec.decision_text,
            dec.context,
            dec.decision_type,
            dec.status,
            dec.superseded_by,
            dec.decision_date,
            dec.confidence,
            dec.extracted_at,
            d.source_path,
            d.project
        FROM decisions dec
        JOIN chunks c ON dec.chunk_id = c.id
        JOIN documents d ON c.document_id = d.id
        WHERE dec.id = ?
        """,
        (decision_id,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    decision_date = None
    if row["decision_date"]:
        with contextlib.suppress(ValueError):
            decision_date = datetime.fromisoformat(row["decision_date"])

    return StoredDecision(
        id=row["id"],
        chunk_id=row["chunk_id"],
        decision_text=row["decision_text"],
        context=row["context"],
        decision_type=row["decision_type"],
        status=row["status"],
        superseded_by=row["superseded_by"],
        decision_date=decision_date,
        confidence=row["confidence"],
        extracted_at=datetime.fromisoformat(row["extracted_at"]),
        source_path=row["source_path"],
        project=row["project"],
    )


def supersede_decision(old_id: int, new_id: int, reason: str | None = None) -> bool:  # noqa: ARG001
    """Mark a decision as superseded by another.

    Args:
        old_id: ID of the decision being superseded.
        new_id: ID of the new decision.
        reason: Optional reason for supersession.

    Returns:
        True if successful.
    """
    db = get_database()

    # Verify both decisions exist
    old = get_decision(old_id)
    new = get_decision(new_id)

    if not old or not new:
        return False

    db.conn.execute(
        """
        UPDATE decisions
        SET status = 'superseded', superseded_by = ?
        WHERE id = ?
        """,
        (new_id, old_id),
    )
    db.conn.commit()

    return True


def clear_decisions(project: str | None = None) -> int:
    """Clear extracted decisions.

    Args:
        project: Project to clear (None for all).

    Returns:
        Number of decisions deleted.
    """
    db = get_database()

    if project:
        cursor = db.conn.execute(
            """
            DELETE FROM decisions
            WHERE chunk_id IN (
                SELECT c.id FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.project = ?
            )
            """,
            (project,),
        )
    else:
        cursor = db.conn.execute("DELETE FROM decisions")

    db.conn.commit()
    return cursor.rowcount
