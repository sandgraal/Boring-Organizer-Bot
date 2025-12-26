"""Document indexing pipeline."""

from __future__ import annotations

import fnmatch
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from bob.config import get_config
from bob.db import get_database
from bob.db.database import compute_content_hash
from bob.index.chunker import chunk_document
from bob.index.embedder import embed_chunks
from bob.ingest import get_parser
from bob.ingest.git_docs import is_git_url, normalize_git_url, parse_git_repo

logger = logging.getLogger(__name__)


def should_ignore(path: Path) -> bool:
    """Check if a path should be ignored during indexing.

    Args:
        path: Path to check.

    Returns:
        True if path should be ignored.
    """
    config = get_config()
    name = path.name

    for pattern in config.paths.ignore:
        if fnmatch.fnmatch(name, pattern):
            return True
        if fnmatch.fnmatch(str(path), pattern):
            return True

    return False


def _resolve_source_type(path: Path, parser: object | None) -> str | None:
    """Best-effort source type detection for ingestion error logging."""
    if parser is not None:
        name = parser.__class__.__name__
        if name.lower().endswith("parser"):
            name = name[:-6]
        return name.lower() or None
    suffix = path.suffix.lower().lstrip(".")
    return suffix or None


def _iter_indexable_files(path: Path) -> Iterator[Path]:
    """Yield files to index under a directory, respecting ignore rules."""

    try:
        for entry in path.iterdir():
            if should_ignore(entry):
                continue
            if entry.is_file():
                yield entry
            elif entry.is_dir():
                yield from _iter_indexable_files(entry)
    except (PermissionError, OSError) as exc:
        logger.warning("Unable to scan %s: %s", path, exc)


def count_indexable_targets(paths: list[Path | str]) -> int:
    """Estimate how many files/targets will be indexed."""

    total = 0
    for target in paths:
        target_str = normalize_git_url(str(target))

        if is_git_url(target_str):
            total += 1
            continue

        target_path = target if isinstance(target, Path) else Path(target_str)
        if not target_path.exists():
            continue

        if target_path.is_file():
            if get_parser(target_path):
                total += 1
            continue

        if target_path.is_dir():
            for item in _iter_indexable_files(target_path):
                if get_parser(item):
                    total += 1

    return total


def index_file(
    path: Path,
    project: str,
    language: str,
    progress_callback: Callable[[Path], None] | None = None,
) -> dict[str, int]:
    """Index a single file.

    Args:
        path: Path to the file.
        project: Project name.
        language: Document language.

    Returns:
        Stats dict with chunks count and skipped status.
    """
    if progress_callback:
        progress_callback(path)

    db = get_database()
    parser = get_parser(path)

    if parser is None:
        logger.debug(f"No parser for {path}")
        return {"chunks": 0, "skipped": 1, "documents": 0}

    max_size_mb = get_config().paths.max_file_size_mb
    if max_size_mb > 0:
        try:
            file_size = path.stat().st_size
        except OSError as exc:
            logger.warning("Unable to read size for %s: %s", path, exc)
        else:
            max_bytes = max_size_mb * 1024 * 1024
            if file_size > max_bytes:
                db.log_ingestion_error(
                    source_path=str(path),
                    source_type=_resolve_source_type(path, parser),
                    project=project,
                    error_type="oversize",
                    error_message=f"File exceeds {max_size_mb} MB size limit.",
                )
                logger.warning("Skipping %s: exceeds %s MB size limit", path, max_size_mb)
                return {"chunks": 0, "skipped": 0, "documents": 0, "errors": 1}

    # Parse the document
    try:
        parsed = parser.parse(path)
    except Exception as e:
        logger.error(f"Failed to parse {path}: {e}")
        db.log_ingestion_error(
            source_path=str(path),
            source_type=_resolve_source_type(path, parser),
            project=project,
            error_type="parse_error",
            error_message=str(e),
        )
        return {"chunks": 0, "skipped": 0, "documents": 0, "errors": 1}

    if not parsed.content.strip():
        db.log_ingestion_error(
            source_path=str(path),
            source_type=parsed.source_type,
            project=project,
            error_type="no_text",
            error_message="Parsed document contained no text.",
        )

    # Check if document has changed
    content_hash = compute_content_hash(parsed.content)
    existing = db.get_document_by_path(str(path), project)

    if existing and existing["content_hash"] == content_hash:
        logger.debug(f"Skipping unchanged document: {path}")
        return {"chunks": 0, "skipped": 1, "documents": 0}

    # Insert/update document
    doc_id = db.insert_document(
        source_path=str(path),
        source_type=parsed.source_type,
        project=project,
        content_hash=content_hash,
        language=language,
        source_date=parsed.source_date,
    )

    # Delete existing chunks if updating
    if existing:
        db.delete_document_chunks(doc_id)

    # Chunk the document
    chunks = chunk_document(parsed)
    if not chunks:
        logger.debug(f"No chunks from {path}")
        return {"chunks": 0, "skipped": 0, "documents": 1}

    # Generate embeddings in batch
    chunk_texts = [c.content for c in chunks]
    embeddings = embed_chunks(chunk_texts)

    # Store chunks and embeddings
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
        chunk_id = db.insert_chunk(
            document_id=doc_id,
            content=chunk.content,
            locator_type=chunk.locator_type,
            locator_value=chunk.locator_value,
            chunk_index=i,
            token_count=chunk.token_count,
        )
        db.insert_embedding(chunk_id, embedding)

    logger.info(f"Indexed {path}: {len(chunks)} chunks")
    return {"chunks": len(chunks), "skipped": 0, "documents": 1}


