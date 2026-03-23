"""
Knowledge graph builder using NetworkX.

Constructs a directed graph from extracted entities, relationships,
and temporal chunk connections.
"""

import logging
import os
from typing import Optional

import networkx as nx

from .config import GraphConfig
from .models import ExtractionResult, ExtractedEntity
from .entity_extractor import LLMEntityExtractor

logger = logging.getLogger(__name__)


def _normalize_node_id(name: str) -> str:
    """
    Normalize an entity name to a consistent node ID.

    Lowercases, strips whitespace, replaces spaces with underscores.
    """
    return name.strip().lower().replace(" ", "_")


class GraphBuilder:
    """
    Builds a NetworkX DiGraph from video chunk data.

    Creates nodes for:
    - VideoChunks (temporal segments of the video)
    - Entities extracted by the LLM (Person, Object, Location, etc.)
    - Detected objects from CV pipeline

    Creates edges for:
    - Temporal sequence (FOLLOWED_BY between chunks)
    - Entity ↔ Chunk membership (MENTIONED_IN, APPEARS_IN)
    - Entity ↔ Entity relationships (from LLM extraction)
    - Object co-occurrence (CO_OCCURS_WITH)
    """

    def __init__(self, config: GraphConfig):
        self.config = config
        self.graph = nx.DiGraph()
        self._entity_names: dict[str, str] = {}  # normalized → display name

    def _add_chunk_node(self, chunk: dict):
        """Add a VideoChunk node to the graph."""
        chunk_id = chunk["chunk_id"]
        node_id = f"chunk_{chunk_id}"

        self.graph.add_node(
            node_id,
            node_type="VideoChunk",
            chunk_id=chunk_id,
            start_timestamp=chunk.get("start_timestamp", 0.0),
            end_timestamp=chunk.get("end_timestamp", 0.0),
            source_video=chunk.get("source_video", ""),
            stream_id=chunk.get("stream_id", "default"),
        )
        return node_id

    def _add_entity_node(self, entity: ExtractedEntity) -> str:
        """
        Add an entity node to the graph (or merge if it already exists).

        Returns the node ID.
        """
        normalized = _normalize_node_id(entity.name)
        node_id = f"entity_{normalized}"

        if self.graph.has_node(node_id):
            # Node exists — update description if longer
            existing_desc = self.graph.nodes[node_id].get("description", "")
            if len(entity.description) > len(existing_desc):
                self.graph.nodes[node_id]["description"] = entity.description
            # Track which chunks mention this entity
            chunks = self.graph.nodes[node_id].get("chunk_ids", [])
            if entity.source_chunk_id not in chunks:
                chunks.append(entity.source_chunk_id)
                self.graph.nodes[node_id]["chunk_ids"] = chunks
        else:
            self.graph.add_node(
                node_id,
                node_type=entity.entity_type,
                name=entity.name,
                description=entity.description,
                chunk_ids=[entity.source_chunk_id],
            )
            self._entity_names[normalized] = entity.name

        return node_id

    def _add_cv_object_nodes(self, chunk: dict, chunk_node_id: str):
        """
        Add detected CV objects as nodes and link to their chunk.
        """
        cv_meta = chunk.get("cv_metadata", {})
        if not cv_meta or not cv_meta.get("objects"):
            return

        objects = cv_meta["objects"]
        object_nodes = []

        for obj in objects:
            cls = obj.get("class", "unknown")
            track_id = obj.get("track_id", -1)
            node_id = f"object_{cls}_{track_id}"

            if not self.graph.has_node(node_id):
                self.graph.add_node(
                    node_id,
                    node_type="DetectedObject",
                    class_name=cls,
                    track_id=track_id,
                    confidence=obj.get("confidence", 0.0),
                    chunk_ids=[chunk["chunk_id"]],
                )
            else:
                # Merge: track additional chunk appearances
                chunks = self.graph.nodes[node_id].get("chunk_ids", [])
                if chunk["chunk_id"] not in chunks:
                    chunks.append(chunk["chunk_id"])
                    self.graph.nodes[node_id]["chunk_ids"] = chunks
                # Update confidence if higher
                if obj.get("confidence", 0) > self.graph.nodes[node_id].get(
                    "confidence", 0
                ):
                    self.graph.nodes[node_id]["confidence"] = obj["confidence"]

            # Edge: object APPEARS_IN chunk
            self.graph.add_edge(
                node_id,
                chunk_node_id,
                relationship="APPEARS_IN",
                confidence=obj.get("confidence", 0.0),
            )
            object_nodes.append(node_id)

        # Co-occurrence edges between objects in the same chunk
        for i in range(len(object_nodes)):
            for j in range(i + 1, len(object_nodes)):
                if not self.graph.has_edge(object_nodes[i], object_nodes[j]):
                    self.graph.add_edge(
                        object_nodes[i],
                        object_nodes[j],
                        relationship="CO_OCCURS_WITH",
                        chunk_id=chunk["chunk_id"],
                    )

    def _add_extraction_results(
        self, extraction: ExtractionResult, chunk_node_id: str
    ):
        """
        Add LLM-extracted entities and relationships to the graph.
        """
        # Add entity nodes and link to chunk
        entity_node_ids = {}
        for entity in extraction.entities:
            ent_node_id = self._add_entity_node(entity)
            entity_node_ids[entity.name] = ent_node_id

            # Edge: entity MENTIONED_IN chunk
            if not self.graph.has_edge(ent_node_id, chunk_node_id):
                self.graph.add_edge(
                    ent_node_id,
                    chunk_node_id,
                    relationship="MENTIONED_IN",
                )

        # Add inter-entity relationships
        for rel in extraction.relationships:
            source_norm = _normalize_node_id(rel.source)
            target_norm = _normalize_node_id(rel.target)
            source_id = f"entity_{source_norm}"
            target_id = f"entity_{target_norm}"

            # Ensure both nodes exist (they should from entities above)
            if not self.graph.has_node(source_id):
                self.graph.add_node(
                    source_id,
                    node_type="Object",
                    name=rel.source,
                    description="",
                    chunk_ids=[extraction.chunk_id],
                )
            if not self.graph.has_node(target_id):
                self.graph.add_node(
                    target_id,
                    node_type="Object",
                    name=rel.target,
                    description="",
                    chunk_ids=[extraction.chunk_id],
                )

            self.graph.add_edge(
                source_id,
                target_id,
                relationship=rel.relationship_type,
                description=rel.description,
                chunk_id=extraction.chunk_id,
            )

    def _add_temporal_edges(self, chunk_ids: list[int]):
        """
        Add FOLLOWED_BY edges between consecutive chunks.
        """
        sorted_ids = sorted(chunk_ids)
        for i in range(len(sorted_ids) - 1):
            src = f"chunk_{sorted_ids[i]}"
            tgt = f"chunk_{sorted_ids[i + 1]}"
            if self.graph.has_node(src) and self.graph.has_node(tgt):
                self.graph.add_edge(
                    src, tgt, relationship="FOLLOWED_BY"
                )

    def build_from_chunks(
        self,
        chunk_results: list[dict],
        extractor: LLMEntityExtractor,
    ):
        """
        Build the full knowledge graph from ingestion results.

        Args:
            chunk_results: List of chunk dicts from the ingestion JSON.
            extractor: LLMEntityExtractor for entity/relationship extraction.
        """
        logger.info("=" * 60)
        logger.info("KNOWLEDGE GRAPH CONSTRUCTION")
        logger.info("=" * 60)
        logger.info(f"Processing {len(chunk_results)} chunks")

        chunk_ids = []

        # Step 1: Extract entities from all chunks via LLM
        extractions = extractor.extract_batch(chunk_results)

        # Step 2: Build graph
        for chunk, extraction in zip(chunk_results, extractions):
            chunk_id = chunk["chunk_id"]
            chunk_ids.append(chunk_id)

            # Add chunk node
            chunk_node_id = self._add_chunk_node(chunk)

            # Add CV-detected objects
            self._add_cv_object_nodes(chunk, chunk_node_id)

            # Add LLM-extracted entities and relationships
            self._add_extraction_results(extraction, chunk_node_id)

        # Step 3: Add temporal edges
        self._add_temporal_edges(chunk_ids)

        logger.info(
            f"Graph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )

    def save(self, path: Optional[str] = None):
        """
        Save the graph to disk.

        Args:
            path: Override path. Defaults to config.persist_dir.
        """
        if path is None:
            os.makedirs(self.config.persist_dir, exist_ok=True)
            if self.config.output_format == "graphml":
                path = os.path.join(
                    self.config.persist_dir, "knowledge_graph.graphml"
                )
            else:
                path = os.path.join(
                    self.config.persist_dir, "knowledge_graph.json"
                )

        os.makedirs(os.path.dirname(path), exist_ok=True)

        if path.endswith(".graphml"):
            self._save_graphml(path)
        else:
            self._save_json(path)

    def _save_graphml(self, path: str):
        """Save as GraphML (compatible with Gephi, yEd, etc.)."""
        # GraphML doesn't support list attributes, so convert them
        G_copy = self.graph.copy()
        for node_id in G_copy.nodes:
            for key, value in list(G_copy.nodes[node_id].items()):
                if isinstance(value, list):
                    G_copy.nodes[node_id][key] = str(value)

        nx.write_graphml(G_copy, path)
        logger.info(f"Graph saved as GraphML: {path}")

    def _save_json(self, path: str):
        """Save as JSON (node-link format)."""
        import json
        from networkx.readwrite import json_graph

        data = json_graph.node_link_data(G=self.graph)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Graph saved as JSON: {path}")

    def get_stats(self) -> dict:
        """Return summary statistics of the graph."""
        node_types = {}
        for _, attrs in self.graph.nodes(data=True):
            nt = attrs.get("node_type", "unknown")
            node_types[nt] = node_types.get(nt, 0) + 1

        edge_types = {}
        for _, _, attrs in self.graph.edges(data=True):
            et = attrs.get("relationship", "unknown")
            edge_types[et] = edge_types.get(et, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
        }
