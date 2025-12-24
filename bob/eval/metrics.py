"""Evaluation metrics for retrieval quality.

Implements standard information retrieval metrics:
- Recall@k: What fraction of relevant docs are in top k?
- Precision@k: What fraction of top k are relevant?
- MRR: Mean Reciprocal Rank of first relevant result
"""

from __future__ import annotations


def recall_at_k(expected: list[int], retrieved: list[int], k: int) -> float:
    """Calculate Recall@k.
    
    Recall measures what fraction of relevant documents were retrieved.
    
    Args:
        expected: List of expected chunk IDs (ground truth).
        retrieved: List of retrieved chunk IDs (ranked).
        k: Number of top results to consider.
    
    Returns:
        Recall score between 0.0 and 1.0.
        Returns 1.0 if expected is empty (no relevant = trivially satisfied).
    
    Example:
        >>> recall_at_k([1, 2, 3], [1, 4, 2, 5, 6], k=5)
        0.6666666666666666  # Found 2 of 3 expected
    """
    if not expected:
        return 1.0  # No expected = trivially satisfied
    
    expected_set = set(expected)
    retrieved_k = set(retrieved[:k])
    relevant_retrieved = len(expected_set & retrieved_k)
    
    return relevant_retrieved / len(expected_set)


def precision_at_k(expected: list[int], retrieved: list[int], k: int) -> float:
    """Calculate Precision@k.
    
    Precision measures what fraction of retrieved documents are relevant.
    
    Args:
        expected: List of expected chunk IDs (ground truth).
        retrieved: List of retrieved chunk IDs (ranked).
        k: Number of top results to consider.
    
    Returns:
        Precision score between 0.0 and 1.0.
    
    Example:
        >>> precision_at_k([1, 2, 3], [1, 4, 2, 5, 6], k=5)
        0.4  # 2 of 5 retrieved are relevant
    """
    expected_set = set(expected)
    retrieved_k = set(retrieved[:k])
    relevant_retrieved = len(expected_set & retrieved_k)
    
    return relevant_retrieved / k if k > 0 else 0.0


def mrr(expected: list[int], retrieved: list[int]) -> float:
    """Calculate Mean Reciprocal Rank.
    
    MRR measures how high the first relevant result ranks.
    
    Args:
        expected: List of expected chunk IDs (ground truth).
        retrieved: List of retrieved chunk IDs (ranked).
    
    Returns:
        MRR score between 0.0 and 1.0.
        Returns 1.0 if first result is relevant, 0.5 if second, etc.
        Returns 0.0 if no relevant results found.
    
    Example:
        >>> mrr([1, 2, 3], [4, 1, 5, 2, 3])
        0.5  # First relevant (1) is at position 2
    """
    expected_set = set(expected)
    
    for i, chunk_id in enumerate(retrieved, 1):
        if chunk_id in expected_set:
            return 1.0 / i
    
    return 0.0


def f1_at_k(expected: list[int], retrieved: list[int], k: int) -> float:
    """Calculate F1@k (harmonic mean of precision and recall).
    
    Args:
        expected: List of expected chunk IDs (ground truth).
        retrieved: List of retrieved chunk IDs (ranked).
        k: Number of top results to consider.
    
    Returns:
        F1 score between 0.0 and 1.0.
    
    Example:
        >>> f1_at_k([1, 2, 3], [1, 4, 2, 5, 6], k=5)
        0.5  # Harmonic mean of recall=0.67 and precision=0.4
    """
    r = recall_at_k(expected, retrieved, k)
    p = precision_at_k(expected, retrieved, k)
    
    if r + p == 0:
        return 0.0
    
    return 2 * (p * r) / (p + r)


def average_precision(expected: list[int], retrieved: list[int]) -> float:
    """Calculate Average Precision.
    
    AP is the average of precision values at each relevant rank.
    
    Args:
        expected: List of expected chunk IDs (ground truth).
        retrieved: List of retrieved chunk IDs (ranked).
    
    Returns:
        AP score between 0.0 and 1.0.
    """
    if not expected:
        return 1.0
    
    expected_set = set(expected)
    relevant_count = 0
    precision_sum = 0.0
    
    for i, chunk_id in enumerate(retrieved, 1):
        if chunk_id in expected_set:
            relevant_count += 1
            precision_sum += relevant_count / i
    
    return precision_sum / len(expected_set) if expected_set else 0.0
