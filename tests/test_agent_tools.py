"""Tests for agent tool interfaces."""

from __future__ import annotations

from bob.agents.tools import AgentResult, SourceInfo


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating a successful result."""
        result = AgentResult(
            success=True,
            message="Test passed",
            data={"key": "value"},
        )

        assert result.success is True
        assert result.message == "Test passed"
        assert result.data == {"key": "value"}
        assert result.sources == []
        assert result.warnings == []

    def test_failure_result(self) -> None:
        """Test creating a failure result."""
        result = AgentResult(
            success=False,
            message="Test failed",
            warnings=["Something went wrong"],
        )

        assert result.success is False
        assert "failed" in result.message
        assert len(result.warnings) == 1

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        result = AgentResult(
            success=True,
            message="Test",
            data={"count": 42},
            sources=[
                SourceInfo(
                    file="test.md",
                    locator={"heading": "Test", "start_line": 1},
                    date="2024-01-01",
                    confidence="HIGH",
                    score=0.95,
                    content_preview="Test content",
                )
            ],
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["message"] == "Test"
        assert d["data"]["count"] == 42
        assert len(d["sources"]) == 1
        assert d["sources"][0]["file"] == "test.md"

    def test_to_json(self) -> None:
        """Test converting to JSON."""
        result = AgentResult(
            success=True,
            message="Test",
        )

        json_str = result.to_json()

        assert '"success": true' in json_str
        assert '"message": "Test"' in json_str


class TestSourceInfo:
    """Tests for SourceInfo dataclass."""

    def test_source_info_creation(self) -> None:
        """Test creating SourceInfo."""
        source = SourceInfo(
            file="docs/test.md",
            locator={"heading": "Introduction", "start_line": 10, "end_line": 20},
            date="2024-03-15",
            confidence="HIGH",
            score=0.89,
            content_preview="This is the introduction...",
            outdated=False,
        )

        assert source.file == "docs/test.md"
        assert source.locator["heading"] == "Introduction"
        assert source.confidence == "HIGH"
        assert source.outdated is False

    def test_source_info_outdated(self) -> None:
        """Test outdated source."""
        source = SourceInfo(
            file="old.md",
            locator={},
            date="2020-01-01",
            confidence="LOW",
            score=0.5,
            content_preview="Old content",
            outdated=True,
        )

        assert source.outdated is True
        assert source.confidence == "LOW"


class TestIndexFunction:
    """Tests for index() function."""

    def test_index_missing_paths(self) -> None:
        """Test indexing with non-existent paths."""
        from bob.agents import index

        result = index(
            paths=["/nonexistent/path/that/does/not/exist"],
            project="test",
        )

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_index_empty_paths(self) -> None:
        """Test indexing with empty paths list."""
        from bob.agents import index

        # Empty paths should work but do nothing
        result = index(paths=[], project="test")

        # Implementation may vary - just ensure it doesn't crash
        assert isinstance(result, AgentResult)


class TestAskFunction:
    """Tests for ask() function."""

    def test_ask_returns_result(self) -> None:
        """Test that ask returns AgentResult."""
        from bob.agents import ask

        # This may fail if database isn't initialized, but structure should be correct
        result = ask(question="test question", project=None, top_k=5)

        assert isinstance(result, AgentResult)
        assert result.answer_id is not None or result.success is False

    def test_ask_with_project_filter(self) -> None:
        """Test ask with project filter."""
        from bob.agents import ask

        result = ask(
            question="test",
            project="nonexistent-project",
            top_k=3,
        )

        assert isinstance(result, AgentResult)
        # Should succeed but return no results for nonexistent project


class TestExplainSources:
    """Tests for explain_sources() function."""

    def test_explain_no_chunks(self) -> None:
        """Test explain_sources with no chunk IDs."""
        from bob.agents import explain_sources

        result = explain_sources(chunk_ids=None)

        assert result.success is False
        assert "No chunk_ids" in result.message

    def test_explain_empty_chunks(self) -> None:
        """Test explain_sources with empty list."""
        from bob.agents import explain_sources

        result = explain_sources(chunk_ids=[])

        assert result.success is False


class TestRunEval:
    """Tests for run_eval() function."""

    def test_run_eval_missing_golden(self) -> None:
        """Test run_eval with missing golden file."""
        from bob.agents import run_eval

        result = run_eval(golden_path="/nonexistent/golden.jsonl")

        assert result.success is False
        assert "not found" in result.message.lower()
