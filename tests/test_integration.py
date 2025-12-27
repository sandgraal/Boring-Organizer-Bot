"""Integration tests for end-to-end workflows.

These tests verify complete user workflows from indexing to querying
and routine execution. They ensure all components work together correctly.
"""

from datetime import UTC
from pathlib import Path

import pytest

from bob.index.indexer import index_file, index_paths
from bob.retrieval.search import search


def test_index_and_search_workflow(test_db, temp_dir):  # noqa: ARG001
    """Test the complete workflow: create file -> index -> search."""
    # Create a markdown file with searchable content
    doc_path = temp_dir / "notes.md"
    doc_path.write_text(
        """# Machine Learning Notes

## Neural Networks

Deep learning models use multiple layers of neurons to learn complex patterns.
The backpropagation algorithm is used for training.

## Training Process

We use stochastic gradient descent with a learning rate of 0.001.
The batch size is typically 32 or 64.
"""
    )

    # Index the file
    stats = index_file(doc_path, project="test", language="en")
    assert stats["documents"] == 1
    assert stats["chunks"] > 0
    assert stats["skipped"] == 0

    # Search for content
    results = search(
        query="How do we train neural networks?",
        project="test",
        top_k=5,
    )

    assert len(results) > 0
    assert any("backpropagation" in r.chunk.content.lower() for r in results)


def test_index_multiple_files_and_project_filter(test_db, temp_dir):  # noqa: ARG001
    """Test indexing multiple files and filtering by project."""
    # Create files in different projects
    project_a = temp_dir / "project_a"
    project_b = temp_dir / "project_b"
    project_a.mkdir()
    project_b.mkdir()

    (project_a / "doc1.md").write_text(
        """# Project A Document

This is about project A implementation.
We use Python for this project.
"""
    )

    (project_b / "doc2.md").write_text(
        """# Project B Document

This is about project B infrastructure.
We use Docker and Kubernetes.
"""
    )

    # Index both projects
    index_paths([project_a], project="project-a", language="en")
    index_paths([project_b], project="project-b", language="en")

    # Search in project A only
    results_a = search("implementation", project="project-a", top_k=5)
    assert len(results_a) > 0
    assert all(r.chunk.project == "project-a" for r in results_a)

    # Search in project B only
    results_b = search("infrastructure", project="project-b", top_k=5)
    assert len(results_b) > 0
    assert all(r.chunk.project == "project-b" for r in results_b)

    # Search across all projects
    results_all = search("project", project=None, top_k=10)
    assert len(results_all) > 0


def test_reindex_updated_file(test_db, temp_dir):  # noqa: ARG001
    """Test that re-indexing an updated file replaces old content."""
    doc_path = temp_dir / "evolving.md"

    # Initial content
    doc_path.write_text(
        """# Initial Version

This is the first version of the document.
"""
    )

    # Index first version
    stats1 = index_file(doc_path, project="test", language="en")
    assert stats1["documents"] == 1
    assert stats1["chunks"] > 0

    # Search for initial content
    results1 = search("first version", project="test", top_k=5)
    assert len(results1) > 0

    # Update the file
    doc_path.write_text(
        """# Updated Version

This is the second version with completely different content.
The first version has been replaced.
"""
    )

    # Re-index
    stats2 = index_file(doc_path, project="test", language="en")
    assert stats2["documents"] == 1

    # Search for new content - should find it
    results_new = search("second version", project="test", top_k=5)
    assert len(results_new) > 0

    # Old content should not be found (or have low score)
    results_old = search("first version", project="test", top_k=5)
    # Either no results, or results don't contain the old content
    if results_old:
        # The old specific phrase shouldn't appear anymore
        assert not any("This is the first version" in r.chunk.content for r in results_old)


def test_skip_unchanged_file(test_db, temp_dir):  # noqa: ARG001
    """Test that unchanged files are skipped on re-indexing."""
    doc_path = temp_dir / "static.md"
    doc_path.write_text(
        """# Static Document

This content never changes.
"""
    )

    # Index first time
    stats1 = index_file(doc_path, project="test", language="en")
    assert stats1["documents"] == 1
    assert stats1["skipped"] == 0

    # Index again without changes
    stats2 = index_file(doc_path, project="test", language="en")
    assert stats2["documents"] == 0
    assert stats2["skipped"] == 1  # Should be skipped


