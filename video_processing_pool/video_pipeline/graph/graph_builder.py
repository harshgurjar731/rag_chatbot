"""
Knowledge graph builder using NetworkX.

Constructs a directed graph with the following schema:
Nodes: Video, Chunk, Summary, Object, Frame
Edges: HAS_CHUNK, HAS_FRAME, DESCRIBES, CONTAINS_OBJECT, TEMPORAL_NEXT, INVOLVED_IN
"""

import logging
import os
import json
from typing import Optional

import networkx as nx

from .config import GraphConfig
from .models import ExtractionResult, ExtractedEntity
from .entity_extractor import LLMEntityExtractor

logger = logging.getLogger(__name__)


def _normalize_id(val: str) -> str:
    return str(val).lower().strip().replace(" ", "_")


class GraphBuilder:
    def __init__(self, config: GraphConfig):
        self.config = config
        self.graph = nx.DiGraph()

    def _add_video_node(self, stream_id: str, source_video: str):
        node_id = f"video_{stream_id}"
        if not self.graph.has_node(node_id):
            self.graph.add_node(
                node_id,
                node_type="Video",
                uuid=stream_id,
                filename=os.path.basename(source_video) if source_video else "unknown",
                camera_id="default",
                is_live=False
            )
        return node_id

    def _add_chunk_node(self, chunk: dict):
        chunk_idx = chunk["chunk_id"]
        node_id = f"chunk_{chunk_idx}"
        cv_meta_str = json.dumps(chunk.get("cv_metadata", {}))

        self.graph.add_node(
            node_id,
            node_type="Chunk",
            chunkIdx=chunk_idx,
            start_time=float(chunk.get("start_timestamp", 0.0)),
            end_time=float(chunk.get("end_timestamp", 0.0)),
            cv_meta=cv_meta_str
        )
        return node_id

    def _add_summary_node(self, chunk: dict):
        chunk_idx = chunk["chunk_id"]
        caption_data = chunk.get("caption", {})
        transcript_data = chunk.get("transcript", {})

        text = caption_data.get("text", "")
        if not text:
            text = transcript_data.get("full_text", "")

        model_id = caption_data.get("model", transcript_data.get("model", "unknown"))
        start_time = float(chunk.get("start_timestamp", 0.0))

        if not text:
            return None

        node_id = f"summary_{chunk_idx}"
        self.graph.add_node(
            node_id,
            node_type="Summary",
            text=text,
            embedding=[],  # Add vector store embedding here if supported natively by graph
            model_id=model_id,
            timestamp=start_time
        )
        return node_id

    def _add_frame_node(self, chunk_idx: int, frame_offset: int, timestamp: float):
        node_id = f"frame_{chunk_idx}_{frame_offset}"
        if not self.graph.has_node(node_id):
            self.graph.add_node(
                node_id,
                node_type="Frame",
                timestamp=float(timestamp),
                image_path=""
            )
        return node_id

    def _add_object_node(self, obj: dict):
        label = obj.get("class", "unknown").capitalize()
        track_id = str(obj.get("track_id", "unknown"))

        node_id = f"object_{_normalize_id(label)}_{track_id}"
        if not self.graph.has_node(node_id):
            self.graph.add_node(
                node_id,
                node_type="Object",
                label=label,
                object_id=track_id
            )
        return node_id

    def build_from_chunks(
        self,
        chunk_results: list[dict],
        extractor: LLMEntityExtractor,
    ):
        logger.info("=" * 60)
        logger.info("KNOWLEDGE GRAPH CONSTRUCTION")
        logger.info("=" * 60)
        logger.info(f"Processing {len(chunk_results)} chunks")

        extractions = extractor.extract_batch(chunk_results)

        chunk_nodes_created = []

        for chunk_idx, (chunk, extraction) in enumerate(zip(chunk_results, extractions)):
            # 1. Video Node
            stream_id = chunk.get("stream_id", "default")
            source_video = chunk.get("source_video", "")
            video_node = self._add_video_node(stream_id, source_video)

            # 2. Chunk Node
            chunk_node = self._add_chunk_node(chunk)
            chunk_nodes_created.append((chunk["chunk_id"], chunk_node))

            # Edge: HAS_CHUNK
            self.graph.add_edge(
                video_node, chunk_node, relationship="HAS_CHUNK", sequence_order=chunk["chunk_id"]
            )

            # 3. Summary Node
            summary_node = self._add_summary_node(chunk)
            if summary_node:
                # Edge: DESCRIBES
                self.graph.add_edge(
                    summary_node, chunk_node, relationship="DESCRIBES", confidence_score=1.0
                )

            # 4. CV Objects and Frames
            cv_meta = chunk.get("cv_metadata", {})
            objects = cv_meta.get("objects", [])

            start_time = float(chunk.get("start_timestamp", 0.0))

            # Extract normalized labels from LLM for INVOLVED_IN heuristic
            llm_entity_names = [_normalize_id(ent.name) for ent in extraction.entities]

            for obj in objects:
                obj_node = self._add_object_node(obj)
                bbox = obj.get("bbox", [])
                conf = float(obj.get("confidence", 0.0))
                label_norm = _normalize_id(obj.get("class", ""))

                # Edge: CONTAINS_OBJECT (Chunk -> Object)
                self.graph.add_edge(
                    chunk_node, obj_node, relationship="CONTAINS_OBJECT", bbox=bbox, confidence=conf
                )

                frames_seen = obj.get("frames_seen", [])
                for f_offset in frames_seen:
                    # Approximate frame timestamp based on offset
                    frame_ts = start_time + (f_offset * 0.5)
                    frame_node = self._add_frame_node(chunk["chunk_id"], f_offset, frame_ts)

                    # Edge: HAS_FRAME (Chunk -> Frame)
                    if not self.graph.has_edge(chunk_node, frame_node):
                        self.graph.add_edge(
                            chunk_node, frame_node, relationship="HAS_FRAME", offset_ns=f_offset
                        )

                    # Edge: CONTAINS_OBJECT (Frame -> Object)
                    self.graph.add_edge(
                        frame_node, obj_node, relationship="CONTAINS_OBJECT", bbox=bbox, confidence=conf
                    )

                # 5. INVOLVED_IN (Object -> Summary)
                if summary_node:
                    summary_text = self.graph.nodes[summary_node].get("text", "").lower()
                    if label_norm in summary_text or label_norm in llm_entity_names:
                        self.graph.add_edge(
                            obj_node, summary_node, relationship="INVOLVED_IN"
                        )

        # 6. TEMPORAL_NEXT Edges
        chunk_nodes_created.sort(key=lambda x: x[0])
        for i in range(len(chunk_nodes_created) - 1):
            src_node = chunk_nodes_created[i][1]
            tgt_node = chunk_nodes_created[i + 1][1]
            self.graph.add_edge(src_node, tgt_node, relationship="TEMPORAL_NEXT")

        logger.info(
            f"Graph built: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges"
        )

    def save(self, path: Optional[str] = None):
        if path is None:
            os.makedirs(self.config.persist_dir, exist_ok=True)
            if self.config.output_format == "graphml":
                path = os.path.join(self.config.persist_dir, "knowledge_graph.graphml")
            else:
                path = os.path.join(self.config.persist_dir, "knowledge_graph.json")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        if path.endswith(".graphml"):
            self._save_graphml(path)
        else:
            self._save_json(path)

    def _save_graphml(self, path: str):
        G_copy = self.graph.copy()
        for node_id in G_copy.nodes:
            for key, value in list(G_copy.nodes[node_id].items()):
                if isinstance(value, list) or isinstance(value, dict):
                    G_copy.nodes[node_id][key] = json.dumps(value)

        for src, tgt in G_copy.edges:
            for key, value in list(G_copy.edges[src, tgt].items()):
                if isinstance(value, list) or isinstance(value, dict):
                    G_copy.edges[src, tgt][key] = json.dumps(value)

        nx.write_graphml(G_copy, path)
        logger.info(f"Graph saved as GraphML: {path}")

    def _save_json(self, path: str):
        from networkx.readwrite import json_graph

        data = json_graph.node_link_data(G=self.graph)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Graph saved as JSON: {path}")

    def get_stats(self) -> dict:
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
