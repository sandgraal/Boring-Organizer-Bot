"""Index module for chunking and embedding documents."""

from bob.index.chunker import chunk_document, chunk_text
from bob.index.embedder import embed_chunks, embed_text, get_embedder
from bob.index.indexer import index_paths

__all__ = [
    "chunk_document",
    "chunk_text",
    "embed_chunks",
    "embed_text",
    "get_embedder",
    "index_paths",
]
