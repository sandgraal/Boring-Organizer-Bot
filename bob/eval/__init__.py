"""Evaluation module for B.O.B.

Provides metrics and runners for evaluating retrieval quality.
"""

from bob.eval.metrics import mrr, precision_at_k, recall_at_k
from bob.eval.runner import EvalResult, run_evaluation

__all__ = [
    "EvalResult",
    "mrr",
    "precision_at_k",
    "recall_at_k",
    "run_evaluation",
]
