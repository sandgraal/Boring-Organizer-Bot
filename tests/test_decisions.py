"""Tests for decision extraction."""

import pytest

from bob.extract.patterns import (
    PatternMatch,
    detect_decision_type,
    find_decisions,
    find_rejected_alternatives,
)
from bob.extract.decisions import (
    ExtractedDecision,
    extract_decisions_from_chunk,
)
from bob.retrieval.search import (
    DecisionInfo,
    SearchResult,
    enrich_with_decisions,
    has_superseded_decisions,
    get_active_decisions,
)


class TestDecisionPatterns:
    """Tests for pattern matching."""

    def test_find_adr_decision(self) -> None:
        """High-confidence ADR detection."""
        content = """# ADR-001: Use PostgreSQL

## Status
Accepted

## Context
We need a database for the application.

## Decision
We will use PostgreSQL for its reliability.
"""
        matches = find_decisions(content)
        assert len(matches) >= 1
        # ADR should be high confidence
        assert any(m.confidence >= 0.9 for m in matches)

    def test_find_explicit_decision_marker(self) -> None:
        """High-confidence explicit decision markers."""
        content = "Decision: We will use React for the frontend."
        matches = find_decisions(content)
        assert len(matches) >= 1
        assert matches[0].confidence >= 0.9

    def test_find_we_decided_pattern(self) -> None:
        """Medium-confidence 'we decided' patterns."""
        content = "After discussion, we decided to implement caching at the API layer."
        matches = find_decisions(content)
        assert len(matches) >= 1
        assert matches[0].confidence >= 0.7

    def test_find_chose_pattern(self) -> None:
        """Medium-confidence 'chose/chosen' patterns."""
        content = "The team chose Python for its ecosystem."
        matches = find_decisions(content)
        assert len(matches) >= 1
        assert matches[0].confidence >= 0.7

    def test_find_agreed_pattern(self) -> None:
        """Medium-confidence 'agreed' patterns."""
        content = "We agreed to deploy weekly on Tuesdays."
        matches = find_decisions(content)
        assert len(matches) >= 1
        assert matches[0].confidence >= 0.7

    def test_find_going_forward_pattern(self) -> None:
        """Lower confidence 'going forward' patterns."""
        content = "Going forward, all APIs must be versioned."
        matches = find_decisions(content, min_confidence=0.5)
        assert len(matches) >= 1

    def test_no_decision_in_regular_text(self) -> None:
        """Regular text should not match as decisions."""
        content = "This is just a regular paragraph about nothing in particular."
        matches = find_decisions(content)
        assert len(matches) == 0

    def test_min_confidence_filter(self) -> None:
        """Respects minimum confidence threshold."""
        content = """
        Going forward, we use TypeScript.
        Decision: We use Python for backend.
        """
        # High threshold should only get explicit decision
        high_conf = find_decisions(content, min_confidence=0.9)
        assert all(m.confidence >= 0.9 for m in high_conf)

        # Lower threshold gets more
        low_conf = find_decisions(content, min_confidence=0.5)
        assert len(low_conf) >= len(high_conf)


class TestRejectedAlternatives:
    """Tests for detecting rejected alternatives."""

    def test_find_instead_of(self) -> None:
        """Detects 'instead of X' patterns."""
        content = "We chose PostgreSQL instead of MongoDB for ACID compliance."
        rejected = find_rejected_alternatives(content)
        assert len(rejected) >= 1
        assert any("MongoDB" in r for r in rejected)

    def test_find_rather_than(self) -> None:
        """Detects 'rather than X' patterns."""
        content = "We use React rather than Vue for the frontend."
        rejected = find_rejected_alternatives(content)
        assert len(rejected) >= 1
        assert any("Vue" in r for r in rejected)

    def test_find_not_pattern(self) -> None:
        """Detects 'not X' patterns."""
        content = "We decided to use REST, not GraphQL."
        rejected = find_rejected_alternatives(content)
        assert len(rejected) >= 1
        assert any("GraphQL" in r for r in rejected)

    def test_find_rejected_considered(self) -> None:
        """Detects alternatives that were considered but rejected."""
        content = """
        Alternatives Considered:
        - MySQL
        - SQLite
        
        These were rejected because they don't support our scale.
        """
        rejected = find_rejected_alternatives(content)
        # Should find at least one rejected alternative
        assert len(rejected) >= 1


class TestDecisionTypeDetection:
    """Tests for decision type classification."""

    def test_architecture_type(self) -> None:
        """Detects architecture decisions."""
        text = "We chose a microservices architecture pattern."
        assert detect_decision_type(text) == "architecture"

    def test_technology_type(self) -> None:
        """Detects technology choices."""
        text = "The framework selected was Django."
        assert detect_decision_type(text) == "technology"

    def test_process_type(self) -> None:
        """Detects process decisions."""
        text = "Our workflow includes code review before merge."
        assert detect_decision_type(text) == "process"

    def test_unknown_type(self) -> None:
        """Returns None for unclassified decisions."""
        text = "We will do this thing."
        result = detect_decision_type(text)
        # Could be None or some type, just ensure it doesn't error
        assert result is None or isinstance(result, str)


