"""Agent tool interfaces for B.O.B.

This module exposes stable functions that AI agents can use reliably.
The interface is designed to be simple and consistent, hiding internal
complexity from agents.

Design principles:
1. Simple inputs and outputs (primitives and dicts)
2. Comprehensive error handling (never raise to agent)
3. Stable API (changes require version bump)
4. Full provenance in results (citations always included)

Usage:
    from bob.agents import index, ask, explain_sources, run_eval

    # Index documents
    result = index(["./docs"], project="my-project")

    # Ask a question
    result = ask("How do I configure logging?", project="my-project")

    # Get detailed source information
    sources = explain_sources(answer_id="abc123")

    # Run evaluation
    eval_result = run_eval(golden_path="docs/eval/example_gold.jsonl")
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SourceInfo:
    """Information about a source citation."""

    file: str
    locator: dict[str, Any]
    date: str | None
    confidence: str
    score: float
    content_preview: str
    outdated: bool = False


@dataclass
class AgentResult:
    """Standard result format for agent tool calls.

    All agent tools return this format for consistency.
    Agents can rely on these fields being present.
    """

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    sources: list[SourceInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    answer_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["sources"] = [asdict(s) for s in self.sources]
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


def index(
    paths: list[str],
    project: str,
    language: str = "en",
) -> AgentResult:
    """Index documents from specified paths.

    This is the agent-safe wrapper around the indexing pipeline.

    Args:
        paths: List of file or directory paths to index.
        project: Project name for organizing documents.
        language: ISO 639-1 language code (default: "en").

    Returns:
        AgentResult with indexing statistics in data field.

    Example:
        result = index(["./docs", "./notes"], project="my-knowledge")
        if result.success:
            print(f"Indexed {result.data['documents']} documents")
    """
    try:
        from bob.index import index_paths

        # Convert to Path objects
        path_objects = [Path(p) for p in paths]

        # Validate paths exist
        missing = [p for p in path_objects if not p.exists()]
        if missing:
            return AgentResult(
                success=False,
                message=f"Paths not found: {missing}",
                warnings=[f"Path does not exist: {p}" for p in missing],
            )

        # Run indexing
        stats = index_paths(
            paths=path_objects,
            project=project,
            language=language,
        )

        return AgentResult(
            success=True,
            message=f"Indexed {stats['documents']} documents ({stats['chunks']} chunks)",
            data={
                "documents": stats["documents"],
                "chunks": stats["chunks"],
                "skipped": stats["skipped"],
                "errors": stats["errors"],
                "project": project,
                "language": language,
            },
            warnings=[f"Errors during indexing: {stats['errors']}"] if stats["errors"] else [],
        )

    except ImportError as e:
        logger.error(f"Import error during indexing: {e}")
        return AgentResult(
            success=False,
            message=f"Module not available: {e}",
        )
    except Exception as e:
        logger.exception("Error during indexing")
        return AgentResult(
            success=False,
            message=f"Indexing failed: {e}",
        )


def ask(
    question: str,
    project: str | None = None,
    top_k: int = 5,
    include_content: bool = True,
) -> AgentResult:
    """Ask a question and get answers with citations.

    This is the agent-safe wrapper around the search and retrieval pipeline.

    Args:
        question: Natural language question.
        project: Filter by project (optional).
        top_k: Number of results to retrieve (default: 5).
        include_content: Include chunk content in results (default: True).

    Returns:
        AgentResult with search results and citations.
        If no results found, success=True but data["results"] is empty.

    Example:
        result = ask("How do I configure logging?", project="docs")
        if result.success and result.sources:
            for source in result.sources:
                print(f"[{source.file}] {source.content_preview}")
        elif not result.sources:
            print("No relevant documents found")

    Note:
        This function NEVER fabricates results. If nothing is found,
        it returns an empty result with appropriate message.
    """
    try:
        from bob.answer.formatter import (
            DateConfidence,
            get_date_confidence,
            is_outdated,
        )
        from bob.retrieval import search

        # Run search
        results = search(
            query=question,
            project=project,
            top_k=top_k,
        )

        # Generate answer ID for tracking
        answer_id = hashlib.sha256(
            f"{question}:{project}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        # Handle no results case
        if not results:
            return AgentResult(
                success=True,  # Search worked, just no results
                message="No relevant documents found for this question.",
                answer_id=answer_id,
                data={
                    "question": question,
                    "project": project,
                    "results_count": 0,
                    "suggestions": [
                        "Try different keywords",
                        "Check if relevant documents are indexed",
                        "Remove project filter if set",
                    ],
                },
                warnings=["No citations available - cannot provide grounded answer"],
            )

        # Build sources list
        sources: list[SourceInfo] = []
        oldest_date = None

        for r in results:
            # Determine date confidence
            confidence = get_date_confidence(r.source_date)
            is_old = is_outdated(r.source_date)

            # Track oldest date for aggregate confidence
            if r.source_date and (oldest_date is None or r.source_date < oldest_date):
                oldest_date = r.source_date

            sources.append(
                SourceInfo(
                    file=r.source_path,
                    locator=r.locator_value,
                    date=r.source_date.isoformat() if r.source_date else None,
                    confidence=confidence.value,
                    score=r.score,
                    content_preview=r.content[:200] + "..." if len(r.content) > 200 else r.content,
                    outdated=is_old,
                )
            )

        # Determine aggregate date confidence
        aggregate_confidence = get_date_confidence(oldest_date)

        # Build warnings
        warnings: list[str] = []
        if any(s.outdated for s in sources):
            warnings.append("Some sources may be outdated (>6 months old)")
        if aggregate_confidence == DateConfidence.LOW:
            warnings.append("Date confidence is LOW - verify information is current")
        if aggregate_confidence == DateConfidence.UNKNOWN:
            warnings.append("Date confidence is UNKNOWN - source dates not available")

        return AgentResult(
            success=True,
            message=f"Found {len(results)} relevant passages",
            answer_id=answer_id,
            data={
                "question": question,
                "project": project,
                "results_count": len(results),
                "date_confidence": aggregate_confidence.value,
                "chunks": [
                    {
                        "chunk_id": r.chunk_id,
                        "content": r.content if include_content else None,
                        "score": r.score,
                        "source_type": r.source_type,
                    }
                    for r in results
                ]
                if include_content
                else [],
            },
            sources=sources,
            warnings=warnings,
        )

    except ImportError as e:
        logger.error(f"Import error during search: {e}")
        return AgentResult(
            success=False,
            message=f"Module not available: {e}",
        )
    except Exception as e:
        logger.exception("Error during search")
        return AgentResult(
            success=False,
            message=f"Search failed: {e}",
        )


def explain_sources(
    answer_id: str | None = None,
    chunk_ids: list[int] | None = None,
) -> AgentResult:
    """Get detailed information about sources.

    Provides full context for citations, useful for verification.

    Args:
        answer_id: ID from a previous ask() result (not yet implemented).
        chunk_ids: List of chunk IDs to explain.

    Returns:
        AgentResult with detailed source information.

    Example:
        result = explain_sources(chunk_ids=[12, 45, 67])
        for source in result.sources:
            print(f"File: {source.file}")
            print(f"Locator: {source.locator}")
            print(f"Content: {source.content_preview}")
    """
    try:
        from bob.db import get_database

        if answer_id is not None:
            logger.debug("answer_id provided but not yet supported")

        if not chunk_ids:
            return AgentResult(
                success=False,
                message="No chunk_ids provided. Provide chunk_ids to explain.",
            )

        db = get_database()
        sources: list[SourceInfo] = []

        for chunk_id in chunk_ids:
            # Query chunk and document info via raw SQL
            # (get_chunk_by_id will be added in future; this is a workaround)
            cursor = db.conn.execute(
                """
                SELECT c.id, c.content, c.locator_type, c.locator_value,
                       d.source_path, d.source_date, d.source_type
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.id = ?
                """,
                (chunk_id,),
            )
            row = cursor.fetchone()

            if row is None:
                logger.warning(f"Chunk {chunk_id} not found")
                continue

            # Parse locator
            locator = row["locator_value"]
            if isinstance(locator, str):
                locator = json.loads(locator)

            # Parse date
            date_str = row["source_date"]

            sources.append(
                SourceInfo(
                    file=row["source_path"] or "unknown",
                    locator=locator or {},
                    date=date_str,
                    confidence="UNKNOWN",  # Would need date calculation
                    score=0.0,  # Not from search, no score
                    content_preview=row["content"][:500] if row["content"] else "",
                    outdated=False,  # Would need date calculation
                )
            )

        return AgentResult(
            success=True,
            message=f"Retrieved details for {len(sources)} chunks",
            sources=sources,
            data={"chunk_ids": chunk_ids},
        )

    except ImportError as e:
        logger.error(f"Import error: {e}")
        return AgentResult(
            success=False,
            message=f"Module not available: {e}",
        )
    except Exception as e:
        logger.exception("Error explaining sources")
        return AgentResult(
            success=False,
            message=f"Failed to explain sources: {e}",
        )


def run_eval(
    golden_path: str = "docs/eval/example_gold.jsonl",
    k: int = 5,
) -> AgentResult:
    """Run evaluation against a golden dataset.

    Computes retrieval metrics (Recall@k, Precision@k, MRR) against
    a golden set of question-answer pairs.

    Args:
        golden_path: Path to golden dataset (JSONL format).
        k: Number of results to consider for metrics (default: 5).

    Returns:
        AgentResult with evaluation metrics in data field.

    Example:
        result = run_eval(golden_path="docs/eval/example_gold.jsonl")
        if result.success:
            print(f"Recall@5: {result.data['recall_at_k']:.2f}")
            print(f"MRR: {result.data['mrr']:.2f}")

    Note:
        This is a stub implementation. Full evaluation harness
        will be implemented in Phase 5.
    """
    try:
        golden_file = Path(golden_path)

        if not golden_file.exists():
            return AgentResult(
                success=False,
                message=f"Golden dataset not found: {golden_path}",
                warnings=["Create golden dataset first: see docs/eval/README.md"],
            )

        # Load golden set
        golden_examples: list[dict[str, Any]] = []
        with open(golden_file) as f:
            for line in f:
                if line.strip():
                    golden_examples.append(json.loads(line))

        if not golden_examples:
            return AgentResult(
                success=False,
                message="Golden dataset is empty",
            )

        # Run evaluation (simplified version)
        from bob.retrieval import search

        results_per_query: list[dict[str, Any]] = []
        total_recall = 0.0
        total_precision = 0.0
        total_mrr = 0.0

        for example in golden_examples:
            question = example["question"]
            expected = set(example.get("expected_chunks", []))

            # Run search
            search_results = search(query=question, top_k=k)
            retrieved = [r.chunk_id for r in search_results]
            retrieved_set = set(retrieved[:k])

            # Calculate metrics
            if expected:
                recall = len(expected & retrieved_set) / len(expected)
                precision = len(expected & retrieved_set) / k

                # MRR
                mrr = 0.0
                for i, chunk_id in enumerate(retrieved, 1):
                    if chunk_id in expected:
                        mrr = 1.0 / i
                        break
            else:
                # No expected chunks - negative example
                recall = 1.0 if not retrieved else 0.0
                precision = 1.0 if not retrieved else 0.0
                mrr = 0.0

            total_recall += recall
            total_precision += precision
            total_mrr += mrr

            results_per_query.append(
                {
                    "id": example.get("id"),
                    "question": question,
                    "recall": recall,
                    "precision": precision,
                    "mrr": mrr,
                    "expected": list(expected),
                    "retrieved": retrieved[:k],
                }
            )

        n = len(golden_examples)

        return AgentResult(
            success=True,
            message=f"Evaluation complete: {n} queries",
            data={
                "recall_at_k": total_recall / n,
                "precision_at_k": total_precision / n,
                "mrr": total_mrr / n,
                "k": k,
                "num_queries": n,
                "golden_path": str(golden_path),
                "per_query": results_per_query,
            },
            warnings=[
                "This is a simplified evaluation stub.",
                "Full harness will be implemented in Phase 5.",
            ],
        )

    except ImportError as e:
        logger.error(f"Import error: {e}")
        return AgentResult(
            success=False,
            message=f"Module not available: {e}",
        )
    except json.JSONDecodeError as e:
        return AgentResult(
            success=False,
            message=f"Invalid golden dataset format: {e}",
        )
    except Exception as e:
        logger.exception("Error running evaluation")
        return AgentResult(
            success=False,
            message=f"Evaluation failed: {e}",
        )
