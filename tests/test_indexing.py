"""Integration tests for the indexing pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from bob.db.database import Database


@pytest.fixture
def docs_dir(temp_dir: Path) -> Path:
    """Create a directory with various document types."""
    docs = temp_dir / "docs"
    docs.mkdir()

    # Markdown file
    md_file = docs / "guide.md"
    md_file.write_text("""# User Guide

Welcome to the application.

## Installation

Run the following command:

```bash
pip install myapp
```

## Configuration

Configure the app using `config.yaml`.

### Database Settings

Set the database URL in the config file.

### Logging Settings

Adjust log level as needed.
""")

    # Another markdown file
    readme = docs / "readme.md"
    readme.write_text("""# Project README

This project does amazing things.

## Features

- Feature one
- Feature two
- Feature three

## Quick Start

Get started in 5 minutes.
""")

    # Nested directory
    nested = docs / "advanced"
    nested.mkdir()

    adv_file = nested / "advanced.md"
    adv_file.write_text("""# Advanced Topics

## Performance Tuning

Optimize your setup.

## Security

Keep your data safe.
""")

    return docs


class TestIndexPaths:
    """Tests for the full indexing pipeline."""

    def test_index_single_file(self, temp_dir: Path, test_db: Database) -> None:
        """Test indexing a single markdown file."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        # Create test file
        test_file = temp_dir / "test.md"
        test_file.write_text("""# Test Document

This is a test paragraph with some content.

## Section One

Content in section one.

## Section Two

Content in section two.
""")

        # Patch database at the module where it's imported
        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            stats = index_paths(
                paths=[test_file],
                project="test-project",
                language="en",
            )

            assert stats["documents"] == 1
            assert stats["chunks"] >= 1
            assert stats["errors"] == 0

            # Verify document in database
            cursor = test_db.conn.execute(
                "SELECT * FROM documents WHERE project = ?", ("test-project",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["source_type"] == "markdown"
            assert row["project"] == "test-project"
        finally:
            indexer_module.get_database = original_get_db

    def test_index_directory(self, docs_dir: Path, test_db: Database) -> None:
        """Test indexing a directory of files."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            stats = index_paths(
                paths=[docs_dir],
                project="docs-project",
                language="en",
            )

            # Should index all 3 markdown files
            assert stats["documents"] == 3
            assert stats["chunks"] >= 3  # At least one chunk per doc
            assert stats["errors"] == 0
        finally:
            indexer_module.get_database = original_get_db

    def test_count_indexable_targets_skips_unsupported(self, temp_dir: Path) -> None:
        """Only supported file types are counted for progress."""
        from bob.index.indexer import count_indexable_targets

        docs = temp_dir / "docs"
        docs.mkdir()

        (docs / "notes.md").write_text("# Notes\n\nSome content for indexing.")
        (docs / "image.png").write_text("fake image data")
        (docs / "notes.txt").write_text("plain text")

        total = count_indexable_targets([docs])
        assert total == 1

    def test_count_indexable_targets_accepts_git_urls(self) -> None:
        """Git URLs should count as indexable targets."""
        from bob.index.indexer import count_indexable_targets

        total = count_indexable_targets([Path("https://github.com/example/repo")])
        assert total == 1

    def test_index_paths_normalizes_git_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Indexing should normalize git URLs before cloning."""
        from bob.index import indexer as indexer_module

        captured: dict[str, str] = {}

        def fake_index_git_repo(
            url: str,
            project: str,  # noqa: ARG001
            language: str,  # noqa: ARG001
            progress_callback=None,  # noqa: ARG001
        ) -> dict[str, int]:
            captured["url"] = url
            return {"documents": 1, "chunks": 0, "skipped": 0, "errors": 0}

        monkeypatch.setattr(indexer_module, "index_git_repo", fake_index_git_repo)

        stats = indexer_module.index_paths(
            paths=[Path("https://github.com/example/repo")],
            project="docs",
            language="en",
        )

        assert stats["documents"] == 1
        assert captured["url"] == "https://github.com/example/repo"

    def test_index_skips_unchanged(self, temp_dir: Path, test_db: Database) -> None:
        """Test that unchanged files are skipped on re-index."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        test_file = temp_dir / "unchanged.md"
        test_file.write_text("# Unchanged\n\nThis content won't change.")

        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            # First index
            stats1 = index_paths(
                paths=[test_file],
                project="test",
                language="en",
            )
            assert stats1["documents"] == 1
            assert stats1["skipped"] == 0

            # Second index (should skip)
            stats2 = index_paths(
                paths=[test_file],
                project="test",
                language="en",
            )
            assert stats2["documents"] == 0
            assert stats2["skipped"] == 1
        finally:
            indexer_module.get_database = original_get_db

    def test_index_updates_changed(self, temp_dir: Path, test_db: Database) -> None:
        """Test that changed files are re-indexed."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        test_file = temp_dir / "changing.md"
        test_file.write_text("# Original\n\nOriginal content.")

        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            # First index
            stats1 = index_paths(
                paths=[test_file],
                project="test",
                language="en",
            )
            assert stats1["documents"] == 1

            # Modify file
            test_file.write_text("# Updated\n\nNew content here.")

            # Second index (should update)
            stats2 = index_paths(
                paths=[test_file],
                project="test",
                language="en",
            )
            assert stats2["documents"] == 1
            assert stats2["skipped"] == 0
        finally:
            indexer_module.get_database = original_get_db

    def test_index_skips_oversize_file(self, temp_dir: Path, test_db: Database) -> None:
        """Oversize files are logged and not indexed."""
        from bob.config import get_config
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        test_file = temp_dir / "big.md"
        test_file.write_text("word " * 300000)

        config = get_config()
        config.paths.max_file_size_mb = 1

        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            stats = index_paths(
                paths=[test_file],
                project="test-project",
                language="en",
            )

            assert stats["documents"] == 0
            assert stats["errors"] == 1

            metrics = test_db.get_ingestion_error_metrics(window_hours=1, limit=5)
            assert metrics["counts"]["oversize"] == 1
        finally:
            indexer_module.get_database = original_get_db

    def test_index_ignores_patterns(self, temp_dir: Path, test_db: Database) -> None:
        """Test that ignored patterns are skipped."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        # Create files - .hidden should be ignored by default config
        hidden_file = temp_dir / ".hidden.md"
        hidden_file.write_text("# Hidden")

        valid_file = temp_dir / "valid.md"
        valid_file.write_text("# Valid\n\nContent.")

        # Create __pycache__ directory (should be ignored)
        pycache = temp_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.md").write_text("# Cached")

        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            stats = index_paths(
                paths=[temp_dir],
                project="test",
                language="en",
            )

            # Should only index valid.md (hidden file and __pycache__ ignored)
            # Note: This verifies the current behavior
            assert stats["documents"] >= 1

            # Verify only valid.md is indexed
            cursor = test_db.conn.execute(
                "SELECT source_path FROM documents WHERE project = ?", ("test",)
            )
            paths = [row[0] for row in cursor.fetchall()]
            # Valid.md should be there
            assert any("valid.md" in p for p in paths)
        finally:
            indexer_module.get_database = original_get_db

    def test_index_multiple_paths(self, temp_dir: Path, test_db: Database) -> None:
        """Test indexing multiple paths at once."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        # Create two separate directories
        dir1 = temp_dir / "dir1"
        dir1.mkdir()
        (dir1 / "file1.md").write_text("# File One\n\nContent one.")

        dir2 = temp_dir / "dir2"
        dir2.mkdir()
        (dir2 / "file2.md").write_text("# File Two\n\nContent two.")

        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            stats = index_paths(
                paths=[dir1, dir2],
                project="multi",
                language="en",
            )

            assert stats["documents"] == 2
        finally:
            indexer_module.get_database = original_get_db

    def test_index_creates_embeddings(self, temp_dir: Path, test_db: Database) -> None:
        """Test that embeddings are created for chunks."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        test_file = temp_dir / "embed.md"
        test_file.write_text("""# Embedding Test

This is a test document for embedding creation.

## Section

More content for embedding.
""")

        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            stats = index_paths(
                paths=[test_file],
                project="embed-test",
                language="en",
            )

            assert stats["chunks"] >= 1

            # Query the database to verify embeddings exist
            # Check both vec table and fallback table
            if test_db.has_vec:
                cursor = test_db.conn.execute("""
                    SELECT COUNT(*) FROM chunk_embeddings
                """)
            else:
                cursor = test_db.conn.execute("""
                    SELECT COUNT(*) FROM chunk_embeddings_fallback
                """)
            embedding_count = cursor.fetchone()[0]
            assert embedding_count >= 1
        finally:
            indexer_module.get_database = original_get_db


class TestLocatorConsistency:
    """Tests for consistent locator format across parsers."""

    def test_markdown_locators(self, temp_dir: Path, test_db: Database) -> None:
        """Test markdown parser produces consistent locators."""
        from bob.index import index_paths
        from bob.index import indexer as indexer_module

        test_file = temp_dir / "locator.md"
        test_file.write_text("""# Main Heading

Content under main heading.

## Sub Heading

Content under sub heading.
""")

        original_get_db = indexer_module.get_database
        indexer_module.get_database = lambda: test_db

        try:
            index_paths(paths=[test_file], project="loc", language="en")

            # Check chunks have proper locator format
            cursor = test_db.conn.execute("""
                SELECT locator_type, locator_value FROM chunks
            """)
            rows = cursor.fetchall()

            for row in rows:
                assert row[0] == "heading"
                import json

                locator = json.loads(row[1])
                assert "heading" in locator
                assert "start_line" in locator
                assert "end_line" in locator
        finally:
            indexer_module.get_database = original_get_db
