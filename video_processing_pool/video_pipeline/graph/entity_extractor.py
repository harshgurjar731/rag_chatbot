"""
LLM-based entity and relationship extraction.

Uses the Mistral API to extract structured entities and relationships
from video chunk captions and transcripts.
"""

import json
import logging
import os
import time
from typing import Optional

from .config import GraphConfig
from .models import ExtractedEntity, ExtractedRelationship, ExtractionResult

logger = logging.getLogger(__name__)

# Prompt template for entity/relationship extraction
EXTRACTION_PROMPT = """You are an expert at extracting structured entities and relationships from video descriptions.

Given the following video chunk data (a caption describing the visual content and an audio transcript), extract all meaningful entities and the relationships between them.

**Entity types to extract:** Person, Vehicle, Location, Object, Action, Event

**Relationship types to use:** INTERACTS_WITH, LOCATED_AT, PART_OF, OCCURS_AT, INVOLVES, PERFORMS, USES, NEAR

**Rules:**
1. Each entity should have a name, type, and brief description.
2. Relationships should connect two entities by name.
3. Be specific — prefer "CNC machine" over "machine".
4. Merge duplicates — if two phrases refer to the same thing, use one name.
5. Include temporal information in descriptions when available.

**Video Chunk (timestamps: {start}s – {end}s):**

VISUAL CAPTION:
{caption}

AUDIO TRANSCRIPT:
{transcript}

DETECTED OBJECTS:
{objects}

**Output ONLY valid JSON in this exact format, nothing else:**
{{
  "entities": [
    {{"name": "...", "type": "Person|Vehicle|Location|Object|Action|Event", "description": "..."}}
  ],
  "relationships": [
    {{"source": "...", "target": "...", "type": "INTERACTS_WITH|LOCATED_AT|PART_OF|OCCURS_AT|INVOLVES|PERFORMS|USES|NEAR", "description": "..."}}
  ]
}}"""


class LLMEntityExtractor:
    """
    Extracts entities and relationships from video chunk data using an LLM.

    Uses the Mistral API (same key as the ingestion pipeline) to call
    a small, fast model for structured JSON extraction.
    """

    def __init__(self, config: GraphConfig):
        self.config = config
        self._client = None

    def _get_client(self):
        """Lazily initialize the Mistral client."""
        if self._client is None:
            from dotenv import load_dotenv
            load_dotenv()

            api_key = os.getenv("MISTRAL_API_KEY")
            if not api_key:
                raise ValueError(
                    "MISTRAL_API_KEY not found. Set it in .env or environment."
                )

            from mistralai import Mistral
            self._client = Mistral(api_key=api_key)
            logger.info(f"Mistral client initialized for entity extraction")
        return self._client

    def _format_objects(self, cv_metadata: dict) -> str:
        """Format CV metadata objects into a readable string."""
        if not cv_metadata or not cv_metadata.get("objects"):
            return "None detected"

        lines = []
        for obj in cv_metadata["objects"]:
            cls = obj.get("class", "unknown")
            track_id = obj.get("track_id", "?")
            conf = obj.get("confidence", 0)
            frames = obj.get("frames_seen", [])
            lines.append(
                f"- {cls} (track_id={track_id}, "
                f"confidence={conf:.2f}, frames={frames})"
            )
        return "\n".join(lines)

    def extract(self, chunk: dict) -> ExtractionResult:
        """
        Extract entities and relationships from a single video chunk.

        Args:
            chunk: A chunk dict from the ingestion results JSON.

        Returns:
            ExtractionResult with lists of entities and relationships.
        """
        chunk_id = chunk.get("chunk_id", -1)

        # Build prompt inputs
        caption = ""
        if chunk.get("caption") and chunk["caption"].get("text"):
            caption = chunk["caption"]["text"]

        transcript = ""
        if chunk.get("transcript") and chunk["transcript"].get("full_text"):
            transcript = chunk["transcript"]["full_text"]

        objects_str = self._format_objects(chunk.get("cv_metadata", {}))

        if not caption and not transcript:
            logger.warning(f"Chunk {chunk_id}: no text data, skipping.")
            return ExtractionResult(chunk_id=chunk_id)

        # Build the prompt
        prompt = EXTRACTION_PROMPT.format(
            start=chunk.get("start_timestamp", 0),
            end=chunk.get("end_timestamp", 0),
            caption=caption or "N/A",
            transcript=transcript or "N/A",
            objects=objects_str,
        )

        # Call the LLM
        try:
            response_text = self._call_llm(prompt)
            return self._parse_response(response_text, chunk_id)
        except Exception as e:
            logger.error(
                f"Chunk {chunk_id}: LLM extraction failed: {e}"
            )
            return ExtractionResult(chunk_id=chunk_id)

    def _call_llm(self, prompt: str, retries: int = 3) -> str:
        """
        Call the Mistral API with retry logic.

        Args:
            prompt: The extraction prompt.
            retries: Number of retry attempts.

        Returns:
            The raw text response from the LLM.
        """
        client = self._get_client()

        for attempt in range(retries):
            try:
                response = client.chat.complete(
                    model=self.config.llm_model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.config.llm_max_tokens,
                    temperature=self.config.llm_temperature,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content.strip()

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate" in error_str.lower():
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        f"Rate limited, retrying in {wait}s "
                        f"(attempt {attempt + 1}/{retries})"
                    )
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError(f"LLM call failed after {retries} retries")

    def _parse_response(
        self, response_text: str, chunk_id: int
    ) -> ExtractionResult:
        """
        Parse the LLM JSON response into structured objects.

        Args:
            response_text: Raw JSON string from the LLM.
            chunk_id: The source chunk ID.

        Returns:
            ExtractionResult with parsed entities and relationships.
        """
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(
                f"Chunk {chunk_id}: Failed to parse LLM JSON: {e}"
            )
            logger.debug(f"Raw response: {response_text[:500]}")
            return ExtractionResult(chunk_id=chunk_id)

        entities = []
        for ent in data.get("entities", []):
            entities.append(ExtractedEntity(
                name=ent.get("name", ""),
                entity_type=ent.get("type", "Object"),
                description=ent.get("description", ""),
                source_chunk_id=chunk_id,
            ))

        relationships = []
        for rel in data.get("relationships", []):
            relationships.append(ExtractedRelationship(
                source=rel.get("source", ""),
                target=rel.get("target", ""),
                relationship_type=rel.get("type", "RELATED_TO"),
                description=rel.get("description", ""),
                source_chunk_id=chunk_id,
            ))

        logger.info(
            f"Chunk {chunk_id}: Extracted {len(entities)} entities, "
            f"{len(relationships)} relationships"
        )
        return ExtractionResult(
            chunk_id=chunk_id,
            entities=entities,
            relationships=relationships,
        )

    def extract_batch(
        self,
        chunk_results: list[dict],
        delay_seconds: float = 2.0,
    ) -> list[ExtractionResult]:
        """
        Extract entities from multiple chunks with rate limiting.

        Args:
            chunk_results: List of chunk dicts.
            delay_seconds: Pause between API calls.

        Returns:
            List of ExtractionResult objects.
        """
        results = []
        total = len(chunk_results)

        for i, chunk in enumerate(chunk_results):
            logger.info(
                f"Extracting entities from chunk {i + 1}/{total} "
                f"(chunk_id={chunk.get('chunk_id', '?')})"
            )
            result = self.extract(chunk)
            results.append(result)

            # Rate limit delay (skip after last chunk)
            if i < total - 1:
                time.sleep(delay_seconds)

        return results