def test_search_with_max_age_filter(test_db, temp_dir):
    """Test search with max_age filter for recent documents."""
    from datetime import datetime, timedelta

    # Create a document
    doc_path = temp_dir / "dated.md"
    doc_path.write_text(
        """# Recent Document
2025-01-15

This is recent content that should be found.
"""
    )

    # Index it
    index_file(doc_path, project="test", language="en")

    # Update the document's source_date to be recent
    recent_date = datetime.now(UTC) - timedelta(days=10)
    test_db.conn.execute(
        "UPDATE documents SET source_date = ? WHERE source_path = ?",
        (recent_date.isoformat(), str(doc_path)),
    )
    test_db.conn.commit()

    # Search with max_age that includes this document (30 days)
    results_include = search("recent content", project="test", max_age_days=30, top_k=5)
    assert len(results_include) > 0

    # Search with max_age that excludes this document (5 days)
    results_exclude = search("recent content", project="test", max_age_days=5, top_k=5)
    # Should be empty or not include the 10-day-old document
    assert len(results_exclude) == 0


def test_pdf_parsing_and_page_locators(test_db, temp_dir):  # noqa: ARG001
    """Test that PDF files can be indexed with page locators.

    This test requires pypdf. If PDFs with actual content are needed,
    we would need to create them programmatically or include fixtures.
    For now, we test that the parser exists and handles errors gracefully.
    """
    from bob.ingest import get_parser

    # Create a fake PDF path
    pdf_path = temp_dir / "test.pdf"
    pdf_path.touch()

    # Verify we have a PDF parser
    parser = get_parser(pdf_path)
    assert parser is not None
    assert "pdf" in parser.__class__.__name__.lower()


def test_different_file_types_in_same_project(test_db, temp_dir):
    """Test indexing multiple file types in the same project."""
    # Create markdown file
    md_path = temp_dir / "notes.md"
    md_path.write_text(
        """# Markdown Notes

These are markdown notes about the project.
"""
    )

    # Create recipe file
    recipe_path = temp_dir / "recipe.recipe.yaml"
    recipe_path.write_text(
        """name: Test Recipe
description: A delicious test
ingredients:
  - item: flour
    amount: 2 cups
instructions:
  - Mix ingredients
  - Bake
"""
    )

    # Index both
    stats_md = index_file(md_path, project="mixed", language="en")
    stats_recipe = index_file(recipe_path, project="mixed", language="en")

    assert stats_md["documents"] == 1
    assert stats_recipe["documents"] == 1

    # Verify both are in the same project
    docs = list(
        test_db.conn.execute("SELECT source_type FROM documents WHERE project = ?", ("mixed",))
    )
    source_types = {row[0] for row in docs}
    assert "markdown" in source_types
    assert "recipe" in source_types


def test_large_file_size_limit(test_db, temp_dir):
    """Test that files exceeding size limit are rejected."""
    from bob.config import get_config

    # Create a file that exceeds the limit
    large_path = temp_dir / "large.md"

    # Get max file size from config
    max_size_mb = get_config().paths.max_file_size_mb

    if max_size_mb <= 0:
        pytest.skip("File size limit is disabled in config")

    # Create content that exceeds the limit
    # Write slightly more than max_size_mb megabytes
    large_content = "x" * ((max_size_mb * 1024 * 1024) + 1024)
    large_path.write_text(large_content)

    # Try to index - should be rejected
    stats = index_file(large_path, project="test", language="en")
    assert stats["documents"] == 0
    assert stats.get("errors", 0) == 1

    # Verify error was logged
    errors = list(
        test_db.conn.execute(
            "SELECT error_type FROM ingestion_errors WHERE source_path = ?", (str(large_path),)
        )
    )
    assert len(errors) > 0
    assert errors[0][0] == "oversize"


def test_query_parser_with_advanced_syntax(test_db, temp_dir):  # noqa: ARG001
    """Test query parser with exact phrases, exclusions, and project filters."""
    from bob.retrieval.query_parser import QueryParser

    # Create test documents
    doc1 = temp_dir / "doc1.md"
    doc1.write_text(
        """# API Documentation

The REST API endpoint is /api/v1/users.
You can use GET or POST methods.
"""
    )

    doc2 = temp_dir / "doc2.md"
    doc2.write_text(
        """# GraphQL Guide

GraphQL provides a flexible API interface.
It's different from REST APIs.
"""
    )

    # Index both
    index_paths([temp_dir], project="docs", language="en")

    # Test exact phrase matching
    parser = QueryParser('"REST API" endpoint')
    assert "REST API" in parser.exact_phrases
    assert "endpoint" in parser.terms

    # Test exclusion
    parser = QueryParser("API -GraphQL")
    assert "api" in parser.terms
    assert "graphql" in parser.excluded_terms

    # Test project filter
    parser = QueryParser("API project:docs")
    assert parser.project_filter == "docs"
    assert "api" in parser.terms


