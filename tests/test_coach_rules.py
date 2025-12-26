"""Tests for Coach Mode gating rules."""

from __future__ import annotations

from datetime import datetime

from bob.api.schemas import Source, SourceLocator
from bob.coach.engine import generate_coach_suggestions


class DummyDB:
    """Minimal DB stub for cooldown checks."""

    def __init__(
        self,
        cooldown_types: set[str] | None = None,
        health: dict[str, object] | None = None,
    ) -> None:
        self.cooldown_types = cooldown_types or set()
        self.health = health or {}

    def is_suggestion_type_in_cooldown(
        self, *, project: str, suggestion_type: str, cooldown_days: int
    ) -> bool:
        _ = project
        _ = cooldown_days
        return suggestion_type in self.cooldown_types

    def get_feedback_metrics(
        self, *, project: str | None = None, window_hours: int = 48
    ) -> dict[str, object]:
        _ = project
        _ = window_hours
        return self.health.get(
            "feedback_metrics",
            {
                "total": 0,
                "counts": {},
                "not_found_frequency": 0.0,
                "repeated_questions": [],
            },
        )

    def get_missing_metadata_total(self, *, project: str | None = None) -> int:
        _ = project
        return int(self.health.get("missing_metadata_total", 0))

    def get_permission_denial_metrics(
        self,
        *,
        project: str | None = None,
        window_hours: int | None = 168,
        limit: int = 5,
    ) -> dict[str, object]:
        _ = project
        _ = window_hours
        _ = limit
        return self.health.get(
            "permission_metrics",
            {"total": 0, "counts": {}, "recent": [], "window_hours": window_hours},
        )

    def get_project_document_counts(
        self, project: str | None = None
    ) -> list[dict[str, object]]:
        _ = project
        return self.health.get("project_document_counts", [])

    def get_search_history_stats(
        self,
        *,
        window_hours: int = 168,
        min_count: int = 1,
        project: str | None = None,
    ) -> list[dict[str, object]]:
        _ = window_hours
        _ = min_count
        _ = project
        return self.health.get("search_history_stats", [])

    def get_stale_document_buckets(
        self,
        *,
        buckets_days: list[int],
        source_type: str | None = None,
        project: str | None = None,
    ) -> list[dict[str, object]]:
        _ = buckets_days
        _ = source_type
        _ = project
        return self.health.get("stale_notes", [])

    def get_stale_decision_buckets(
        self, *, buckets_days: list[int], project: str | None = None
    ) -> list[dict[str, object]]:
        _ = buckets_days
        _ = project
        return self.health.get("stale_decisions", [])

    def get_ingestion_error_metrics(
        self, *, project: str | None = None, window_hours: int = 168, limit: int = 5
    ) -> dict[str, object]:
        _ = project
        _ = window_hours
        _ = limit
        return self.health.get("ingestion_metrics", {"total": 0, "counts": {}, "recent": []})


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
    assert suggestions[0].routine_action == "daily-checkin"


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
    assert suggestions[0].routine_action == "weekly-review"


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
    assert suggestions[0].routine_action == "daily-checkin"


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
    assert suggestions[0].routine_action is None


def test_health_suggestion_surfaces_feedback_gaps():
    db = DummyDB(
        health={
            "feedback_metrics": {
                "total": 5,
                "counts": {"didnt_answer": 2},
                "not_found_frequency": 0.4,
                "repeated_questions": [],
            }
        }
    )
    sources = [_make_source(1, "HIGH", False), _make_source(2, "HIGH", False)]
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
    assert suggestions[0].type == "health_not_found"
    assert suggestions[0].routine_action == "daily-checkin"
    assert suggestions[0].hypothesis is True
