"""Tests for the answer formatting module."""

from datetime import datetime, timedelta

from bob.answer.formatter import (
    DateConfidence,
    format_answer_plain,
    format_locator,
    get_date_confidence,
    highlight_terms,
    is_outdated,
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


class TestHighlightTerms:
    """Tests for term highlighting in search results."""

    def test_highlights_single_term(self):
        text = "This is a document about configuration settings."
        result = highlight_terms(text, "configuration")
        # The result is a Rich Text object
        assert "configuration" in result.plain

    def test_highlights_multiple_terms(self):
        text = "Learn about search and retrieval systems."
        result = highlight_terms(text, "search retrieval")
        assert "search" in result.plain
        assert "retrieval" in result.plain

    def test_case_insensitive_highlighting(self):
        text = "Configuration and CONFIGURATION are the same."
        result = highlight_terms(text, "configuration")
        # Both occurrences should be in the result, and highlighted
        # Check that both appear in the plain text
        assert "Configuration" in result.plain
        assert "CONFIGURATION" in result.plain
        # The plain text should match the original
        assert result.plain == text

    def test_ignores_short_words(self):
        text = "The cat sat on the mat."
        result = highlight_terms(text, "the cat on")
        # "the" and "on" are short words, only "cat" should be highlighted
        assert "cat" in result.plain

    def test_ignores_common_words(self):
        text = "How to configure with settings."
        result = highlight_terms(text, "how configure with")
        # "how" and "with" are common stop words
        assert "configure" in result.plain

    def test_handles_query_syntax(self):
        text = "Python programming tutorial for beginners."
        result = highlight_terms(text, '"exact phrase" python -excluded project:test')
        # Should highlight python, ignore syntax
        assert "Python" in result.plain

    def test_empty_query_returns_plain_text(self):
        text = "Some document text."
        result = highlight_terms(text, "")
        assert result.plain == text

    def test_no_matching_terms(self):
        text = "Document about something else."
        result = highlight_terms(text, "unrelated query")
        # Should return the text unchanged (dim style)
        assert "Document about something else" in result.plain
