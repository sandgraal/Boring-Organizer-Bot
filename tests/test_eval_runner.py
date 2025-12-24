"""Tests for evaluation runner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from bob.eval.runner import (
    EvalResult,
    GoldenExample,
    compare_results,
    load_golden_set,
    run_evaluation,
)


class TestGoldenExample:
    """Tests for GoldenExample dataclass."""
    
    def test_create_example(self) -> None:
        """Test creating a golden example."""
        example = GoldenExample(
            id=1,
            question="How do I install?",
            expected_chunks=[1, 2, 3],
            difficulty="easy",
        )
        
        assert example.id == 1
        assert example.question == "How do I install?"
        assert example.expected_chunks == [1, 2, 3]
        assert example.difficulty == "easy"
    
    def test_default_values(self) -> None:
        """Test default values."""
        example = GoldenExample(
            id=1,
            question="Test",
            expected_chunks=[],
        )
        
        assert example.difficulty == "medium"
        assert example.category == "general"
        assert example.notes == ""
        assert example.expected_answer is None


class TestLoadGoldenSet:
    """Tests for loading golden datasets."""
    
    def test_load_valid_golden_set(self, tmp_path: Path) -> None:
        """Test loading a valid golden set."""
        golden_file = tmp_path / "golden.jsonl"
        golden_file.write_text(
            '{"id": 1, "question": "Q1", "expected_chunks": [1, 2]}\n'
            '{"id": 2, "question": "Q2", "expected_chunks": [3]}\n'
        )
        
        examples = load_golden_set(golden_file)
        
        assert len(examples) == 2
        assert examples[0].id == 1
        assert examples[0].question == "Q1"
        assert examples[1].expected_chunks == [3]
    
    def test_load_with_optional_fields(self, tmp_path: Path) -> None:
        """Test loading with optional fields."""
        golden_file = tmp_path / "golden.jsonl"
        golden_file.write_text(
            '{"id": 1, "question": "Q", "expected_chunks": [], '
            '"difficulty": "hard", "category": "api", "notes": "Test note"}\n'
        )
        
        examples = load_golden_set(golden_file)
        
        assert len(examples) == 1
        assert examples[0].difficulty == "hard"
        assert examples[0].category == "api"
        assert examples[0].notes == "Test note"
    
    def test_skip_empty_lines(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped."""
        golden_file = tmp_path / "golden.jsonl"
        golden_file.write_text(
            '{"id": 1, "question": "Q1", "expected_chunks": []}\n'
            '\n'
            '{"id": 2, "question": "Q2", "expected_chunks": []}\n'
        )
        
        examples = load_golden_set(golden_file)
        
        assert len(examples) == 2
    
    def test_file_not_found(self) -> None:
        """Test FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_golden_set(Path("/nonexistent/golden.jsonl"))


class TestEvalResult:
    """Tests for EvalResult dataclass."""
    
    def test_create_eval_result(self) -> None:
        """Test creating an eval result."""
        result = EvalResult(
            recall_mean=0.8,
            recall_std=0.1,
            precision_mean=0.6,
            precision_std=0.15,
            mrr_mean=0.7,
            mrr_std=0.12,
            num_queries=20,
            num_passed=18,
            num_failed=2,
            k=5,
            golden_path="test.jsonl",
        )
        
        assert result.recall_mean == 0.8
        assert result.num_queries == 20
        assert result.num_passed == 18
    
    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        result = EvalResult(
            recall_mean=0.8,
            recall_std=0.1,
            precision_mean=0.6,
            precision_std=0.15,
            mrr_mean=0.7,
            mrr_std=0.12,
            num_queries=20,
            num_passed=18,
            num_failed=2,
            k=5,
            golden_path="test.jsonl",
        )
        
        d = result.to_dict()
        
        assert d["recall_mean"] == 0.8
        assert d["k"] == 5
        assert "per_query" in d
    
    def test_to_json(self) -> None:
        """Test converting to JSON."""
        result = EvalResult(
            recall_mean=0.8,
            recall_std=0.1,
            precision_mean=0.6,
            precision_std=0.15,
            mrr_mean=0.7,
            mrr_std=0.12,
            num_queries=5,
            num_passed=4,
            num_failed=1,
            k=5,
            golden_path="test.jsonl",
        )
        
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["recall_mean"] == 0.8


class TestRunEvaluation:
    """Tests for run_evaluation function."""
    
    def test_run_with_custom_search(self, tmp_path: Path) -> None:
        """Test running evaluation with custom search function."""
        golden_file = tmp_path / "golden.jsonl"
        golden_file.write_text(
            '{"id": 1, "question": "Q1", "expected_chunks": [1, 2, 3]}\n'
            '{"id": 2, "question": "Q2", "expected_chunks": [4, 5]}\n'
        )
        
        # Perfect search function
        def perfect_search(query: str) -> list[int]:
            if "Q1" in query:
                return [1, 2, 3, 10, 11]
            return [4, 5, 10, 11, 12]
        
        result = run_evaluation(
            golden_path=golden_file,
            search_fn=perfect_search,
            k=5,
        )
        
        assert result.recall_mean == 1.0  # Found all expected
        assert result.num_queries == 2
    
    def test_run_with_imperfect_search(self, tmp_path: Path) -> None:
        """Test with search that misses some results."""
        golden_file = tmp_path / "golden.jsonl"
        golden_file.write_text(
            '{"id": 1, "question": "Q", "expected_chunks": [1, 2, 3]}\n'
        )
        
        # Only finds 2 of 3 expected
        def partial_search(query: str) -> list[int]:
            return [1, 10, 2, 11, 12]
        
        result = run_evaluation(
            golden_path=golden_file,
            search_fn=partial_search,
            k=5,
        )
        
        assert result.recall_mean == pytest.approx(2/3)
        assert result.mrr_mean == 1.0  # First result is relevant
    
    def test_empty_golden_raises(self, tmp_path: Path) -> None:
        """Test that empty golden set raises ValueError."""
        golden_file = tmp_path / "golden.jsonl"
        golden_file.write_text("")
        
        with pytest.raises(ValueError, match="empty"):
            run_evaluation(golden_path=golden_file, search_fn=lambda q: [])


class TestCompareResults:
    """Tests for compare_results function."""
    
    def test_improvement(self) -> None:
        """Test detecting improvement."""
        baseline = EvalResult(
            recall_mean=0.7,
            recall_std=0.1,
            precision_mean=0.5,
            precision_std=0.1,
            mrr_mean=0.6,
            mrr_std=0.1,
            num_queries=10,
            num_passed=8,
            num_failed=2,
            k=5,
            golden_path="test.jsonl",
        )
        
        current = EvalResult(
            recall_mean=0.8,  # Improved
            recall_std=0.1,
            precision_mean=0.6,  # Improved
            precision_std=0.1,
            mrr_mean=0.7,  # Improved
            mrr_std=0.1,
            num_queries=10,
            num_passed=9,
            num_failed=1,
            k=5,
            golden_path="test.jsonl",
        )
        
        comparison = compare_results(current, baseline)
        
        assert comparison["overall_passed"] is True
        assert comparison["recall_delta"] == pytest.approx(0.1)
    
    def test_regression(self) -> None:
        """Test detecting regression."""
        baseline = EvalResult(
            recall_mean=0.8,
            recall_std=0.1,
            precision_mean=0.6,
            precision_std=0.1,
            mrr_mean=0.7,
            mrr_std=0.1,
            num_queries=10,
            num_passed=8,
            num_failed=2,
            k=5,
            golden_path="test.jsonl",
        )
        
        current = EvalResult(
            recall_mean=0.6,  # Regressed
            recall_std=0.1,
            precision_mean=0.6,
            precision_std=0.1,
            mrr_mean=0.7,
            mrr_std=0.1,
            num_queries=10,
            num_passed=6,
            num_failed=4,
            k=5,
            golden_path="test.jsonl",
        )
        
        comparison = compare_results(current, baseline, tolerance=0.05)
        
        assert comparison["overall_passed"] is False
        assert comparison["recall_passed"] is False
        assert comparison["recall_delta"] == pytest.approx(-0.2)
    
    def test_within_tolerance(self) -> None:
        """Test changes within tolerance pass."""
        baseline = EvalResult(
            recall_mean=0.8,
            recall_std=0.1,
            precision_mean=0.6,
            precision_std=0.1,
            mrr_mean=0.7,
            mrr_std=0.1,
            num_queries=10,
            num_passed=8,
            num_failed=2,
            k=5,
            golden_path="test.jsonl",
        )
        
        current = EvalResult(
            recall_mean=0.77,  # -3%, within 5% tolerance
            recall_std=0.1,
            precision_mean=0.58,  # -2%
            precision_std=0.1,
            mrr_mean=0.68,  # -2%
            mrr_std=0.1,
            num_queries=10,
            num_passed=7,
            num_failed=3,
            k=5,
            golden_path="test.jsonl",
        )
        
        comparison = compare_results(current, baseline, tolerance=0.05)
        
        assert comparison["overall_passed"] is True
