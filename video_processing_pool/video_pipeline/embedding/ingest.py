"""
Post-ingestion orchestrator — Main entry point.

Reads the ingestion pipeline output (JSON), generates embeddings
for each video chunk, stores them in a vector database, and builds
a knowledge graph.
"""

import json
import logging
import argparse
import os
import sys

from .config import EmbeddingConfig
from .models import EmbeddingDocument
from .embedder import Embedder
from .vector_store import create_vector_store

logger = logging.getLogger(__name__)


def build_documents(chunk_results: list[dict]) -> list[EmbeddingDocument]:
    """
    Convert raw chunk results into EmbeddingDocument objects.

    Each video chunk produces exactly one document by combining
    the VLM caption and audio transcript.

    Args:
        chunk_results: List of chunk dicts from the ingestion JSON.

    Returns:
        List of EmbeddingDocument objects, one per chunk.
    """
    documents = []
    for chunk in chunk_results:
        # Extract caption text
        caption_text = ""
        if chunk.get("caption") and chunk["caption"].get("text"):
            caption_text = chunk["caption"]["text"]

        # Extract transcript text
        transcript_text = ""
        if chunk.get("transcript") and chunk["transcript"].get("full_text"):
            transcript_text = chunk["transcript"]["full_text"]

        # Combine into one document
        parts = []
        if caption_text:
            parts.append(caption_text)
        if transcript_text:
            parts.append(f"Transcript: {transcript_text}")

        document_text = "\n\n".join(parts) if parts else ""

        if not document_text.strip():
            logger.warning(
                f"Chunk {chunk['chunk_id']} has no caption or transcript, "
                f"skipping."
            )
            continue
        
        if caption_text and caption_text.strip():
            doc = EmbeddingDocument(
                document_text=caption_text,
                chunk_id=f"{chunk['chunk_id']}_c",
                source_video=chunk.get("source_video", ""),
                stream_id=chunk.get("stream_id", "default"),
                start_timestamp=chunk.get("start_timestamp", 0.0),
                end_timestamp=chunk.get("end_timestamp", 0.0),
            )
            documents.append(doc)
        if transcript_text and transcript_text.strip():
            doc = EmbeddingDocument(
                document_text=transcript_text,
                chunk_id=f"{chunk['chunk_id']}_t",
                source_video=chunk.get("source_video", ""),
                stream_id=chunk.get("stream_id", "default"),
                start_timestamp=chunk.get("start_timestamp", 0.0),
                end_timestamp=chunk.get("end_timestamp", 0.0),
            )
            documents.append(doc)

    return documents


def run_embedding_ingestion(
    chunk_results: list[dict],
    config: EmbeddingConfig,
) -> None:
    """
    Run the embedding ingestion pipeline.

    1. Build documents from chunk results (1:1 mapping).
    2. Encode documents into vectors.
    3. Store in vector database.

    Args:
        chunk_results: List of chunk dicts from the ingestion JSON.
        config: EmbeddingConfig with model and store settings.
    """
    logger.info("=" * 60)
    logger.info("EMBEDDING INGESTION PIPELINE")
    logger.info("=" * 60)

    # Step 1: Build documents
    documents = build_documents(chunk_results)
    logger.info(f"Built {len(documents)} documents from {len(chunk_results)} chunks")

    if not documents:
        logger.warning("No documents to embed. Exiting.")
        return

    # Step 2: Encode
    embedder = Embedder(config)
    texts = [doc.document_text for doc in documents]
    embeddings = embedder.encode(texts)

    # Step 3: Store
    store = create_vector_store(config.vector_store)
    store.upsert(documents, embeddings)

    logger.info(
        f"Embedding ingestion complete. "
        f"{store.count()} documents in vector store."
    )


def main():
    """CLI entry point for the post-ingestion pipeline."""
    parser = argparse.ArgumentParser(
        description="Post-ingestion pipeline: embeddings + knowledge graph"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the ingestion results JSON file",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to config.yaml (optional)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load results
    logger.info(f"Loading ingestion results from: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        chunk_results = json.load(f)
    logger.info(f"Loaded {len(chunk_results)} chunks")

    # Load config
    embedding_config = EmbeddingConfig()
    if args.config:
        import yaml
        with open(args.config, "r") as f:
            yaml_config = yaml.safe_load(f)
        if yaml_config and "embedding" in yaml_config:
            embedding_config = EmbeddingConfig.from_dict(
                yaml_config["embedding"]
            )

    # Run embedding ingestion
    if embedding_config.enabled:
        run_embedding_ingestion(chunk_results, embedding_config)
    else:
        logger.info("Embedding ingestion is disabled in config.")

    # Run graph construction (imported here to avoid circular deps)
    graph_config_dict = {}
    if args.config:
        import yaml
        with open(args.config, "r") as f:
            yaml_config = yaml.safe_load(f)
        graph_config_dict = yaml_config.get("graph", {})

    if graph_config_dict.get("enabled", True):
        from ..graph.config import GraphConfig
        from ..graph.graph_builder import GraphBuilder
        from ..graph.entity_extractor import LLMEntityExtractor

        graph_config = GraphConfig.from_dict(graph_config_dict)
        extractor = LLMEntityExtractor(graph_config)
        builder = GraphBuilder(graph_config)
        builder.build_from_chunks(chunk_results, extractor)
        builder.save()
        logger.info("Graph construction complete.")
    else:
        logger.info("Graph construction is disabled in config.")

    logger.info("Post-ingestion pipeline finished.")


if __name__ == "__main__":
    main()
