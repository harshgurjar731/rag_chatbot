"""
Stream Handler — Video ingestion and chunking.

Accepts video files (MP4, MKV, etc.) and splits them into
fixed-duration chunks using FFmpeg segment demuxing.
"""

import logging
import os
import shutil
import subprocess
import re
from pathlib import Path

from .config import StreamHandlerConfig
from .models import ChunkMetadata

logger = logging.getLogger(__name__)


def _find_ffmpeg_binary(name: str) -> str:
    """
    Locate an FFmpeg binary (ffmpeg or ffprobe).

    Checks known install locations on Windows before falling back to PATH.
    """
    local_appdata = os.environ.get("LOCALAPPDATA", "")

    # 1. Search %LOCALAPPDATA%\ffmpeg recursively
    if local_appdata:
        ffmpeg_dir = Path(local_appdata, "ffmpeg")
        if ffmpeg_dir.exists():
            candidates = list(ffmpeg_dir.rglob(f"{name}.exe"))
            if candidates:
                logger.info(f"Found {name} at: {candidates[0]}")
                return str(candidates[0])

    # 2. Search WinGet packages directory (winget install puts FFmpeg here)
    if local_appdata:
        winget_dir = Path(local_appdata, "Microsoft", "WinGet", "Packages")
        if winget_dir.exists():
            candidates = list(winget_dir.rglob(f"{name}.exe"))
            if candidates:
                logger.info(f"Found {name} in WinGet packages: {candidates[0]}")
                return str(candidates[0])

    # 3. Refresh PATH from system environment (picks up recent installs)
    try:
        import winreg
        machine_path = winreg.QueryValueEx(
            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            "Path")[0]
        user_path = winreg.QueryValueEx(
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment"),
            "Path")[0]
        os.environ["PATH"] = machine_path + ";" + user_path
    except Exception:
        pass

    # 4. Fallback: look on PATH
    found = shutil.which(name)
    if found:
        return found

    raise FileNotFoundError(
        f"'{name}' not found. Please install FFmpeg and ensure it is on your PATH, "
        f"or install it to %LOCALAPPDATA%\\ffmpeg."
    )


FFMPEG = _find_ffmpeg_binary("ffmpeg")
FFPROBE = _find_ffmpeg_binary("ffprobe")


