"""Tests for Coach Mode gating rules."""

from __future__ import annotations

from datetime import datetime

from bob.api.schemas import Source, SourceLocator
from bob.coach.engine import generate_coach_suggestions


class DummyDB:
    """Minimal DB stub for cooldown checks."""

    def __init__(self, cooldown_types: set[str] | None = None) -> None:
        self.cooldown_types = cooldown_types or set()

    def is_suggestion_type_in_cooldown(
        self, *, project: str, suggestion_type: str, cooldown_days: int
    ) -> bool:
        _ = project
        _ = cooldown_days
        return suggestion_type in self.cooldown_types


def _make_source(
    source_id: int, confidence: str, outdated: bool, snippet: str = "Test content"
) -> Source:
    return Source(
        id=source_id,
        chunk_id=source_id,
        file_path=f"docs/source_{source_id}.md",
        file_type="markdown",
        locator=SourceLocator(type="heading", heading="Test", start_line=1, end_line=2),
        snippet=snippet,
        date=datetime(2024, 1, 1),
        date_confidence=confidence,
        project="docs",
        may_be_outdated=outdated,
        similarity_score=0.9,
        git_repo=None,
        git_commit=None,
    )


def test_coach_disabled_returns_no_suggestions():
    db = DummyDB()
    suggestions = generate_coach_suggestions(
        sources=[],
        overall_confidence=None,
        not_found=True,
        project="docs",
        coach_enabled=False,
        cooldown_days=7,
        db=db,
    )
    assert suggestions == []


def test_not_found_returns_coverage_suggestion():
    db = DummyDB()
    suggestions = generate_coach_suggestions(
        sources=[],
        overall_confidence=None,
        not_found=True,
        project="docs",
        coach_enabled=True,
        cooldown_days=7,
        db=db,
    )
    assert len(suggestions) == 1
    assert suggestions[0].type == "coverage_gaps"
    assert suggestions[0].hypothesis is True


def test_low_confidence_limits_to_one_suggestion():
    db = DummyDB()
    sources = [
        _make_source(1, "LOW", True),
        _make_source(2, "LOW", True),
    ]
    suggestions = generate_coach_suggestions(
        sources=sources,
        overall_confidence="LOW",
        not_found=False,
        project="docs",
        coach_enabled=True,
        cooldown_days=7,
        db=db,
    )
    assert len(suggestions) == 1
    assert suggestions[0].type == "staleness"


def test_low_source_count_limits_to_coverage():
    db = DummyDB()
    sources = [_make_source(1, "HIGH", False)]
    suggestions = generate_coach_suggestions(
        sources=sources,
        overall_confidence="HIGH",
        not_found=False,
        project="docs",
        coach_enabled=True,
        cooldown_days=7,
        db=db,
    )
    assert len(suggestions) == 1
    assert suggestions[0].type == "coverage_gaps"


def test_cooldown_suppresses_suggestion():
    db = DummyDB(cooldown_types={"coverage_gaps"})
    suggestions = generate_coach_suggestions(
        sources=[],
        overall_confidence=None,
        not_found=True,
        project="docs",
        coach_enabled=True,
        cooldown_days=7,
        db=db,
    )
    assert suggestions == []


def test_capture_hygiene_suggestion_when_decisions_missing_rationale():
    db = DummyDB()
    sources = [
        _make_source(1, "HIGH", False, "Decision: Ship now"),
        _make_source(2, "HIGH", False, "Decision: Pause rollout"),
    ]
    suggestions = generate_coach_suggestions(
        sources=sources,
        overall_confidence="HIGH",
        not_found=False,
        project="docs",
        coach_enabled=True,
        cooldown_days=7,
        db=db,
    )
    assert len(suggestions) == 1
    assert suggestions[0].type == "capture_hygiene"