def index_directory(
    path: Path,
    project: str,
    language: str,
    progress_callback: Callable[[Path], None] | None = None,
) -> dict[str, int]:
    """Recursively index a directory.

    Args:
        path: Directory path.
        project: Project name.
        language: Document language.

    Returns:
        Aggregate stats.
    """
    stats: dict[str, int] = {"documents": 0, "chunks": 0, "skipped": 0, "errors": 0}

    for item in path.iterdir():
        if should_ignore(item):
            continue

        if item.is_file():
            result = index_file(item, project, language, progress_callback)
            for key in stats:
                stats[key] = stats.get(key, 0) + result.get(key, 0)
        elif item.is_dir():
            result = index_directory(item, project, language, progress_callback)
            for key in stats:
                stats[key] = stats.get(key, 0) + result.get(key, 0)

    return stats


def index_git_repo(
    url: str,
    project: str,
    language: str,
    progress_callback: Callable[[Path], None] | None = None,
) -> dict[str, int]:
    """Index documentation from a git repository.

    Args:
        url: Repository URL.
        project: Project name.
        language: Document language.

    Returns:
        Stats dict.
    """
    db = get_database()
    stats: dict[str, int] = {"documents": 0, "chunks": 0, "skipped": 0, "errors": 0}

    try:
        for parsed in parse_git_repo(url, project):
            if progress_callback and parsed.source_path:
                progress_callback(Path(parsed.source_path))
            content_hash = compute_content_hash(parsed.content)

            doc_id = db.insert_document(
                source_path=parsed.source_path,
                source_type="git",
                project=project,
                content_hash=content_hash,
                language=language,
                source_date=parsed.source_date,
                git_repo=parsed.metadata.get("git_repo"),
                git_commit=parsed.metadata.get("git_commit"),
            )

            chunks = chunk_document(parsed)
            if chunks:
                chunk_texts = [c.content for c in chunks]
                embeddings = embed_chunks(chunk_texts)

                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                    chunk_id = db.insert_chunk(
                        document_id=doc_id,
                        content=chunk.content,
                        locator_type=chunk.locator_type,
                        locator_value=chunk.locator_value,
                        chunk_index=i,
                        token_count=chunk.token_count,
                    )
                    db.insert_embedding(chunk_id, embedding)

                stats["chunks"] += len(chunks)

            stats["documents"] += 1

    except Exception as e:
        logger.error(f"Failed to index git repo {url}: {e}")
        stats["errors"] += 1

    return stats


def index_paths(
    paths: list[Path | str],
    project: str,
    language: str,
    progress_callback: Callable[[Path], None] | None = None,
) -> dict[str, Any]:
    """Index multiple paths (files, directories, or git URLs).

    Args:
        paths: List of paths to index.
        project: Project name.
        language: Document language.

    Returns:
        Aggregate stats.
    """
    # Ensure database is initialized
    db = get_database()
    db.migrate()

    stats: dict[str, int] = {"documents": 0, "chunks": 0, "skipped": 0, "errors": 0}

    for path in paths:
        path_str = normalize_git_url(str(path))

        if is_git_url(path_str):
            result = index_git_repo(path_str, project, language, progress_callback)
        else:
            target_path = path if isinstance(path, Path) else Path(path_str)
            if target_path.is_file():
                result = index_file(target_path, project, language, progress_callback)
            elif target_path.is_dir():
                result = index_directory(target_path, project, language, progress_callback)
            else:
                logger.warning(f"Path not found: {target_path}")
                stats["errors"] = stats.get("errors", 0) + 1
                continue

        for key in stats:
            stats[key] = stats.get(key, 0) + result.get(key, 0)

    return stats
