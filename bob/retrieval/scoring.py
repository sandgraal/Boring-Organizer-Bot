"""Hybrid scoring for retrieval.

Combines vector similarity with BM25-style keyword matching for improved
relevance ranking. Supports configurable weights and score normalization.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

# BM25 parameters (standard defaults)
BM25_K1 = 1.2  # Term frequency saturation
BM25_B = 0.75  # Length normalization


@dataclass
class ScoringConfig:
    """Configuration for hybrid scoring."""

    # Weight for vector similarity (0-1)
    vector_weight: float = 0.7

    # Weight for keyword matching (0-1, should sum to ~1 with vector_weight)
    keyword_weight: float = 0.3

    # BM25 parameters
    bm25_k1: float = BM25_K1
    bm25_b: float = BM25_B

    # Metadata boosts (multiplicative)
    recency_boost_enabled: bool = False
    recency_half_life_days: int = 180  # Score halves every 180 days old

    project_match_boost: float = 1.0  # Boost when project matches query context


@dataclass
class ScoredResult:
    """A result with component scores."""

    chunk_id: int
    content: str

    # Component scores (0-1)
    vector_score: float
    keyword_score: float

    # Combined final score (0-1)
    final_score: float

    # Original data
    metadata: dict[str, Any] = field(default_factory=dict)


def tokenize(text: str) -> list[str]:
    """Simple tokenization for BM25.

    Lowercase, split on non-alphanumeric, remove short tokens.

    Args:
        text: Input text.

    Returns:
        List of tokens.
    """
    # Lowercase and split on non-alphanumeric
    tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())
    # Remove very short tokens (except common ones)
    return [t for t in tokens if len(t) > 1]


def compute_idf(documents: list[str]) -> dict[str, float]:
    """Compute inverse document frequency for terms.

    IDF = log((N - df + 0.5) / (df + 0.5))

    Args:
        documents: List of document texts.

    Returns:
        Dictionary mapping terms to IDF scores.
    """
    n = len(documents)
    if n == 0:
        return {}

    # Count document frequency for each term
    df: dict[str, int] = Counter()
    for doc in documents:
        tokens = set(tokenize(doc))
        for token in tokens:
            df[token] += 1

    # Compute IDF
    idf: dict[str, float] = {}
    for term, doc_freq in df.items():
        idf[term] = math.log((n - doc_freq + 0.5) / (doc_freq + 0.5) + 1)

    return idf


def compute_bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    idf: dict[str, float],
    avg_doc_len: float,
    k1: float = BM25_K1,
    b: float = BM25_B,
) -> float:
    """Compute BM25 score for a document given a query.

    BM25 formula:
    score = sum(IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D|/avgdl)))

    Args:
        query_tokens: Tokenized query.
        doc_tokens: Tokenized document.
        idf: Pre-computed IDF dictionary.
        avg_doc_len: Average document length in corpus.
        k1: Term frequency saturation parameter.
        b: Length normalization parameter.

    Returns:
        BM25 score (not normalized).
    """
    doc_len = len(doc_tokens)
    if doc_len == 0 or not query_tokens:
        return 0.0

    # Term frequencies in document
    tf = Counter(doc_tokens)

    score = 0.0
    for term in query_tokens:
        if term not in tf:
            continue

        term_freq = tf[term]
        term_idf = idf.get(term, 0.0)

        # BM25 term score
        numerator = term_freq * (k1 + 1)
        denominator = term_freq + k1 * (1 - b + b * (doc_len / avg_doc_len))

        score += term_idf * (numerator / denominator)

    return score


def normalize_scores(scores: Sequence[float]) -> list[float]:
    """Normalize scores to 0-1 range using min-max normalization.

    Args:
        scores: List of raw scores.

    Returns:
        Normalized scores in [0, 1].
    """
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return [1.0] * len(scores)  # All equal, give max score

    return [(s - min_score) / (max_score - min_score) for s in scores]


class HybridScorer:
    """Combines vector similarity with keyword matching."""

    def __init__(self, config: ScoringConfig | None = None) -> None:
        """Initialize the hybrid scorer.

        Args:
            config: Scoring configuration. Uses defaults if not provided.
        """
        self.config = config or ScoringConfig()

    def score_results(
        self,
        query: str,
        results: list[dict[str, Any]],
        vector_scores: list[float],
    ) -> list[ScoredResult]:
        """Score and re-rank results using hybrid scoring.

        Args:
            query: Original query text.
            results: List of result dictionaries with 'content' field.
            vector_scores: Corresponding vector similarity scores (0-1).

        Returns:
            List of ScoredResult objects, sorted by final_score descending.
        """
        if not results:
            return []

        # Tokenize query
        query_tokens = tokenize(query)

        # Tokenize all documents and compute IDF
        doc_contents = [r.get("content", "") for r in results]
        doc_tokens_list = [tokenize(doc) for doc in doc_contents]

        idf = compute_idf(doc_contents)

        # Compute average document length
        total_tokens = sum(len(tokens) for tokens in doc_tokens_list)
        avg_doc_len = total_tokens / len(results) if results else 1

        # Compute BM25 scores
        bm25_scores = [
            compute_bm25_score(
                query_tokens,
                doc_tokens,
                idf,
                avg_doc_len,
                k1=self.config.bm25_k1,
                b=self.config.bm25_b,
            )
            for doc_tokens in doc_tokens_list
        ]

        # Normalize scores
        normalized_vector = normalize_scores(vector_scores)
        normalized_keyword = normalize_scores(bm25_scores)

        # Combine scores
        scored_results: list[ScoredResult] = []
        for i, result in enumerate(results):
            v_score = normalized_vector[i]
            k_score = normalized_keyword[i]

            # Weighted combination
            final_score = self.config.vector_weight * v_score + self.config.keyword_weight * k_score

            scored_results.append(
                ScoredResult(
                    chunk_id=result.get("id", 0),
                    content=result.get("content", ""),
                    vector_score=v_score,
                    keyword_score=k_score,
                    final_score=final_score,
                    metadata=result,
                )
            )

        # Sort by final score (descending)
        scored_results.sort(key=lambda x: x.final_score, reverse=True)

        return scored_results
