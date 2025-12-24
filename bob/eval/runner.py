"""Evaluation runner for golden datasets.

Runs queries from a golden dataset and computes retrieval metrics.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Callable

from bob.eval.metrics import mrr, precision_at_k, recall_at_k

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result for a single query evaluation."""
    
    id: int
    question: str
    recall: float
    precision: float
    mrr: float
    expected: list[int]
    retrieved: list[int]
    passed: bool  # True if MRR >= 0.5 (first relevant in top 2)


@dataclass
class EvalResult:
    """Aggregate evaluation results."""
    
    # Aggregate metrics
    recall_mean: float
    recall_std: float
    precision_mean: float
    precision_std: float
    mrr_mean: float
    mrr_std: float
    
    # Counts
    num_queries: int
    num_passed: int
    num_failed: int
    
    # Details
    k: int
    golden_path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    per_query: list[QueryResult] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "recall_mean": self.recall_mean,
            "recall_std": self.recall_std,
            "precision_mean": self.precision_mean,
            "precision_std": self.precision_std,
            "mrr_mean": self.mrr_mean,
            "mrr_std": self.mrr_std,
            "num_queries": self.num_queries,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "k": self.k,
            "golden_path": self.golden_path,
            "timestamp": self.timestamp,
            "per_query": [
                {
                    "id": q.id,
                    "question": q.question,
                    "recall": q.recall,
                    "precision": q.precision,
                    "mrr": q.mrr,
                    "passed": q.passed,
                }
                for q in self.per_query
            ],
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class GoldenExample:
    """A single example from the golden dataset."""
    
    id: int
    question: str
    expected_chunks: list[int]
    expected_answer: str | None = None
    difficulty: str = "medium"
    category: str = "general"
    notes: str = ""


def load_golden_set(path: Path) -> list[GoldenExample]:
    """Load golden dataset from JSONL file.
    
    Args:
        path: Path to JSONL file.
    
    Returns:
        List of GoldenExample objects.
    
    Raises:
        FileNotFoundError: If path does not exist.
        json.JSONDecodeError: If file is malformed.
    """
    examples: list[GoldenExample] = []
    
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            
            try:
                data = json.loads(line)
                examples.append(GoldenExample(
                    id=data["id"],
                    question=data["question"],
                    expected_chunks=data.get("expected_chunks", []),
                    expected_answer=data.get("expected_answer"),
                    difficulty=data.get("difficulty", "medium"),
                    category=data.get("category", "general"),
                    notes=data.get("notes", ""),
                ))
            except (KeyError, json.JSONDecodeError) as e:
                logger.warning(f"Skipping invalid line {line_num}: {e}")
    
    return examples


def run_evaluation(
    golden_path: Path | str,
    search_fn: Callable[[str], list[int]] | None = None,
    k: int = 5,
) -> EvalResult:
    """Run evaluation against a golden dataset.
    
    Args:
        golden_path: Path to golden dataset (JSONL format).
        search_fn: Optional custom search function. If None, uses bob.retrieval.search.
        k: Number of results to consider for metrics.
    
    Returns:
        EvalResult with aggregate and per-query metrics.
    """
    golden_path = Path(golden_path)
    
    # Load golden set
    golden = load_golden_set(golden_path)
    
    if not golden:
        raise ValueError(f"Golden set is empty: {golden_path}")
    
    # Default search function
    if search_fn is None:
        from bob.retrieval import search
        
        def default_search(query: str) -> list[int]:
            results = search(query=query, top_k=k)
            return [r.chunk_id for r in results]
        
        search_fn = default_search
    
    # Run evaluation
    query_results: list[QueryResult] = []
    recalls: list[float] = []
    precisions: list[float] = []
    mrrs: list[float] = []
    
    for example in golden:
        retrieved = search_fn(example.question)
        
        # Handle negative examples (expected_chunks is empty)
        if not example.expected_chunks:
            # For negative examples, success means returning empty or irrelevant results
            # We measure this differently - skip standard metrics
            r = 1.0 if not retrieved else 0.0
            p = 1.0 if not retrieved else 0.0
            m = 0.0
        else:
            r = recall_at_k(example.expected_chunks, retrieved, k)
            p = precision_at_k(example.expected_chunks, retrieved, k)
            m = mrr(example.expected_chunks, retrieved)
        
        recalls.append(r)
        precisions.append(p)
        mrrs.append(m)
        
        query_results.append(QueryResult(
            id=example.id,
            question=example.question,
            recall=r,
            precision=p,
            mrr=m,
            expected=example.expected_chunks,
            retrieved=retrieved[:k],
            passed=m >= 0.5 or not example.expected_chunks,  # Pass if MRR >= 0.5 or negative example
        ))
    
    # Compute statistics
    n = len(golden)
    
    return EvalResult(
        recall_mean=mean(recalls),
        recall_std=stdev(recalls) if n > 1 else 0.0,
        precision_mean=mean(precisions),
        precision_std=stdev(precisions) if n > 1 else 0.0,
        mrr_mean=mean(mrrs),
        mrr_std=stdev(mrrs) if n > 1 else 0.0,
        num_queries=n,
        num_passed=sum(1 for q in query_results if q.passed),
        num_failed=sum(1 for q in query_results if not q.passed),
        k=k,
        golden_path=str(golden_path),
        per_query=query_results,
    )


def compare_results(
    current: EvalResult,
    baseline: EvalResult,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Compare current results to baseline.
    
    Args:
        current: Current evaluation results.
        baseline: Baseline results to compare against.
        tolerance: Acceptable regression threshold (default 5%).
    
    Returns:
        Comparison dict with deltas and pass/fail status.
    """
    recall_delta = current.recall_mean - baseline.recall_mean
    precision_delta = current.precision_mean - baseline.precision_mean
    mrr_delta = current.mrr_mean - baseline.mrr_mean
    
    return {
        "recall_delta": recall_delta,
        "precision_delta": precision_delta,
        "mrr_delta": mrr_delta,
        "recall_passed": recall_delta >= -tolerance,
        "precision_passed": precision_delta >= -tolerance,
        "mrr_passed": mrr_delta >= -tolerance,
        "overall_passed": (
            recall_delta >= -tolerance and
            precision_delta >= -tolerance and
            mrr_delta >= -tolerance
        ),
        "tolerance": tolerance,
    }
