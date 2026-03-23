"""
Configuration dataclasses for the knowledge graph pipeline.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GraphConfig:
    """Configuration for the knowledge graph pipeline."""
    enabled: bool = True
    entity_extraction: str = "llm"     # options: llm
    persist_dir: str = "./data/graph"
    output_format: str = "graphml"     # options: graphml, json
    node_types: list[str] = field(default_factory=lambda: [
        "VideoChunk", "Person", "Vehicle", "Location",
        "Object", "Action", "Event",
    ])
    edge_types: list[str] = field(default_factory=lambda: [
        "APPEARS_IN", "MENTIONED_IN", "FOLLOWED_BY",
        "CO_OCCURS_WITH", "INTERACTS_WITH", "LOCATED_AT",
        "PART_OF", "OCCURS_AT", "INVOLVES",
    ])
    deduplicate_nodes: bool = True
    duplicate_score_threshold: float = 0.9
    llm_model: str = "mistral-small-latest"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    @classmethod
    def from_dict(cls, data: dict) -> "GraphConfig":
        """Create config from a YAML-parsed dictionary."""
        if not data:
            return cls()

        return cls(
            enabled=data.get("enabled", True),
            entity_extraction=data.get("entity_extraction", "llm"),
            persist_dir=data.get("persist_dir", "./data/graph"),
            output_format=data.get("output_format", "graphml"),
            node_types=data.get("node_types", cls().node_types),
            edge_types=data.get("edge_types", cls().edge_types),
            deduplicate_nodes=data.get("deduplicate_nodes", True),
            duplicate_score_threshold=data.get(
                "duplicate_score_threshold", 0.9
            ),
            llm_model=data.get("llm_model", "mistral-small-latest"),
            llm_temperature=data.get("llm_temperature", 0.1),
            llm_max_tokens=data.get("llm_max_tokens", 2048),
        )
