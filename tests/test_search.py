"""Integration tests for the search pipeline."""

from __future__ import annotations

import os
from datetime import datetime
from importlib import import_module
from pathlib import Path

import pytest

from bob.db.database import Database


def get_search_module():
    """Get the actual search module (not the re-exported function)."""
    return import_module("bob.retrieval.search")


@pytest.fixture
def indexed_docs(temp_dir: Path, test_db: Database) -> tuple[Path, Database]:
    """Create and index a set of test documents."""
    from bob.index import index_paths
    from bob.index import indexer as indexer_module

    docs = temp_dir / "docs"
    docs.mkdir()

    # Document about Python
    (docs / "python.md").write_text("""# Python Programming

Python is a high-level programming language known for its readability.

## Features

- Dynamic typing
- Automatic memory management
- Extensive standard library

## Getting Started

Install Python from python.org and create a virtual environment.
""")

    # Document about databases
    (docs / "databases.md").write_text("""# Database Design

Learn about database design principles.

## Relational Databases

Use SQL for relational databases like PostgreSQL and MySQL.

## NoSQL Databases

MongoDB and Redis are popular NoSQL options.

## Best Practices

Always normalize your data and use proper indexing.
""")

    # Document about testing
    (docs / "testing.md").write_text("""# Software Testing

Testing ensures code quality and reliability.

## Unit Testing

Write unit tests for individual functions.

## Integration Testing

Test how components work together.

## Test Coverage

Aim for high test coverage but focus on critical paths.
""")

    # Additional document for another project
    other_docs = temp_dir / "other-project"
    other_docs.mkdir()
    (other_docs / "other-details.md").write_text(
        """# Other Project Details

This document lives in a different project and introduces a unique search term: multi project token.
"""
    )

    old_timestamp = datetime(2020, 1, 1).timestamp()
    new_timestamp = datetime(2024, 1, 1).timestamp()

    os.utime(docs / "python.md", (old_timestamp, old_timestamp))
    os.utime(docs / "databases.md", (new_timestamp, new_timestamp))
    os.utime(docs / "testing.md", (new_timestamp, new_timestamp))

    # Index the documents
    original_get_db = indexer_module.get_database
    indexer_module.get_database = lambda: test_db

    try:
        index_paths(paths=[docs], project="test-project", language="en")
        index_paths(paths=[other_docs], project="other-project", language="en")
    finally:
        indexer_module.get_database = original_get_db

    return docs, test_db


