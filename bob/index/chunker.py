"""Text chunking for document indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bob.config import get_config
from bob.ingest.base import ParsedDocument

# Common boilerplate patterns to detect low-quality chunks
BOILERPLATE_PATTERNS = [
    r"^copyright\s+\d{4}",  # Copyright notices
    r"^all\s+rights\s+reserved",  # Rights reserved
    r"^table\s+of\s+contents?",  # TOC headers
    r"^page\s+\d+\s*(of\s+\d+)?$",  # Page numbers
    r"^\d+\s*/\s*\d+$",  # Slide numbers (1/10)
    r"^(chapter|section|part)\s+\d+$",  # Just section numbers
    r"^-{3,}$",  # Horizontal rules
    r"^[_=]{3,}$",  # Alternative horizontal rules
    r"^\s*\.{3,}\s*$",  # Ellipsis lines
    r"^(click|tap|select)\s+here",  # Navigation instructions
    r"^back\s+to\s+top$",  # Navigation links
    r"^(next|previous|continue)$",  # Navigation buttons
]

# Minimum meaningful content thresholds
MIN_WORDS = 10  # Minimum word count for a meaningful chunk
MIN_UNIQUE_WORDS = 5  # Minimum unique words to avoid repetitive content
MIN_ALPHA_RATIO = 0.5  # At least 50% alphabetic characters


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
                    overlap_sentences: list[str] = []
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
                overlap_paras: list[str] = []
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


def is_boilerplate(text: str) -> bool:
    """Check if text is likely boilerplate content.

    Args:
        text: Text to check.

    Returns:
        True if text matches boilerplate patterns.
    """
    text_lower = text.lower().strip()
    return any(re.match(pattern, text_lower, re.IGNORECASE) for pattern in BOILERPLATE_PATTERNS)


def has_minimal_content(text: str) -> bool:
    """Check if text has enough meaningful content.

    Args:
        text: Text to check.

    Returns:
        True if text has sufficient meaningful content.
    """
    # Count words
    words = text.split()
    if len(words) < MIN_WORDS:
        return False

    # Count unique words
    unique_words = {w.lower() for w in words if len(w) > 1}
    if len(unique_words) < MIN_UNIQUE_WORDS:
        return False

    # Check alpha ratio (avoid chunks that are mostly numbers/symbols)
    alpha_chars = sum(1 for c in text if c.isalpha())
    total_chars = len(text.replace(" ", ""))
    return not (total_chars > 0 and alpha_chars / total_chars < MIN_ALPHA_RATIO)


def validate_chunk(chunk: Chunk) -> bool:
    """Validate that a chunk meets quality criteria.

    Args:
        chunk: Chunk to validate.

    Returns:
        True if chunk passes quality validation.
    """
    content = chunk.content.strip()

    # Empty or whitespace-only
    if not content:
        return False

    # Too short (use token count which is already computed)
    if chunk.token_count < 5:  # Extremely short
        return False

    # Check for boilerplate
    if is_boilerplate(content):
        return False

    # Check for minimal content
    return has_minimal_content(content)


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
            chunk = Chunk(
                content=section_text,
                locator_type=section.locator_type,
                locator_value=section.locator_value.copy(),
                token_count=estimated_tokens,
            )
            if validate_chunk(chunk):
                chunks.append(chunk)
        else:
            # Split large sections
            text_chunks = chunk_text(section_text)
            for i, text in enumerate(text_chunks):
                locator = section.locator_value.copy()
                locator["chunk_part"] = i + 1
                locator["chunk_total"] = len(text_chunks)

                chunk = Chunk(
                    content=text,
                    locator_type=section.locator_type,
                    locator_value=locator,
                    token_count=estimate_tokens(text),
                )
                if validate_chunk(chunk):
                    chunks.append(chunk)

    return chunks
