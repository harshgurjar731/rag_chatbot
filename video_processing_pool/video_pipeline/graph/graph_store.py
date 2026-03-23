"""
Graph persistence utilities.

Provides load/save functions for the NetworkX knowledge graph.
"""

import json
import logging
import os
from typing import Optional

import networkx as nx

logger = logging.getLogger(__name__)


class GraphStore:
    """
    Handles loading, saving, and clearing a NetworkX knowledge graph.
    """

    @staticmethod
    def clear(path: str):
        """
        Delete the graph file from disk.

        Args:
            path: Path to the .graphml or .json file.
        """
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Deleted graph file at: {path}")
            except Exception as e:
                logger.warning(f"Failed to delete graph file: {e}")

    @staticmethod
    def load_graphml(path: str) -> nx.DiGraph:
        """
        Load a graph from a GraphML file.

        Args:
            path: Path to the .graphml file.

        Returns:
            A NetworkX DiGraph.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Graph file not found: {path}")

        G = nx.read_graphml(path)
        logger.info(
            f"Loaded graph from {path}: "
            f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
        )
        return G

    @staticmethod
    def load_json(path: str) -> nx.DiGraph:
        """
        Load a graph from a JSON file (node-link format).

        Args:
            path: Path to the .json file.

        Returns:
            A NetworkX DiGraph.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Graph file not found: {path}")

        from networkx.readwrite import json_graph

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        G = json_graph.node_link_graph(data=data)
        logger.info(
            f"Loaded graph from {path}: "
            f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
        )
        return G

    @staticmethod
    def load(path: str) -> nx.DiGraph:
        """
        Load a graph, auto-detecting format from file extension.

        Args:
            path: Path to the graph file (.graphml or .json).

        Returns:
            A NetworkX DiGraph.
        """
        if path.endswith(".graphml"):
            return GraphStore.load_graphml(path)
        elif path.endswith(".json"):
            return GraphStore.load_json(path)
        else:
            raise ValueError(
                f"Unsupported graph format: {path}. "
                f"Use .graphml or .json."
            )

    @staticmethod
    def save_graphml(G: nx.DiGraph, path: str):
        """Save graph as GraphML."""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # GraphML doesn't support list attributes
        G_copy = G.copy()
        for node_id in G_copy.nodes:
            for key, value in list(G_copy.nodes[node_id].items()):
                if isinstance(value, list):
                    G_copy.nodes[node_id][key] = str(value)

        nx.write_graphml(G_copy, path)
        logger.info(f"Graph saved as GraphML: {path}")

    @staticmethod
    def save_json(G: nx.DiGraph, path: str):
        """Save graph as JSON (node-link format)."""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        from networkx.readwrite import json_graph

        data = json_graph.node_link_data(G=G)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Graph saved as JSON: {path}")
