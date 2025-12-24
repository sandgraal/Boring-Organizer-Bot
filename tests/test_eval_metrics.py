"""Tests for evaluation metrics."""

from __future__ import annotations

import pytest

from bob.eval.metrics import (
    average_precision,
    f1_at_k,
    mrr,
    precision_at_k,
    recall_at_k,
)


class TestRecallAtK:
    """Tests for recall@k metric."""

    def test_perfect_recall(self) -> None:
        """Test when all expected chunks are retrieved."""
        expected = [1, 2, 3]
        retrieved = [1, 2, 3, 4, 5]

        assert recall_at_k(expected, retrieved, k=5) == 1.0

    def test_partial_recall(self) -> None:
        """Test when some expected chunks are retrieved."""
        expected = [1, 2, 3]
        retrieved = [1, 4, 2, 5, 6]

        # 2 of 3 expected found
        assert recall_at_k(expected, retrieved, k=5) == pytest.approx(2 / 3)

    def test_zero_recall(self) -> None:
        """Test when no expected chunks are retrieved."""
        expected = [1, 2, 3]
        retrieved = [4, 5, 6, 7, 8]

        assert recall_at_k(expected, retrieved, k=5) == 0.0

    def test_empty_expected(self) -> None:
        """Test with empty expected set (trivially satisfied)."""
        expected: list[int] = []
        retrieved = [1, 2, 3]

        assert recall_at_k(expected, retrieved, k=5) == 1.0

    def test_k_limits_retrieved(self) -> None:
        """Test that k limits the retrieved set."""
        expected = [5]  # Only in position 5
        retrieved = [1, 2, 3, 4, 5]

        # k=3 should miss chunk 5
        assert recall_at_k(expected, retrieved, k=3) == 0.0
        # k=5 should find chunk 5
        assert recall_at_k(expected, retrieved, k=5) == 1.0


class TestPrecisionAtK:
    """Tests for precision@k metric."""

    def test_perfect_precision(self) -> None:
        """Test when all retrieved chunks are relevant."""
        expected = [1, 2, 3, 4, 5]
        retrieved = [1, 2, 3, 4, 5]

        assert precision_at_k(expected, retrieved, k=5) == 1.0

    def test_partial_precision(self) -> None:
        """Test when some retrieved chunks are relevant."""
        expected = [1, 2, 3]
        retrieved = [1, 4, 2, 5, 6]

        # 2 of 5 retrieved are relevant
        assert precision_at_k(expected, retrieved, k=5) == pytest.approx(2 / 5)

    def test_zero_precision(self) -> None:
        """Test when no retrieved chunks are relevant."""
        expected = [1, 2, 3]
        retrieved = [4, 5, 6, 7, 8]

        assert precision_at_k(expected, retrieved, k=5) == 0.0

    def test_k_zero(self) -> None:
        """Test with k=0 returns 0."""
        expected = [1, 2]
        retrieved = [1, 2]

        assert precision_at_k(expected, retrieved, k=0) == 0.0


class TestMRR:
    """Tests for Mean Reciprocal Rank metric."""

    def test_first_result_relevant(self) -> None:
        """Test when first result is relevant."""
        expected = [1, 2, 3]
        retrieved = [1, 4, 5, 6, 7]

        assert mrr(expected, retrieved) == 1.0

    def test_second_result_relevant(self) -> None:
        """Test when second result is relevant."""
        expected = [1, 2, 3]
        retrieved = [4, 1, 5, 6, 7]

        assert mrr(expected, retrieved) == 0.5

    def test_third_result_relevant(self) -> None:
        """Test when third result is relevant."""
        expected = [1, 2, 3]
        retrieved = [4, 5, 1, 6, 7]

        assert mrr(expected, retrieved) == pytest.approx(1 / 3)

    def test_no_relevant_results(self) -> None:
        """Test when no results are relevant."""
        expected = [1, 2, 3]
        retrieved = [4, 5, 6, 7, 8]

        assert mrr(expected, retrieved) == 0.0

    def test_empty_retrieved(self) -> None:
        """Test with empty retrieved list."""
        expected = [1, 2, 3]
        retrieved: list[int] = []

        assert mrr(expected, retrieved) == 0.0


class TestF1AtK:
    """Tests for F1@k metric."""

    def test_perfect_f1(self) -> None:
        """Test perfect precision and recall."""
        expected = [1, 2, 3, 4, 5]
        retrieved = [1, 2, 3, 4, 5]

        assert f1_at_k(expected, retrieved, k=5) == 1.0

    def test_zero_f1(self) -> None:
        """Test zero precision and recall."""
        expected = [1, 2, 3]
        retrieved = [4, 5, 6, 7, 8]

        assert f1_at_k(expected, retrieved, k=5) == 0.0

    def test_f1_harmonic_mean(self) -> None:
        """Test F1 is harmonic mean of precision and recall."""
        expected = [1, 2, 3]
        retrieved = [1, 4, 2, 5, 6]

        r = recall_at_k(expected, retrieved, k=5)  # 2/3
        p = precision_at_k(expected, retrieved, k=5)  # 2/5
        expected_f1 = 2 * (p * r) / (p + r)

        assert f1_at_k(expected, retrieved, k=5) == pytest.approx(expected_f1)


class TestAveragePrecision:
    """Tests for Average Precision metric."""

    def test_perfect_ap(self) -> None:
        """Test perfect ranking (all relevant first)."""
        expected = [1, 2, 3]
        retrieved = [1, 2, 3, 4, 5]

        # Precision at rank 1: 1/1 = 1.0
        # Precision at rank 2: 2/2 = 1.0
        # Precision at rank 3: 3/3 = 1.0
        # AP = (1 + 1 + 1) / 3 = 1.0
        assert average_precision(expected, retrieved) == 1.0

    def test_mixed_ap(self) -> None:
        """Test with mixed ranking."""
        expected = [1, 2, 3]
        retrieved = [1, 4, 2, 5, 3]

        # Precision at rank 1 (found 1): 1/1 = 1.0
        # Precision at rank 3 (found 2): 2/3 ≈ 0.67
        # Precision at rank 5 (found 3): 3/5 = 0.6
        # AP = (1 + 0.67 + 0.6) / 3 ≈ 0.756
        assert average_precision(expected, retrieved) == pytest.approx((1 + 2 / 3 + 3 / 5) / 3)

    def test_no_relevant(self) -> None:
        """Test with no relevant results."""
        expected = [1, 2, 3]
        retrieved = [4, 5, 6, 7, 8]

        assert average_precision(expected, retrieved) == 0.0

    def test_empty_expected(self) -> None:
        """Test with empty expected set."""
        expected: list[int] = []
        retrieved = [1, 2, 3]

        assert average_precision(expected, retrieved) == 1.0
