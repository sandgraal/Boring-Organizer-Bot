"""Text chunking for document indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bob.config import get_config
from bob.ingest.base import ParsedDocument


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    content: str
    locator_type: str
    locator_value: dict[str, Any]
    token_count: int


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses a simple approximation: ~4 characters per token for English.

    Args:
        text: Text to estimate.

    Returns:
        Estimated token count.
    """
    return len(text) // 4


def chunk_text(
    text: str,
    target_size: int | None = None,
    overlap: int | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: Text to chunk.
        target_size: Target chunk size in tokens.
        overlap: Overlap between chunks in tokens.
        min_size: Minimum chunk size.
        max_size: Maximum chunk size.

    Returns:
        List of text chunks.
    """
    config = get_config().chunking
    target_size = target_size or config.target_size
    overlap = overlap or config.overlap
    min_size = min_size or config.min_size
    max_size = max_size or config.max_size

    # Convert token targets to character estimates
    target_chars = target_size * 4
    overlap_chars = overlap * 4
    min_chars = min_size * 4
    max_chars = max_size * 4

    # Split on paragraphs first, then sentences
    paragraphs = re.split(r"\n\s*\n", text)

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_size = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_size = len(para)

        # If paragraph alone is too big, split on sentences
        if para_size > max_chars:
            # Flush current chunk first
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0

            # Split paragraph into sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sentence_chunk: list[str] = []
            sentence_size = 0

            for sentence in sentences:
                if sentence_size + len(sentence) > target_chars and sentence_chunk:
                    chunks.append(" ".join(sentence_chunk))
                    # Keep overlap
                    overlap_sentences = []
                    overlap_size = 0
                    for s in reversed(sentence_chunk):
                        if overlap_size + len(s) > overlap_chars:
                            break
                        overlap_sentences.insert(0, s)
                        overlap_size += len(s)
                    sentence_chunk = overlap_sentences
                    sentence_size = overlap_size

                sentence_chunk.append(sentence)
                sentence_size += len(sentence)

            if sentence_chunk:
                chunks.append(" ".join(sentence_chunk))

        # Check if adding paragraph exceeds target
        elif current_size + para_size > target_chars:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                # Keep overlap
                overlap_paras = []
                overlap_size = 0
                for p in reversed(current_chunk):
                    if overlap_size + len(p) > overlap_chars:
                        break
                    overlap_paras.insert(0, p)
                    overlap_size += len(p)
                current_chunk = overlap_paras
                current_size = overlap_size

            current_chunk.append(para)
            current_size += para_size
        else:
            current_chunk.append(para)
            current_size += para_size

    # Don't forget the last chunk
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        if len(chunk_text) >= min_chars:
            chunks.append(chunk_text)
        elif chunks:
            # Merge with previous chunk
            chunks[-1] = chunks[-1] + "\n\n" + chunk_text
        else:
            chunks.append(chunk_text)

    return chunks


def chunk_document(doc: ParsedDocument) -> list[Chunk]:
    """Chunk a parsed document into indexable chunks.

    Respects document structure (sections) when chunking.

    Args:
        doc: Parsed document.

    Returns:
        List of chunks with locator information.
    """
    chunks: list[Chunk] = []
    config = get_config().chunking

    for section in doc.sections:
        section_text = section.content.strip()
        if not section_text:
            continue

        estimated_tokens = estimate_tokens(section_text)

        # If section fits in one chunk, keep it together
        if estimated_tokens <= config.max_size:
            chunks.append(
                Chunk(
                    content=section_text,
                    locator_type=section.locator_type,
                    locator_value=section.locator_value.copy(),
                    token_count=estimated_tokens,
                )
            )
        else:
            # Split large sections
            text_chunks = chunk_text(section_text)
            for i, text in enumerate(text_chunks):
                locator = section.locator_value.copy()
                locator["chunk_part"] = i + 1
                locator["chunk_total"] = len(text_chunks)

                chunks.append(
                    Chunk(
                        content=text,
                        locator_type=section.locator_type,
                        locator_value=locator,
                        token_count=estimate_tokens(text),
                    )
                )

    return chunks
