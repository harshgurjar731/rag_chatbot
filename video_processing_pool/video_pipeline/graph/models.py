"""
Data models for the knowledge graph pipeline.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractedEntity:
    """An entity extracted from text by the LLM."""
    name: str
    entity_type: str             # Person, Vehicle, Location, Object, Action, Event
    description: str = ""
    source_chunk_id: int = -1
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.entity_type,
            "description": self.description,
            "source_chunk_id": self.source_chunk_id,
        }


@dataclass
class ExtractedRelationship:
    """A relationship between two entities, extracted by the LLM."""
    source: str                  # Entity name (source)
    target: str                  # Entity name (target)
    relationship_type: str       # INTERACTS_WITH, LOCATED_AT, etc.
    description: str = ""
    source_chunk_id: int = -1
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.relationship_type,
            "description": self.description,
            "source_chunk_id": self.source_chunk_id,
        }


@dataclass
class ExtractionResult:
    """Complete extraction result for one video chunk."""
    chunk_id: int
    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