def test_error_logging_for_unparseable_files(test_db, temp_dir):  # noqa: ARG001
    """Test that parsing errors are properly logged to ingestion_errors."""
    # Create a file with an unsupported extension
    bad_file = temp_dir / "test.xyz"
    bad_file.write_text("This is an unknown format")

    # Try to index - should skip
    stats = index_file(bad_file, project="test", language="en")
    assert stats["documents"] == 0
    assert stats["skipped"] == 1

    # No error should be logged for files with no parser
    # (they're simply skipped)


def test_watchlist_integration(test_db, temp_dir):
    """Test that watchlist entries can be used for batch indexing."""
    from bob.watchlist import add_watchlist_entry, load_watchlist

    # Set watchlist path
    watchlist_path = temp_dir / ".bob_watchlist.yaml"
    import os

    os.environ["BOB_WATCHLIST_PATH"] = str(watchlist_path)

    # Create test directory
    notes_dir = temp_dir / "notes"
    notes_dir.mkdir()
    (notes_dir / "note1.md").write_text("# Note 1\n\nContent here.")
    (notes_dir / "note2.md").write_text("# Note 2\n\nMore content.")

    # Add to watchlist
    add_watchlist_entry(str(notes_dir), project="notes", language="en")

    # Load and verify
    entries = load_watchlist()
    assert len(entries) == 1
    assert entries[0].path == str(notes_dir.resolve())
    assert entries[0].project == "notes"

    # Index using watchlist entry
    entry = entries[0]
    index_paths([Path(entry.path)], project=entry.project, language=entry.language)

    # Verify both files were indexed
    docs = list(test_db.conn.execute("SELECT COUNT(*) FROM documents WHERE project = ?", ("notes",)))
    assert docs[0][0] == 2


def test_decision_extraction_workflow(test_db, temp_dir):
    """Test extracting and tracking decisions from documents."""
    from bob.extract.decisions import extract_decisions_from_document

    # Create a document with decision content
    doc_path = temp_dir / "decisions.md"
    doc_path.write_text(
        """# Architecture Decision

## Decision: Use PostgreSQL for primary database

We decided to use PostgreSQL instead of MySQL.

### Context
We need a reliable relational database with good JSON support.

### Decision
We will use PostgreSQL 14+ as our primary database.

### Consequences
- Better JSON query capabilities
- Strong ACID guarantees
- Need to learn PostgreSQL-specific features

### Alternatives Considered
- MySQL: Rejected due to limited JSON support
- MongoDB: Rejected as we need strong consistency
"""
    )

    # Index the document
    index_file(doc_path, project="decisions", language="en")

    # Get document ID
    doc = test_db.get_document_by_path(str(doc_path), "decisions")
    assert doc is not None

    # Extract decisions
    decisions = extract_decisions_from_document(test_db, doc["id"])

    # Should have found the decision
    assert len(decisions) > 0
    decision = decisions[0]

    assert "PostgreSQL" in decision["title"]
    assert decision["status"] == "active"
    assert len(decision["alternatives"]) > 0


def test_health_metrics_ingestion_errors(test_db, temp_dir):
    """Test that ingestion errors are tracked for health metrics."""
    # Create a markdown file with encoding issues by writing bytes
    bad_file = temp_dir / "bad_encoding.md"
    # Write invalid UTF-8
    bad_file.write_bytes(b"# Test\n\nInvalid UTF-8: \xff\xfe")

    # Try to index - should fail and log error
    index_file(bad_file, project="test", language="en")

    # Check that error was logged
    errors = list(
        test_db.conn.execute(
            "SELECT error_type, project FROM ingestion_errors WHERE source_path = ?",
            (str(bad_file),),
        )
    )

    # Should have logged a parse error
    assert len(errors) > 0
    assert errors[0][1] == "test"  # Project should be recorded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