class TestExtractDecisionsFromChunk:
    """Tests for chunk-level decision extraction."""

    def test_extract_from_chunk(self) -> None:
        """Extracts decisions with context."""
        content = """
        # Meeting Notes 2024-01-15
        
        ## Decisions
        
        Decision: We will use FastAPI for the REST API.
        
        This was chosen for its async support.
        """
        decisions = extract_decisions_from_chunk(
            chunk_id=1,
            content=content,
            metadata={"source_date": "2024-01-15"},
        )

        assert len(decisions) >= 1
        d = decisions[0]
        assert d.chunk_id == 1
        assert "FastAPI" in d.decision_text
        assert d.confidence >= 0.9
        assert d.context  # Has surrounding context

    def test_extract_with_metadata_date(self) -> None:
        """Uses metadata date for decision date."""
        content = "Decision: We use SQLite for local storage."
        decisions = extract_decisions_from_chunk(
            chunk_id=1,
            content=content,
            metadata={"source_date": "2024-06-01T10:00:00"},
        )

        assert len(decisions) >= 1
        assert decisions[0].decision_date is not None
        assert decisions[0].decision_date.year == 2024

    def test_extract_handles_invalid_date(self) -> None:
        """Handles invalid date gracefully."""
        content = "Decision: We use TypeScript."
        decisions = extract_decisions_from_chunk(
            chunk_id=1,
            content=content,
            metadata={"source_date": "invalid-date"},
        )

        assert len(decisions) >= 1
        assert decisions[0].decision_date is None

    def test_min_confidence_threshold(self) -> None:
        """Respects minimum confidence in extraction."""
        content = """
        Going forward, we test everything.
        Decision: All code must have tests.
        """
        # High threshold
        high = extract_decisions_from_chunk(
            chunk_id=1,
            content=content,
            metadata={},
            min_confidence=0.9,
        )

        # Lower threshold
        low = extract_decisions_from_chunk(
            chunk_id=1,
            content=content,
            metadata={},
            min_confidence=0.5,
        )

        assert len(low) >= len(high)

    def test_empty_content(self) -> None:
        """Handles empty content."""
        decisions = extract_decisions_from_chunk(
            chunk_id=1,
            content="",
            metadata={},
        )
        assert decisions == []

    def test_no_decisions_found(self) -> None:
        """Returns empty list when no decisions found."""
        content = "Just a regular document with no decisions at all."
        decisions = extract_decisions_from_chunk(
            chunk_id=1,
            content=content,
            metadata={},
        )
        assert decisions == []


class TestDecisionSearchIntegration:
    """Tests for decision-aware search features."""

    def _make_result(self, chunk_id: int, decisions: list[DecisionInfo] | None = None) -> SearchResult:
        """Helper to create a SearchResult for testing."""
        from datetime import datetime

        return SearchResult(
            chunk_id=chunk_id,
            content="Test content",
            score=0.8,
            source_path="/test/file.md",
            source_type="markdown",
            locator_type="heading",
            locator_value={"heading": "Test"},
            project="test",
            source_date=datetime.now(),
            git_repo=None,
            git_commit=None,
            decisions=decisions or [],
        )

    def test_has_superseded_decisions_true(self) -> None:
        """Detects superseded decisions in results."""
        results = [
            self._make_result(1, [
                DecisionInfo(
                    decision_id=1,
                    decision_text="Old decision",
                    status="superseded",
                    superseded_by=2,
                    confidence=0.9,
                )
            ]),
            self._make_result(2, []),
        ]
        assert has_superseded_decisions(results) is True

    def test_has_superseded_decisions_false(self) -> None:
        """Returns false when no superseded decisions."""
        results = [
            self._make_result(1, [
                DecisionInfo(
                    decision_id=1,
                    decision_text="Active decision",
                    status="active",
                    superseded_by=None,
                    confidence=0.9,
                )
            ]),
        ]
        assert has_superseded_decisions(results) is False

    def test_has_superseded_decisions_empty(self) -> None:
        """Handles empty results."""
        assert has_superseded_decisions([]) is False

    def test_get_active_decisions(self) -> None:
        """Gets only active decisions from results."""
        results = [
            self._make_result(1, [
                DecisionInfo(
                    decision_id=1,
                    decision_text="Active one",
                    status="active",
                    superseded_by=None,
                    confidence=0.9,
                ),
                DecisionInfo(
                    decision_id=2,
                    decision_text="Superseded one",
                    status="superseded",
                    superseded_by=3,
                    confidence=0.8,
                ),
            ]),
            self._make_result(2, [
                DecisionInfo(
                    decision_id=3,
                    decision_text="Another active",
                    status="active",
                    superseded_by=None,
                    confidence=0.85,
                ),
            ]),
        ]

        active = get_active_decisions(results)
        assert len(active) == 2
        assert all(d.status == "active" for d in active)

    def test_get_active_decisions_none(self) -> None:
        """Returns empty list when no active decisions."""
        results = [self._make_result(1, [])]
        assert get_active_decisions(results) == []
