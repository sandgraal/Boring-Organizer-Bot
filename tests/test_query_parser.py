"""Tests for query parser module."""

from __future__ import annotations

import pytest

from bob.retrieval.query_parser import ParsedQuery, filter_results_by_query, parse_query


class TestParseQuery:
    """Tests for query parsing."""

    def test_simple_query(self):
        """Simple query with no special syntax."""
        parsed = parse_query("how to configure logging")
        assert parsed.text == "how to configure logging"
        assert parsed.required_phrases == []
        assert parsed.excluded_terms == []
        assert parsed.project_filter is None
        assert not parsed.has_filters()

    def test_quoted_phrase(self):
        """Quoted phrases are extracted."""
        parsed = parse_query('"exact match" search')
        assert parsed.text == "search"
        assert parsed.required_phrases == ["exact match"]
        assert parsed.has_filters()

    def test_multiple_quoted_phrases(self):
        """Multiple quoted phrases are extracted."""
        parsed = parse_query('"first phrase" "second phrase"')
        assert parsed.required_phrases == ["first phrase", "second phrase"]
        assert parsed.text == "first phrase second phrase"  # Combined as search text

    def test_excluded_term(self):
        """Excluded terms are extracted."""
        parsed = parse_query("python programming -java")
        assert parsed.text == "python programming"
        assert parsed.excluded_terms == ["java"]
        assert parsed.has_filters()

    def test_multiple_excluded_terms(self):
        """Multiple exclusions are extracted."""
        parsed = parse_query("search query -exclude1 -exclude2")
        assert parsed.text == "search query"
        assert sorted(parsed.excluded_terms) == ["exclude1", "exclude2"]

    def test_project_filter(self):
        """Project filter is extracted."""
        parsed = parse_query("search query project:docs")
        assert parsed.text == "search query"
        assert parsed.project_filter == "docs"
        assert parsed.has_filters()

    def test_project_filter_case_insensitive(self):
        """Project filter works case-insensitively."""
        parsed = parse_query("search PROJECT:MyProject")
        assert parsed.project_filter == "MyProject"

    def test_decision_status_filter(self):
        """Decision status filter is extracted."""
        parsed = parse_query("decision:active review notes")
        assert parsed.text == "review notes"
        assert parsed.decision_status == "active"
        assert parsed.has_filters()

    def test_invalid_decision_status_ignored(self):
        """Invalid decision status is ignored."""
        parsed = parse_query("decision:unknown review notes")
        assert parsed.decision_status is None
        assert "decision:unknown" in parsed.text

    def test_combined_syntax(self):
        """All syntax elements work together."""
        parsed = parse_query('"exact phrase" other words -exclude project:myproj decision:superseded')
        assert parsed.text == "other words"
        assert parsed.required_phrases == ["exact phrase"]
        assert parsed.excluded_terms == ["exclude"]
        assert parsed.project_filter == "myproj"
        assert parsed.decision_status == "superseded"

    def test_empty_quoted_phrase_ignored(self):
        """Empty quotes don't add to required phrases."""
        parsed = parse_query('search "" query')
        assert parsed.required_phrases == []  # Empty phrase not added
        # Text includes the leftover, which is fine
        assert "search" in parsed.text
        assert "query" in parsed.text

    def test_preserves_original(self):
        """Original query is preserved."""
        original = '"test" query -exclude'
        parsed = parse_query(original)
        assert parsed.original == original

    def test_only_phrase_becomes_text(self):
        """If only phrase provided, it becomes search text."""
        parsed = parse_query('"only a phrase"')
        assert parsed.text == "only a phrase"
        assert parsed.required_phrases == ["only a phrase"]


class TestFilterResults:
    """Tests for result filtering."""

    @pytest.fixture
    def sample_results(self):
        """Sample results for filtering tests."""
        return [
            {"id": 1, "content": "Python is a programming language"},
            {"id": 2, "content": "Java is also a programming language"},
            {"id": 3, "content": "Python and Java can work together"},
            {"id": 4, "content": "JavaScript is different from Java"},
        ]

    def test_no_filters_returns_all(self, sample_results):
        """No filters returns all results."""
        parsed = ParsedQuery(text="programming")
        filtered = filter_results_by_query(sample_results, parsed)
        assert len(filtered) == 4

    def test_required_phrase_filters(self, sample_results):
        """Required phrases filter results."""
        parsed = ParsedQuery(
            text="programming",
            required_phrases=["Python"],
        )
        filtered = filter_results_by_query(sample_results, parsed)
        assert len(filtered) == 2
        assert all("python" in r["content"].lower() for r in filtered)

    def test_excluded_term_filters(self, sample_results):
        """Excluded terms filter results."""
        parsed = ParsedQuery(
            text="programming",
            excluded_terms=["java"],
        )
        filtered = filter_results_by_query(sample_results, parsed)
        assert len(filtered) == 1
        assert filtered[0]["id"] == 1  # Only pure Python result

    def test_combined_filters(self, sample_results):
        """Required phrases and exclusions work together."""
        parsed = ParsedQuery(
            text="language",
            required_phrases=["programming language"],
            excluded_terms=["java"],
        )
        filtered = filter_results_by_query(sample_results, parsed)
        assert len(filtered) == 1
        assert filtered[0]["id"] == 1

    def test_case_insensitive_matching(self, sample_results):
        """Filtering is case-insensitive."""
        parsed = ParsedQuery(
            text="test",
            required_phrases=["PYTHON"],
        )
        filtered = filter_results_by_query(sample_results, parsed)
        assert len(filtered) == 2  # Matches "Python" content

    def test_custom_content_key(self):
        """Custom content key is used."""
        results = [
            {"id": 1, "text": "Python content"},
            {"id": 2, "text": "Java content"},
        ]
        parsed = ParsedQuery(text="", required_phrases=["Python"])
        filtered = filter_results_by_query(results, parsed, content_key="text")
        assert len(filtered) == 1
        assert filtered[0]["id"] == 1

    def test_empty_results(self):
        """Empty results list returns empty."""
        parsed = ParsedQuery(text="test", required_phrases=["phrase"])
        filtered = filter_results_by_query([], parsed)
        assert filtered == []

    def test_all_filtered_out(self, sample_results):
        """All results can be filtered out."""
        parsed = ParsedQuery(
            text="test",
            required_phrases=["nonexistent phrase xyz"],
        )
        filtered = filter_results_by_query(sample_results, parsed)
        assert len(filtered) == 0
