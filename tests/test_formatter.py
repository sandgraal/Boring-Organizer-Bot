"""Tests for the answer formatting module."""

from datetime import datetime, timedelta

import pytest

from bob.answer.formatter import (
    DateConfidence,
    format_locator,
    get_date_confidence,
    is_outdated,
    format_answer_plain,
)
from bob.retrieval import SearchResult


class TestDateConfidence:
    """Tests for date confidence calculation."""

    def test_high_confidence_recent(self):
        recent = datetime.now() - timedelta(days=7)
        assert get_date_confidence(recent) == DateConfidence.HIGH

    def test_medium_confidence(self):
        older = datetime.now() - timedelta(days=60)
        assert get_date_confidence(older) == DateConfidence.MEDIUM

    def test_low_confidence_old(self):
        old = datetime.now() - timedelta(days=120)
        assert get_date_confidence(old) == DateConfidence.LOW

    def test_unknown_for_none(self):
        assert get_date_confidence(None) == DateConfidence.UNKNOWN


class TestIsOutdated:
    """Tests for outdated detection."""

    def test_recent_not_outdated(self):
        recent = datetime.now() - timedelta(days=30)
        assert not is_outdated(recent)

    def test_old_is_outdated(self):
        old = datetime.now() - timedelta(days=200)
        assert is_outdated(old)

    def test_none_not_outdated(self):
        assert not is_outdated(None)


class TestFormatLocator:
    """Tests for locator formatting."""

    def test_heading_locator(self):
        result = SearchResult(
            chunk_id=1,
            content="test",
            score=0.9,
            source_path="test.md",
            source_type="markdown",
            locator_type="heading",
            locator_value={"heading": "Introduction", "start_line": 1, "end_line": 10},
            project="test",
            source_date=None,
            git_repo=None,
            git_commit=None,
        )
        formatted = format_locator(result)
        assert "Introduction" in formatted
        assert "lines 1-10" in formatted

    def test_page_locator(self):
        result = SearchResult(
            chunk_id=1,
            content="test",
            score=0.9,
            source_path="test.pdf",
            source_type="pdf",
            locator_type="page",
            locator_value={"page": 5, "total_pages": 20},
            project="test",
            source_date=None,
            git_repo=None,
            git_commit=None,
        )
        formatted = format_locator(result)
        assert "page 5/20" in formatted

    def test_sheet_locator(self):
        result = SearchResult(
            chunk_id=1,
            content="test",
            score=0.9,
            source_path="test.xlsx",
            source_type="excel",
            locator_type="sheet",
            locator_value={"sheet_name": "Data", "row_count": 100},
            project="test",
            source_date=None,
            git_repo=None,
            git_commit=None,
        )
        formatted = format_locator(result)
        assert "Data" in formatted
        assert "100 rows" in formatted


class TestFormatAnswerPlain:
    """Tests for plain text answer formatting."""

    def test_includes_sources(self):
        results = [
            SearchResult(
                chunk_id=1,
                content="Test content here",
                score=0.95,
                source_path="docs/test.md",
                source_type="markdown",
                locator_type="heading",
                locator_value={"heading": "Test", "start_line": 1, "end_line": 5},
                project="test",
                source_date=datetime.now(),
                git_repo=None,
                git_commit=None,
            )
        ]
        formatted = format_answer_plain("test query", results)

        assert "docs/test.md" in formatted
        assert "Test content" in formatted
        assert "Sources:" in formatted

    def test_no_citation_no_claim(self):
        """Verify that answers are grounded in citations."""
        results = [
            SearchResult(
                chunk_id=1,
                content="Specific fact from source",
                score=0.9,
                source_path="source.md",
                source_type="markdown",
                locator_type="heading",
                locator_value={"heading": "Facts", "start_line": 1, "end_line": 3},
                project="test",
                source_date=datetime.now(),
                git_repo=None,
                git_commit=None,
            )
        ]
        formatted = format_answer_plain("query", results)

        # Must include the grounding statement
        assert "grounded in the cited sources" in formatted

    def test_empty_results(self):
        formatted = format_answer_plain("query", [])
        # Should still be valid output, just no sources
        assert "Sources:" in formatted
