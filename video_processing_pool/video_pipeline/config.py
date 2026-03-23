"""
Configuration management for the video ingestion pipeline.

Loads settings from environment variables and/or a YAML config file.
"""

import os
from dotenv import load_dotenv

# Load .env file (if present) so MISTRAL_API_KEY is available via os.getenv
load_dotenv(override=True)
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class StreamHandlerConfig:
    """Configuration for video chunking."""
    chunk_duration_seconds: int = 30
    max_parallel_chunks: int = 8
    supported_formats: list[str] = field(default_factory=lambda: ["mp4", "mkv", "avi", "mov"])
    supported_codecs: list[str] = field(default_factory=lambda: ["h264", "h265", "vp9"])


@dataclass
class VideoProcessingConfig:
    """Configuration for video decode and frame selection."""
    frames_per_chunk: int = 8
    frame_selection: str = "uniform"  # options: uniform, scene_change, keyframe
    scene_change_threshold: float = 30.0
    resize_resolution: tuple[int, int] = (672, 672)
    use_gpu_decode: bool = True


@dataclass
class AudioProcessingConfig:
    """Configuration for Voxtral Mini Transcribe (Mistral API)."""
    enabled: bool = True
    model: str = "voxtral-mini-latest"
    audio_format: str = "mp3"
    sample_rate: int = 16000
    response_format: str = "verbose_json"  # options: text, json, verbose_json
    timestamp_granularities: list[str] = field(default_factory=lambda: ["segment"])
    diarization: bool = True
    language: Optional[str] = None  # None = auto-detect


@dataclass
class CVPipelineConfig:
    """Configuration for YOLO + ByteTrack CV pipeline."""
    enabled: bool = True
    detector: str = "yolov8x"
    tracker: str = "bytetrack"
    confidence_threshold: float = 0.3
    som_prompting: bool = True
    classes_of_interest: list[str] = field(
        default_factory=lambda: ["person", "vehicle", "backpack", "suitcase"]
    )


@dataclass
class VLMConfig:
    """Configuration for Mistral Large VLM captioning via Mistral API."""
    model: str = "mistral-large-2512"
    max_tokens: int = 2048
    temperature: float = 0.2
    frames_per_request: int = 8
    caption_prompt: str = (
        "Analyze the following video frames and provide a detailed description:\n"
        "1. Scene setting and environment\n"
        "2. People present and their actions\n"
        "3. Objects and their states\n"
        "4. CRITICAL: Any text, signage, or tiny numbers visible (You must read and write down any specific numbers or words you see on the screen)\n"
        "5. Temporal progression across frames\n"
        "Format: Provide a structured paragraph with timestamps."
    )


@dataclass
class PipelineConfig:
    """Top-level configuration for the entire ingestion pipeline."""
    stream_handler: StreamHandlerConfig = field(default_factory=StreamHandlerConfig)
    video_processing: VideoProcessingConfig = field(default_factory=VideoProcessingConfig)
    audio_processing: AudioProcessingConfig = field(default_factory=AudioProcessingConfig)
    cv_pipeline: CVPipelineConfig = field(default_factory=CVPipelineConfig)
    vlm: VLMConfig = field(default_factory=VLMConfig)

    # Mistral API key (shared by audio processing and VLM captioning)
    mistral_api_key: str = ""

    # Pipeline settings
    inter_chunk_delay: float = 2.0

    # Paths
    output_dir: str = "./data/output"
    temp_dir: str = "./data/temp"

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        """Load configuration from a YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        config = cls()

        if "stream_handler" in data:
            config.stream_handler = StreamHandlerConfig(**data["stream_handler"])
        if "video_processing" in data:
            vp = data["video_processing"]
            if "resize_resolution" in vp:
                vp["resize_resolution"] = tuple(vp["resize_resolution"])
            config.video_processing = VideoProcessingConfig(**vp)
        if "audio_processing" in data:
            config.audio_processing = AudioProcessingConfig(**data["audio_processing"])
        if "cv_pipeline" in data:
            config.cv_pipeline = CVPipelineConfig(**data["cv_pipeline"])
        if "vlm" in data:
            config.vlm = VLMConfig(**data["vlm"])
        if "output_dir" in data:
            config.output_dir = data["output_dir"]
        if "temp_dir" in data:
            config.temp_dir = data["temp_dir"]
        if "inter_chunk_delay" in data:
            config.inter_chunk_delay = float(data["inter_chunk_delay"])

        # Load API key from environment variable
        mistral_key = os.getenv("MISTRAL_API_KEY", "")
        config.mistral_api_key = mistral_key

        return config

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create config with environment variable overrides."""
        config = cls()
        # Load API key from environment variable
        config.mistral_api_key = os.getenv("MISTRAL_API_KEY", "")
        config.output_dir = os.getenv("OUTPUT_DIR", config.output_dir)
        config.temp_dir = os.getenv("TEMP_DIR", config.temp_dir)
        return config

    def ensure_directories(self):
        """Create output and temp directories if they don't exist."""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
