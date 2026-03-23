"""
Vector store backends for persisting and querying embeddings.

Supports two backends:
- ChromaDB (recommended, persistent, with HNSW index)
- NumPy   (zero-dependency prototype, cosine search)
"""

import json
import logging
import os
import numpy as np
from typing import Optional

from .config import VectorStoreConfig
from .models import EmbeddingDocument

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """
    Vector store backed by ChromaDB (embedded mode, no server needed).

    Data is persisted to disk at `persist_dir` and survives restarts.
    """

    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self._client = None
        self._collection = None

    def _init_client(self):
        """Lazily initialize ChromaDB client and collection."""
        if self._client is None or self._collection is None:
            import chromadb

            os.makedirs(self.config.persist_dir, exist_ok=True)
            logger.info(
                f"Initializing ChromaDB at: {self.config.persist_dir}"
            )
            if self._client is None:
                self._client = chromadb.PersistentClient(
                    path=self.config.persist_dir
                )
            
            self._collection = self._client.get_or_create_collection(
                name=self.config.collection_name,
                metadata={"hnsw:space": self.config.distance_metric},
            )
            logger.info(
                f"Collection '{self.config.collection_name}' ready "
                f"(existing docs: {self._collection.count()})"
            )

    def upsert(
        self,
        documents: list[EmbeddingDocument],
        embeddings: np.ndarray,
    ):
        """
        Upsert documents + embeddings into ChromaDB.

        Args:
            documents: List of EmbeddingDocument objects.
            embeddings: numpy array of shape (N, dim).
        """
        self._init_client()

        ids = [
            f"{doc.stream_id}_{doc.chunk_id}" for doc in documents
        ]
        texts = [doc.document_text for doc in documents]
        metadatas = [doc.to_metadata() for doc in documents]

        logger.info(f"Upserting {len(ids)} documents into ChromaDB")
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(
            f"Upsert complete. Total docs in collection: "
            f"{self._collection.count()}"
        )

    def query(
        self,
        query_embedding: np.ndarray,
        n_results: int = 5,
    ) -> dict:
        """
        Query the vector store for similar documents.

        Args:
            query_embedding: numpy array of shape (dim,).
            n_results: Number of top results to return.

        Returns:
            Dict with keys: ids, documents, metadatas, distances.
        """
        self._init_client()

        results = self._collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def clear(self):
        """Delete the collection and all its data."""
        self._init_client()
        try:
            self._client.delete_collection(name=self.config.collection_name)
            logger.info(f"Deleted collection '{self.config.collection_name}'")
            # Force re-initialization on the next operation
            self._collection = None
        except Exception as e:
            logger.warning(f"Failed to delete collection: {e}")

    def count(self) -> int:
        """Return the number of documents in the collection."""
        self._init_client()
        if self._collection is None:
            return 0
        return self._collection.count()


class NumpyVectorStore:
    """
    Simple vector store using NumPy arrays saved to disk.

    Good for prototyping — zero external dependencies.
    """

    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self._vectors: Optional[np.ndarray] = None
        self._documents: Optional[list[str]] = None
        self._metadatas: Optional[list[dict]] = None
        self._ids: Optional[list[str]] = None

    def _get_store_path(self) -> str:
        os.makedirs(self.config.persist_dir, exist_ok=True)
        return os.path.join(self.config.persist_dir, "embeddings.npz")

    def upsert(
        self,
        documents: list[EmbeddingDocument],
        embeddings: np.ndarray,
    ):
        """Save documents + embeddings to an .npz file."""
        self._ids = [
            f"{doc.stream_id}_{doc.chunk_id}" for doc in documents
        ]
        self._documents = [doc.document_text for doc in documents]
        self._metadatas = [doc.to_metadata() for doc in documents]
        self._vectors = embeddings

        store_path = self._get_store_path()
        logger.info(f"Saving {len(self._ids)} embeddings to: {store_path}")
        np.savez(
            store_path,
            vectors=embeddings,
            ids=np.array(self._ids),
            documents=np.array(self._documents),
            metadatas=np.array(
                [json.dumps(m) for m in self._metadatas]
            ),
        )
        logger.info("NumPy vector store saved.")

    def _load(self):
        """Load from disk if not already in memory."""
        if self._vectors is None:
            store_path = self._get_store_path()
            data = np.load(store_path, allow_pickle=True)
            self._vectors = data["vectors"]
            self._ids = data["ids"].tolist()
            self._documents = data["documents"].tolist()
            self._metadatas = [
                json.loads(m) for m in data["metadatas"].tolist()
            ]

    def query(
        self,
        query_embedding: np.ndarray,
        n_results: int = 5,
    ) -> dict:
        """Cosine similarity search over stored embeddings."""
        self._load()

        from numpy.linalg import norm

        # Cosine similarity (embeddings are already L2-normalized)
        similarities = self._vectors @ query_embedding
        top_k = np.argsort(similarities)[-n_results:][::-1]

        return {
            "ids": [[self._ids[i] for i in top_k]],
            "documents": [[self._documents[i] for i in top_k]],
            "metadatas": [[self._metadatas[i] for i in top_k]],
            "distances": [[float(1 - similarities[i]) for i in top_k]],
        }

    def count(self) -> int:
        self._load()
        return len(self._ids)

    def clear(self):
        """Delete the numpy store file from disk."""
        store_path = self._get_store_path()
        if os.path.exists(store_path):
            try:
                os.remove(store_path)
                logger.info(f"Deleted NumPy vector store at: {store_path}")
                self._vectors = None
                self._documents = None
                self._metadatas = None
                self._ids = None
            except Exception as e:
                logger.warning(f"Failed to delete NumPy store: {e}")


def create_vector_store(config: VectorStoreConfig):
    """
    Factory function to create the appropriate vector store backend.

    Args:
        config: VectorStoreConfig with backend type.

    Returns:
        A ChromaVectorStore or NumpyVectorStore instance.
    """
    if config.backend == "chromadb":
        return ChromaVectorStore(config)
    elif config.backend == "numpy":
        return NumpyVectorStore(config)
    else:
        raise ValueError(f"Unknown vector store backend: {config.backend}")
