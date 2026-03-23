"""
Data models / schemas for the ingestion pipeline.

These dataclasses define the structured output produced at each pipeline stage.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TranscriptSegment:
    """A single segment of transcribed speech."""
    text: str
    start: float  # absolute timestamp in seconds
    end: float    # absolute timestamp in seconds
    speaker: Optional[int] = None  # speaker ID from diarization


@dataclass
class TranscriptResult:
    """Complete transcription result for one video chunk."""
    engine: str = "mistral_api"
    model: str = "voxtral-mini-latest"
    segments: list[TranscriptSegment] = field(default_factory=list)
    full_text: str = ""

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "model": self.model,
            "segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "speaker": seg.speaker,
                }
                for seg in self.segments
            ],
            "full_text": self.full_text,
        }


@dataclass
class DetectedObject:
    """A single detected object from CV pipeline."""
    class_name: str
    bbox: list[float]  # [x1, y1, x2, y2]
    confidence: float
    track_id: Optional[int] = None
    frames_seen: list[int] = field(default_factory=list)


@dataclass
class CVMetadata:
    """Computer vision metadata for one video chunk."""
    detector: str = "yolov8x"
    tracker: str = "bytetrack"
    objects: list[DetectedObject] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "detector": self.detector,
            "tracker": self.tracker,
            "objects": [
                {
                    "class": obj.class_name,
                    "bbox": obj.bbox,
                    "confidence": obj.confidence,
                    "track_id": obj.track_id,
                    "frames_seen": obj.frames_seen,
                }
                for obj in self.objects
            ],
        }


@dataclass
class CaptionResult:
    """VLM captioning result for one video chunk."""
    engine: str = "mistral_api"
    model: str = "mistral-large-2512"
    text: str = ""

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "model": self.model,
            "text": self.text,
        }


@dataclass
class ChunkMetadata:
    """Metadata for a single video chunk (output of the stream handler)."""
    chunk_id: int
    chunk_path: str
    start_timestamp: float
    end_timestamp: float
    stream_id: str
    source_video: str

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "chunk_path": self.chunk_path,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "stream_id": self.stream_id,
            "source_video": self.source_video,
        }


@dataclass
class ChunkResult:
    """Complete ingestion result for one video chunk — the final output."""
    chunk_id: int
    stream_id: str
    source_video: str
    start_timestamp: float
    end_timestamp: float
    duration_seconds: float
    transcript: Optional[TranscriptResult] = None
    caption: Optional[CaptionResult] = None
    cv_metadata: Optional[CVMetadata] = None

    def to_dict(self) -> dict:
        result = {
            "chunk_id": self.chunk_id,
            "stream_id": self.stream_id,
            "source_video": self.source_video,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "duration_seconds": self.duration_seconds,
        }
        if self.transcript:
            result["transcript"] = self.transcript.to_dict()
        if self.caption:
            result["caption"] = self.caption.to_dict()
        if self.cv_metadata:
            result["cv_metadata"] = self.cv_metadata.to_dict()
        return result
