"""Tests for audit payload construction."""

from __future__ import annotations

from datetime import datetime

from bob.answer.audit import build_audit_payload
from bob.retrieval.search import SearchResult


def test_build_audit_payload_marks_retrieved_and_used() -> None:
    """Audit payload separates retrieved and used chunks."""
    results = [
        SearchResult(
            chunk_id=10,
            content="Top answer content.",
            score=0.9,
            source_path="/docs/top.md",
            source_type="markdown",
            locator_type="heading",
            locator_value={"heading": "Top", "start_line": 1, "end_line": 5},
            project="test",
            source_date=datetime(2024, 1, 1),
            git_repo=None,
            git_commit=None,
        ),
        SearchResult(
            chunk_id=11,
            content="Secondary content.",
            score=0.7,
            source_path="/docs/second.md",
            source_type="markdown",
            locator_type="heading",
            locator_value={"heading": "Second", "start_line": 10, "end_line": 15},
            project="test",
            source_date=datetime(2024, 1, 2),
            git_repo=None,
            git_commit=None,
        ),
    ]

    audit = build_audit_payload(results, answer="Top answer content.")

    assert len(audit.retrieved) == 2
    assert len(audit.used) == 1
    assert audit.retrieved[0].chunk_id == 10
    assert audit.retrieved[0].source_id == 1
    assert audit.retrieved[1].rank == 2
    assert audit.used[0].chunk_id == 10
    assert audit.unsupported_spans == []


def test_build_audit_payload_flags_unsupported_span() -> None:
    """Audit payload flags answers that are not in used chunks."""
    results = [
        SearchResult(
            chunk_id=20,
            content="Known content.",
            score=0.8,
            source_path="/docs/known.md",
            source_type="markdown",
            locator_type="heading",
            locator_value={"heading": "Known", "start_line": 1, "end_line": 2},
            project="test",
            source_date=datetime(2024, 2, 1),
            git_repo=None,
            git_commit=None,
        )
    ]

    audit = build_audit_payload(results, answer="Unrelated answer text.")

    assert len(audit.unsupported_spans) == 1
    assert "not found" in audit.unsupported_spans[0].reason.lower()
