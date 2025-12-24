"""Embedding generation for chunks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from bob.config import get_config

if TYPE_CHECKING:
    import numpy.typing as npt


class Embedder:
    """Wrapper for sentence-transformers embedding model."""

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        """Initialize the embedder.

        Args:
            model_name: Name of the sentence-transformers model.
            device: Device to use (cpu, cuda, mps).
        """
        config = get_config().embedding
        self.model_name = model_name or config.model
        self.device = device or config.device
        self._model = None

    @property
    def model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def embed(self, texts: list[str]) -> npt.NDArray[np.float32]:
        """Embed a list of texts.

        Args:
            texts: List of texts to embed.

        Returns:
            Array of embeddings, shape (len(texts), dimension).
        """
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.astype(np.float32)

    def embed_single(self, text: str) -> npt.NDArray[np.float32]:
        """Embed a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """
        return self.embed([text])[0]


# Global embedder instance
_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Get the global embedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def reset_embedder() -> None:
    """Reset the global embedder (useful for testing)."""
    global _embedder
    _embedder = None


def embed_text(text: str) -> npt.NDArray[np.float32]:
    """Embed a single text using the global embedder.

    Args:
        text: Text to embed.

    Returns:
        Embedding vector.
    """
    return get_embedder().embed_single(text)


def embed_chunks(texts: list[str]) -> npt.NDArray[np.float32]:
    """Embed multiple texts using the global embedder.

    Args:
        texts: Texts to embed.

    Returns:
        Array of embeddings.
    """
    return get_embedder().embed(texts)
