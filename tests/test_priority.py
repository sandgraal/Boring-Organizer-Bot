"""Tests for bob.health.priority module.

These tests verify the priority bucket calculation functions used by the
Coach Mode suggestion engine and Fix Queue task builder.
"""

from __future__ import annotations

from bob.health.priority import (
    invert_priority,
    priority_from_count,
    priority_from_ratio,
    staleness_value,
)


class TestInvertPriority:
    """Tests for invert_priority function."""

    def test_invert_min_to_max(self) -> None:
        """Lowest bucket (1) inverts to highest priority (5)."""
        assert invert_priority(1) == 5

    def test_invert_max_to_min(self) -> None:
        """Highest bucket (5) inverts to lowest priority (1)."""
        assert invert_priority(5) == 1

    def test_invert_middle(self) -> None:
        """Middle bucket (3) stays at middle priority (3)."""
        assert invert_priority(3) == 3

    def test_invert_custom_range(self) -> None:
        """Custom min/max values work correctly."""
        # With min=2, max=6: invert(2) = 6+2-2 = 6
        assert invert_priority(2, min_value=2, max_value=6) == 6
        # invert(6) = 6+2-6 = 2
        assert invert_priority(6, min_value=2, max_value=6) == 2


class TestPriorityFromRatio:
    """Tests for priority_from_ratio function."""

    def test_max_ratio_highest_priority(self) -> None:
        """100% ratio yields highest priority (1)."""
        assert priority_from_ratio(1.0) == 1

    def test_zero_ratio_lowest_priority(self) -> None:
        """0% ratio yields lowest priority (5)."""
        assert priority_from_ratio(0.0) == 5

    def test_mid_ratio_high_priority(self) -> None:
        """50% ratio yields high priority (1-2) - high error rate is severe."""
        # With scale=10, 0.5 * 10 = 5, which maps to priority 1
        result = priority_from_ratio(0.5)
        assert result <= 2  # 50% error rate is very severe

    def test_ratio_clamped_above_one(self) -> None:
        """Ratios above 1.0 are clamped."""
        assert priority_from_ratio(1.5) == priority_from_ratio(1.0)

    def test_ratio_clamped_below_zero(self) -> None:
        """Ratios below 0.0 are clamped."""
        assert priority_from_ratio(-0.5) == priority_from_ratio(0.0)

    def test_small_nonzero_ratio(self) -> None:
        """Small positive ratios get low priority (high number)."""
        result = priority_from_ratio(0.05)
        assert result >= 4

    def test_high_ratio(self) -> None:
        """High ratios get high priority (low number)."""
        result = priority_from_ratio(0.9)
        assert result <= 2


class TestPriorityFromCount:
    """Tests for priority_from_count function."""

    def test_max_count_highest_priority(self) -> None:
        """Count at max_value yields highest priority (1)."""
        assert priority_from_count(5) == 1

    def test_min_count_lowest_priority(self) -> None:
        """Count at min_value yields lowest priority (5)."""
        assert priority_from_count(1) == 5

    def test_mid_count_mid_priority(self) -> None:
        """Count of 3 yields middle priority (3)."""
        assert priority_from_count(3) == 3

    def test_count_clamped_above_max(self) -> None:
        """Counts above max_value are clamped."""
        assert priority_from_count(10) == priority_from_count(5)

    def test_count_clamped_below_min(self) -> None:
        """Counts below min_value are clamped."""
        assert priority_from_count(0) == priority_from_count(1)

    def test_custom_range(self) -> None:
        """Custom min/max values work correctly."""
        # With min=1, max=10: count of 10 should be priority 1
        assert priority_from_count(10, max_value=10) == 1
        # count of 1 should be priority 10
        assert priority_from_count(1, max_value=10) == 10


class TestStalenessValue:
    """Tests for staleness_value function."""

    def test_empty_buckets_returns_zero(self) -> None:
        """Empty bucket list returns 0."""
        assert staleness_value([]) == 0

    def test_single_bucket_returns_count(self) -> None:
        """Single bucket returns its count."""
        assert staleness_value([{"count": 42}]) == 42

    def test_multiple_buckets_returns_first(self) -> None:
        """Multiple buckets returns first bucket's count (most inclusive)."""
        buckets = [
            {"count": 100, "days": 90},
            {"count": 50, "days": 180},
            {"count": 10, "days": 365},
        ]
        assert staleness_value(buckets) == 100

    def test_missing_count_key_returns_zero(self) -> None:
        """Missing 'count' key in bucket returns 0."""
        assert staleness_value([{"days": 90}]) == 0

    def test_count_as_string_is_converted(self) -> None:
        """String count values are converted to int."""
        # The function uses .get("count", 0) which returns the value as-is
        # then int() converts it
        assert staleness_value([{"count": "5"}]) == 5


class TestPriorityConsistency:
    """Tests for consistency between priority functions."""

    def test_higher_ratio_means_higher_priority(self) -> None:
        """Increasing ratios should yield equal or higher priority (lower number)."""
        prev = priority_from_ratio(0.0)
        for ratio in [0.2, 0.4, 0.6, 0.8, 1.0]:
            current = priority_from_ratio(ratio)
            assert current <= prev, "Priority should decrease with higher ratio"
            prev = current

    def test_higher_count_means_higher_priority(self) -> None:
        """Increasing counts should yield equal or higher priority (lower number)."""
        prev = priority_from_count(1)
        for count in [2, 3, 4, 5]:
            current = priority_from_count(count)
            assert current <= prev, "Priority should decrease with higher count"
            prev = current

    def test_priority_range_is_1_to_5(self) -> None:
        """All priority functions return values in 1-5 range."""
        for ratio in [0.0, 0.25, 0.5, 0.75, 1.0]:
            result = priority_from_ratio(ratio)
            assert 1 <= result <= 5, f"Ratio {ratio} gave priority {result}"

        for count in [0, 1, 2, 3, 4, 5, 10]:
            result = priority_from_count(count)
            assert 1 <= result <= 5, f"Count {count} gave priority {result}"
