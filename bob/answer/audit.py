"""Audit trail utilities for Ask responses."""

from __future__ import annotations

from bob.api.schemas import AskAudit, AuditChunk, SourceLocator
from bob.api.utils import build_locator
from bob.retrieval.search import SearchResult

SNIPPET_MAX_CHARS = 500


def _build_snippet(content: str) -> str:
    if len(content) <= SNIPPET_MAX_CHARS:
        return content
    return f"{content[:SNIPPET_MAX_CHARS]}..."


def _audit_chunk(result: SearchResult, index: int) -> AuditChunk:
    locator: SourceLocator = build_locator(result)
    return AuditChunk(
        chunk_id=result.chunk_id,
        source_id=index,
        rank=index,
        score=round(result.score, 4),
        file_path=result.source_path,
        locator=locator,
        snippet=_build_snippet(result.content),
    )


def build_audit_payload(results: list[SearchResult]) -> AskAudit:
    """Build audit payload for an Ask response."""
    retrieved = [_audit_chunk(result, idx + 1) for idx, result in enumerate(results)]
    used = retrieved[:1]
    return AskAudit(
        retrieved=retrieved,
        used=used,
        unsupported_spans=[],
    )