class StreamHandler:
    """Handles video file ingestion and chunking via FFmpeg."""

    def __init__(self, config: StreamHandlerConfig, temp_dir: str = "./data/temp"):
        self.config = config
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _validate_input(self, video_path: str) -> Path:
        """Validate the input video file exists and has a supported format."""
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if path.suffix.lstrip(".").lower() not in self.config.supported_formats:
            raise ValueError(
                f"Unsupported format '{path.suffix}'. "
                f"Supported: {self.config.supported_formats}"
            )
        return path

    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using ffprobe."""
        cmd = [
            FFPROBE,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(video_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            info = json.loads(result.stdout)
            return float(info["format"]["duration"])
        except (subprocess.CalledProcessError, KeyError, ValueError) as e:
            logger.warning(f"Could not get duration via ffprobe: {e}. Estimating from chunks.")
            return 0.0

    def _detect_split_points(self, video_path: str, total_duration: float) -> list[float]:
        """Detect optimal split points using scene cuts and audio silence."""
        scene_cuts = []
        try:
            from scenedetect import detect, ContentDetector
            scene_list = detect(str(video_path), ContentDetector())
            scene_cuts = [s[0].get_seconds() for s in scene_list if s[0].get_seconds() > 0]
            logger.info(f"Detected {len(scene_cuts)} visual scene cuts.")
        except ImportError:
            logger.warning("scenedetect not installed. Skipping visual scene detection.")
        except Exception as e:
            logger.warning(f"Scene detection failed: {e}")

        silence_cuts = []
        cmd = [
            FFMPEG,
            "-i", str(video_path),
            "-af", "silencedetect=noise=-30dB:d=1",
            "-f", "null", "-"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            import re
            matches = re.findall(r"silence_start:\s+([\d\.]+)", result.stderr)
            silence_cuts = [float(m) for m in matches]
            logger.info(f"Detected {len(silence_cuts)} audio silence cuts.")
        except Exception as e:
            logger.warning(f"Silence detection failed: {e}")

        candidates = sorted(list(set(scene_cuts + silence_cuts)))

        target = float(self.config.chunk_duration_seconds)
        min_duration = target * 0.5
        max_duration = target * 1.5

        split_points = []
        current_start = 0.0

        while current_start + max_duration < total_duration:
            ideal_split = current_start + target
            min_split = current_start + min_duration
            max_split = current_start + max_duration

            # Find candidates in [min_split, max_split]
            valid_candidates = [c for c in candidates if min_split <= c <= max_split]

            if valid_candidates:
                # Pick candidate closest to ideal_split
                best_split = min(valid_candidates, key=lambda c: abs(c - ideal_split))
                split_points.append(best_split)
                current_start = best_split
            else:
                # Fallback: strictly at ideal_split
                split_points.append(ideal_split)
                current_start = ideal_split
        
        return split_points

    def chunk_video(self, video_path: str, stream_id: str = "default") -> list[ChunkMetadata]:
        """
        Split a video file into semantic chunks using FFmpeg segment muxer.

        Args:
            video_path: Path to the input video file.
            stream_id: Identifier for the video source.

        Returns:
            List of ChunkMetadata objects, one per chunk.
        """
        input_path = self._validate_input(video_path)
        chunk_dir = self.temp_dir / stream_id
        
        # Rigorously wipe any old chunks from previous aborted runs
        if chunk_dir.exists():
            import shutil
            shutil.rmtree(chunk_dir)
            
        chunk_dir.mkdir(parents=True, exist_ok=True)

        # Get total duration for later timestamp calculation
        total_duration = self._get_video_duration(video_path)
        
        split_points = self._detect_split_points(video_path, total_duration)

        output_pattern = str(chunk_dir / "chunk_%04d.mp4")
        
        if not split_points:
            # Fallback to fixed segment time
            cmd = [
                FFMPEG,
                "-i", str(input_path),
                "-c", "copy",
                "-map", "0",
                "-segment_time", str(self.config.chunk_duration_seconds),
                "-f", "segment",
                "-reset_timestamps", "1",
                "-y",
                output_pattern,
            ]
        else:
            # Use dynamic chunking points
            times_str = ",".join([f"{p:.3f}" for p in split_points])
            cmd = [
                FFMPEG,
                "-i", str(input_path),
                "-c", "copy",
                "-map", "0",
                "-f", "segment",
                "-segment_times", times_str,
                "-reset_timestamps", "1",
                "-y",
                output_pattern,
            ]

        logger.info(f"Chunking video: {input_path} (duration: {total_duration:.1f}s)")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg chunking failed: {e.stderr}")
            raise RuntimeError(f"Video chunking failed: {e.stderr}") from e

        # Discover generated chunk files and build metadata
        chunk_files = sorted(chunk_dir.glob("chunk_*.mp4"))
        if not chunk_files:
            raise RuntimeError(f"No chunks generated from {video_path}")

        chunks = []
        current_ts = 0.0
        for i, chunk_file in enumerate(chunk_files):
            # Calculate timestamps. FFmpeg splits perfectly at keyframes, 
            # so duration is most accurate read.
            chunk_duration = self._get_video_duration(str(chunk_file))
            end_ts = current_ts + chunk_duration

            chunk = ChunkMetadata(
                chunk_id=i,
                chunk_path=str(chunk_file),
                start_timestamp=current_ts,
                end_timestamp=end_ts,
                stream_id=stream_id,
                source_video=str(input_path),
            )
            chunks.append(chunk)
            current_ts = end_ts

        logger.info(f"Generated {len(chunks)} semantic chunks from {input_path}")
        return chunks

    def cleanup(self, stream_id: str = "default"):
        """Remove temporary chunk files for a stream."""
        chunk_dir = self.temp_dir / stream_id
        if chunk_dir.exists():
            import shutil
            shutil.rmtree(chunk_dir)
            logger.info(f"Cleaned up temp dir: {chunk_dir}")
