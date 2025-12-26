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

    audit = build_audit_payload(results)

    assert len(audit.retrieved) == 2
    assert len(audit.used) == 1
    assert audit.retrieved[0].chunk_id == 10
    assert audit.retrieved[0].source_id == 1
    assert audit.retrieved[1].rank == 2
    assert audit.used[0].chunk_id == 10
    assert audit.unsupported_spans == []
