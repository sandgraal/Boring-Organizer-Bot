"""Tests for the database module."""

from bob.db.database import compute_content_hash


class TestComputeContentHash:
    """Tests for content hashing."""

    def test_consistent_hash(self):
        content = "test content"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        hash1 = compute_content_hash("content a")
        hash2 = compute_content_hash("content b")
        assert hash1 != hash2

    def test_hash_format(self):
        hash_val = compute_content_hash("test")
        # SHA-256 produces 64 hex characters
        assert len(hash_val) == 64
        assert all(c in "0123456789abcdef" for c in hash_val)


class TestDatabaseOperations:
    """Tests for database operations."""

    def test_migrate_creates_tables(self, test_db):
        # After migration, tables should exist
        cursor = test_db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "documents" in tables
        assert "chunks" in tables
        assert "decisions" in tables
        assert "schema_migrations" in tables

    def test_insert_document(self, test_db):
        doc_id = test_db.insert_document(
            source_path="/test/file.md",
            source_type="markdown",
            project="test-project",
            content_hash="abc123",
            language="en",
        )
        assert doc_id > 0

    def test_get_document_by_path(self, test_db):
        test_db.insert_document(
            source_path="/test/file.md",
            source_type="markdown",
            project="test-project",
            content_hash="abc123",
        )

        doc = test_db.get_document_by_path("/test/file.md", "test-project")
        assert doc is not None
        assert doc["source_path"] == "/test/file.md"
        assert doc["project"] == "test-project"

    def test_get_nonexistent_document(self, test_db):
        doc = test_db.get_document_by_path("/nonexistent.md", "test")
        assert doc is None

    def test_insert_chunk(self, test_db):
        doc_id = test_db.insert_document(
            source_path="/test/file.md",
            source_type="markdown",
            project="test",
            content_hash="abc",
        )

        chunk_id = test_db.insert_chunk(
            document_id=doc_id,
            content="Test chunk content",
            locator_type="heading",
            locator_value={"heading": "Test", "start_line": 1, "end_line": 5},
            chunk_index=0,
            token_count=10,
        )
        assert chunk_id > 0

    def test_get_stats(self, test_db):
        # Insert some test data
        doc_id = test_db.insert_document(
            source_path="/test/file.md",
            source_type="markdown",
            project="test",
            content_hash="abc",
        )
        test_db.insert_chunk(
            document_id=doc_id,
            content="chunk",
            locator_type="heading",
            locator_value={},
            chunk_index=0,
        )

        stats = test_db.get_stats()
        assert stats["document_count"] == 1
        assert stats["chunk_count"] == 1
        assert "markdown" in stats["source_types"]

    def test_stats_filter_by_project(self, test_db):
        test_db.insert_document(
            source_path="/a.md",
            source_type="markdown",
            project="project-a",
            content_hash="a",
        )
        test_db.insert_document(
            source_path="/b.md",
            source_type="markdown",
            project="project-b",
            content_hash="b",
        )

        stats_a = test_db.get_stats(project="project-a")
        assert stats_a["document_count"] == 1

        stats_all = test_db.get_stats()
        assert stats_all["document_count"] == 2


class TestDecisionStorage:
    """Tests for decision storage operations."""

    def _create_test_chunk(self, test_db):
        """Helper to create a chunk for testing decisions."""
        doc_id = test_db.insert_document(
            source_path="/test/decisions.md",
            source_type="markdown",
            project="test-project",
            content_hash="decision123",
        )
        chunk_id = test_db.insert_chunk(
            document_id=doc_id,
            content="Decision: We will use Python.",
            locator_type="heading",
            locator_value={"heading": "Decisions"},
            chunk_index=0,
        )
        return chunk_id

    def test_save_and_get_decision(self, test_db):
        """Test saving and retrieving a decision."""
        from bob.extract.decisions import (
            ExtractedDecision,
            save_decision,
            get_decision,
        )

        chunk_id = self._create_test_chunk(test_db)

        decision = ExtractedDecision(
            chunk_id=chunk_id,
            decision_text="We will use Python for backend",
            context="After discussion, we decided...",
            decision_type="technology",
            decision_date=None,
            confidence=0.9,
            rejected_alternatives=["Java", "Go"],
        )

        decision_id = save_decision(decision)
        assert decision_id > 0

        stored = get_decision(decision_id)
        assert stored is not None
        assert stored.decision_text == "We will use Python for backend"
        assert stored.decision_type == "technology"
        assert stored.confidence == 0.9
        assert stored.status == "active"

    def test_get_decisions_with_filters(self, test_db):
        """Test filtering decisions by project and status."""
        from bob.extract.decisions import (
            ExtractedDecision,
            save_decision,
            get_decisions,
        )

        chunk_id = self._create_test_chunk(test_db)

        # Save multiple decisions
        for i in range(3):
            decision = ExtractedDecision(
                chunk_id=chunk_id,
                decision_text=f"Decision {i}",
                context="context",
                decision_type="technology",
                decision_date=None,
                confidence=0.8 + i * 0.05,
                rejected_alternatives=[],
            )
            save_decision(decision)

        decisions = get_decisions(project="test-project")
        assert len(decisions) == 3

        # Should be ordered by confidence (highest first)
        assert decisions[0].confidence >= decisions[1].confidence

    def test_supersede_decision(self, test_db):
        """Test marking a decision as superseded."""
        from bob.extract.decisions import (
            ExtractedDecision,
            save_decision,
            get_decision,
            supersede_decision,
        )

        chunk_id = self._create_test_chunk(test_db)

        old_decision = ExtractedDecision(
            chunk_id=chunk_id,
            decision_text="Use MySQL",
            context="original decision",
            decision_type="technology",
            decision_date=None,
            confidence=0.8,
            rejected_alternatives=[],
        )
        old_id = save_decision(old_decision)

        new_decision = ExtractedDecision(
            chunk_id=chunk_id,
            decision_text="Use PostgreSQL instead of MySQL",
            context="updated decision",
            decision_type="technology",
            decision_date=None,
            confidence=0.9,
            rejected_alternatives=["MySQL"],
        )
        new_id = save_decision(new_decision)

        result = supersede_decision(old_id, new_id)
        assert result is True

        old = get_decision(old_id)
        assert old is not None
        assert old.status == "superseded"
        assert old.superseded_by == new_id

    def test_clear_decisions(self, test_db):
        """Test clearing decisions."""
        from bob.extract.decisions import (
            ExtractedDecision,
            save_decision,
            get_decisions,
            clear_decisions,
        )

        chunk_id = self._create_test_chunk(test_db)

        decision = ExtractedDecision(
            chunk_id=chunk_id,
            decision_text="Test decision",
            context="context",
            decision_type=None,
            decision_date=None,
            confidence=0.7,
            rejected_alternatives=[],
        )
        save_decision(decision)

        decisions = get_decisions()
        assert len(decisions) > 0

        count = clear_decisions()
        assert count > 0

        decisions = get_decisions()
        assert len(decisions) == 0
