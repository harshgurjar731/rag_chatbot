"""
Embedding model wrapper using sentence-transformers.

Provides lazy-loaded, cached access to a sentence-transformer model
for encoding text documents into dense vectors.
"""

import logging
import numpy as np
from typing import Optional

from .config import EmbeddingConfig

logger = logging.getLogger(__name__)


class Embedder:
    """
    Wraps a sentence-transformers model for encoding text into vectors.

    The model is lazily loaded on first call to encode() and cached
    for subsequent calls.
    """

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model_name = config.model
        self.batch_size = config.batch_size
        self._model = None

    def _load_model(self):
        """Lazily load the sentence-transformers model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.info(
                f"Model loaded. Embedding dimension: "
                f"{self._model.get_sentence_embedding_dimension()}"
            )
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Encode a list of text strings into dense vectors.

        Args:
            texts: List of document strings to embed.

        Returns:
            numpy array of shape (len(texts), embedding_dim).
        """
        model = self._load_model()
        logger.info(
            f"Encoding {len(texts)} documents (batch_size={self.batch_size})"
        )
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,  # L2-normalize for cosine similarity
        )
        logger.info(f"Embeddings shape: {embeddings.shape}")
        return embeddings

    def encode_query(self, query: str) -> np.ndarray:
        """
        Encode a single query string into a dense vector.

        Args:
            query: The user's search query.

        Returns:
            numpy array of shape (embedding_dim,).
        """
        model = self._load_model()
        embedding = model.encode(
            [query],
            normalize_embeddings=True,
        )
        return embedding[0]

    @property
    def embedding_dim(self) -> int:
        """Return the embedding dimension of the loaded model."""
        model = self._load_model()
        return model.get_sentence_embedding_dimension()