class TestSearch:
    """Tests for the search functionality."""

    def test_search_returns_results(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that search returns relevant results."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            results = search_mod.search(query="Python programming language", top_k=5)

            assert len(results) > 0
            # Most relevant result should be from python.md
            assert "python" in results[0].source_path.lower()
        finally:
            search_mod.get_database = original

    def test_search_with_project_filter(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that project filter works."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            # Search with correct project
            results = search_mod.search(query="database design", project="test-project", top_k=5)
            assert len(results) > 0

            # Search with non-existent project
            results_empty = search_mod.search(
                query="database design", project="nonexistent-project", top_k=5
            )
            assert len(results_empty) == 0
        finally:
            search_mod.get_database = original

    def test_search_with_multiple_projects(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that multiple project filters can be combined."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            # Search using multi-project filter should find the other-project doc
            results_multi = search_mod.search(
                query="multi project token",
                projects=["test-project", "other-project"],
                top_k=5,
            )
            assert len(results_multi) > 0
            assert any(r.project == "other-project" for r in results_multi)

            # Filtering by the first project only should not surface the other-project doc
            results_single = search_mod.search(
                query="multi project token",
                project="test-project",
                top_k=5,
            )
            assert all(r.project == "test-project" for r in results_single)
        finally:
            search_mod.get_database = original

    def test_search_result_structure(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that search results have correct structure."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            results = search_mod.search(query="unit testing", top_k=3)

            assert len(results) > 0
            result = results[0]

            # Check all required fields are present
            assert hasattr(result, "chunk_id")
            assert hasattr(result, "content")
            assert hasattr(result, "score")
            assert hasattr(result, "source_path")
            assert hasattr(result, "source_type")
            assert hasattr(result, "locator_type")
            assert hasattr(result, "locator_value")
            assert hasattr(result, "project")

            # Score should be between 0 and 1
            assert 0 <= result.score <= 1

            # Content should not be empty
            assert len(result.content) > 0
        finally:
            search_mod.get_database = original

    def test_search_respects_top_k(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that top_k limits results."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            results_1 = search_mod.search(query="programming", top_k=1)
            results_3 = search_mod.search(query="programming", top_k=3)

            assert len(results_1) <= 1
            assert len(results_3) <= 3
        finally:
            search_mod.get_database = original

    def test_search_filters_by_source_type(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that source type filter works."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            results = search_mod.search(
                query="database design",
                source_types=["markdown"],
                top_k=5,
            )
            assert len(results) > 0

            results_empty = search_mod.search(
                query="database design",
                source_types=["pdf"],
                top_k=5,
            )
            assert len(results_empty) == 0
        finally:
            search_mod.get_database = original

    def test_search_filters_by_language(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that language filter works."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            results = search_mod.search(
                query="database design",
                language="en",
                top_k=5,
            )
            assert len(results) > 0

            results_empty = search_mod.search(
                query="database design",
                language="fr",
                top_k=5,
            )
            assert len(results_empty) == 0
        finally:
            search_mod.get_database = original

    def test_search_filters_by_date_range(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that date range filters work."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        cutoff_after = datetime(2023, 1, 1)
        cutoff_before = datetime(2021, 1, 1)

        try:
            results_after = search_mod.search(
                query="database design",
                date_after=cutoff_after,
                top_k=5,
            )
            assert all(r.source_date and r.source_date >= cutoff_after for r in results_after)

            results_before = search_mod.search(
                query="python programming",
                date_before=cutoff_before,
                top_k=5,
            )
            assert all(r.source_date and r.source_date <= cutoff_before for r in results_before)
        finally:
            search_mod.get_database = original

    def test_search_no_results_gracefully(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test search returns empty list for no matches."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            # Search in non-existent project
            results = search_mod.search(
                query="anything", project="definitely-does-not-exist", top_k=5
            )

            # Should return empty list, not raise exception
            assert results == []
        finally:
            search_mod.get_database = original


class TestSearchRanking:
    """Tests for search result ranking."""

    def test_relevant_results_ranked_higher(self, indexed_docs: tuple[Path, Database]) -> None:
        """Test that more relevant results have higher scores."""
        search_mod = get_search_module()

        _, test_db = indexed_docs

        original = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            results = search_mod.search(query="SQL databases", top_k=5)

            if len(results) >= 2:
                # Results should be sorted by score (descending)
                for i in range(len(results) - 1):
                    assert results[i].score >= results[i + 1].score
        finally:
            search_mod.get_database = original


class TestEndToEndRetrieval:
    """End-to-end tests for the full retrieval flow."""

    def test_index_then_search(self, temp_dir: Path, test_db: Database) -> None:
        """Test complete flow: create doc -> index -> search."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        search_mod = get_search_module()

        # Create a specific document
        doc = temp_dir / "specific.md"
        doc.write_text("""# Unique Document

This document contains a very specific term: xylophone_zebra_123.

## Details

The xylophone_zebra_123 is a made-up identifier for testing search.
""")

        # Patch database for indexing
        original_indexer = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        # Patch database for search
        original_search = search_mod.get_database
        search_mod.get_database = lambda: test_db

        try:
            # Index the document
            stats = index_paths(paths=[doc], project="e2e-test", language="en")
            assert stats["documents"] == 1

            # Search for the specific term
            results = search_mod.search(query="xylophone_zebra_123", project="e2e-test", top_k=5)

            # Should find the document
            assert len(results) > 0
            assert "xylophone_zebra_123" in results[0].content
        finally:
            indexer_module.get_database = original_indexer
            search_mod.get_database = original_search
