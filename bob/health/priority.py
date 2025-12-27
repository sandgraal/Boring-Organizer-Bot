"""Priority calculation utilities for health metrics and fix queue tasks.

These functions convert raw values (ratios, counts) into priority buckets where
1 is highest priority and 5 is lowest. Used by both the Coach Mode suggestion
engine and the Fix Queue task builder.
"""

from __future__ import annotations

from typing import Any


def invert_priority(bucket: int, *, min_value: int = 1, max_value: int = 5) -> int:
    """Invert a priority bucket so higher severity yields lower priority numbers.

    Args:
        bucket: The bucket value to invert.
        min_value: Minimum bucket value (default 1).
        max_value: Maximum bucket value (default 5).

    Returns:
        Inverted priority where 1 is highest priority.
    """
    return max_value + min_value - bucket


def priority_from_ratio(
    value: float, scale: int = 10, *, min_value: int = 1, max_value: int = 5
) -> int:
    """Convert a ratio (0.0-1.0) into a priority bucket.

    Higher ratios indicate more severe issues and result in higher priority
    (lower numbers). For example, a 30% not-found rate is more urgent than 10%.

    Args:
        value: A ratio between 0.0 and 1.0.
        scale: Scaling factor for bucket calculation (default 10).
        min_value: Minimum bucket value before inversion (default 1).
        max_value: Maximum bucket value (default 5).

    Returns:
        Priority bucket from min_value (highest) to max_value (lowest).
    """
    normalized = max(0.0, min(1.0, value))
    bucket = max(min_value, min(max_value, int(normalized * scale) or min_value))
    return invert_priority(bucket, min_value=min_value, max_value=max_value)


def priority_from_count(value: int, *, min_value: int = 1, max_value: int = 5) -> int:
    """Convert a count into a 1-5 priority bucket.

    Higher counts indicate more severe issues and result in higher priority
    (lower numbers). For example, 10 repeated questions is more urgent than 2.

    Args:
        value: A count value.
        min_value: Minimum bucket value (default 1).
        max_value: Maximum bucket value (default 5).

    Returns:
        Priority bucket from 1 (highest) to 5 (lowest).
    """
    bucket = max(min_value, min(max_value, value))
    return invert_priority(bucket, min_value=min_value, max_value=max_value)


def staleness_value(buckets: list[dict[str, Any]]) -> int:
    """Extract the count from the first (smallest/most inclusive) staleness bucket.

    The staleness buckets are ordered by age threshold, with the smallest (most
    inclusive) bucket first. This returns that count as the signal value.

    Args:
        buckets: List of bucket dicts with 'count' keys, ordered by threshold.

    Returns:
        Count from the first bucket, or 0 if buckets is empty.
    """
    if not buckets:
        return 0
    return int(buckets[0].get("count", 0))
