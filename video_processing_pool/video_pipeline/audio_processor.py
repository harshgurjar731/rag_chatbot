"""
Audio Processor — Voxtral Mini Transcribe via Mistral API.

Extracts audio from video chunks (as MP3) and transcribes
using Mistral's `/v1/audio/transcriptions` endpoint.
"""

import logging
import subprocess
import time
from pathlib import Path

from .config import AudioProcessingConfig
from .models import TranscriptResult, TranscriptSegment
from .stream_handler import FFMPEG

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Extracts audio and transcribes via Mistral's Voxtral Mini Transcribe API."""

    def __init__(self, config: AudioProcessingConfig, api_key: str = "", temp_dir: str = "./data/temp"):
        self.config = config
        self.api_key = api_key
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._client = None

    def _get_client(self):
        """Lazily initialize the Mistral API client."""
        if self._client is None:
            from mistralai import Mistral

            if not self.api_key:
                raise ValueError(
                    "MISTRAL_API_KEY not set. Provide it via the "
                    "MISTRAL_API_KEY environment variable."
                )
            self._client = Mistral(api_key=self.api_key)
        return self._client

    def extract_audio(self, video_path: str, output_path: str = None) -> str:
        """
        Extract audio from a video file as MP3.

        Args:
            video_path: Path to the video chunk.
            output_path: Optional output path. Auto-generated if not provided.

        Returns:
            Path to the extracted audio file.
        """
        if output_path is None:
            video_name = Path(video_path).stem
            output_path = str(self.temp_dir / f"{video_name}_audio.{self.config.audio_format}")

        cmd = [
            FFMPEG,
            "-i", str(video_path),
            "-ac", "1",                              # mono
            "-ar", str(self.config.sample_rate),      # sample rate
            "-q:a", "2",                              # quality (for MP3)
            "-y",                                     # overwrite
            str(output_path),
        ]

        logger.debug(f"Extracting audio: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            if "Output file does not contain any stream" in e.stderr:
                logger.info(f"No audio stream found in {video_path}")
                return None
            logger.error(f"Audio extraction failed: {e.stderr}")
            raise RuntimeError(f"Audio extraction failed: {e.stderr}") from e

        logger.info(f"Extracted audio: {output_path}")
        return output_path

    def transcribe(
        self,
        audio_path: str,
        chunk_start_time: float = 0.0,
    ) -> TranscriptResult:
        """
        Transcribe an audio file using Voxtral Mini Transcribe.

        Args:
            audio_path: Path to the audio file (MP3/WAV).
            chunk_start_time: Absolute start time of this chunk for timestamp alignment.

        Returns:
            TranscriptResult with aligned timestamps.
        """
        client = self._get_client()

        # Read audio file
        audio_file_path = Path(audio_path)
        if not audio_file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing: {audio_path}")

        with open(audio_path, "rb") as f:
            audio_content = f.read()

        # Build API request params
        request_params = {
            "model": self.config.model,
            "file": {
                "file_name": audio_file_path.name,
                "content": audio_content,
            },
            "timestamp_granularities": self.config.timestamp_granularities,
        }

        # Add optional params
        # if self.config.diarization:
        #     request_params["diarize"] = True
        if self.config.language:
            request_params["language"] = self.config.language

        # Call Mistral API with retry for rate limiting (free tier = 1 RPS)
        max_retries = 3
        base_delay = 2  # seconds

        for attempt in range(max_retries + 1):
            try:
                result = client.audio.transcriptions.complete(**request_params)
                break  # Success
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Rate limited (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Rate limited after {max_retries + 1} attempts")
                        raise RuntimeError(
                            f"Voxtral transcription rate limited after {max_retries + 1} attempts"
                        ) from e
                else:
                    logger.error(f"Transcription API call failed: {e}")
                    raise RuntimeError(f"Voxtral transcription failed: {e}") from e

        # Parse response and align timestamps
        segments = []
        if hasattr(result, "segments") and result.segments:
            for seg in result.segments:
                segment = TranscriptSegment(
                    text=seg.text.strip() if hasattr(seg, "text") else "",
                    start=chunk_start_time + (seg.start if hasattr(seg, "start") else 0.0),
                    end=chunk_start_time + (seg.end if hasattr(seg, "end") else 0.0),
                    speaker=getattr(seg, "speaker", None),
                )
                segments.append(segment)

        full_text = result.text if hasattr(result, "text") else ""

        transcript = TranscriptResult(
            engine="mistral_api",
            model=self.config.model,
            segments=segments,
            full_text=full_text.strip(),
        )

        logger.info(
            f"Transcription complete: {len(segments)} segments, "
            f"{len(full_text)} chars"
        )
        return transcript

    def process_chunk(
        self,
        video_path: str,
        chunk_start_time: float = 0.0,
    ) -> TranscriptResult:
        """
        Full audio pipeline: extract audio + transcribe.

        Args:
            video_path: Path to the video chunk.
            chunk_start_time: Absolute start time for timestamp alignment.

        Returns:
            TranscriptResult with aligned timestamps.
        """
        if not self.config.enabled:
            logger.info("Audio processing disabled, skipping")
            return TranscriptResult()

        # Step 1: Extract audio
        audio_path = self.extract_audio(video_path)
        if not audio_path:
            return TranscriptResult()

        # Step 2: Transcribe
        try:
            transcript = self.transcribe(audio_path, chunk_start_time)
        finally:
            # Clean up temp audio file
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass

        return transcript
