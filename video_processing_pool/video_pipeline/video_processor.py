"""
Video Processor — Frame decoding and selection.

Decodes video chunks and selects representative frames
for downstream CV and VLM processing.
"""

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from .config import VideoProcessingConfig

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Decodes video chunks and selects representative frames."""

    def __init__(self, config: VideoProcessingConfig):
        self.config = config

    def _decode_with_opencv(self, video_path: str) -> list[np.ndarray]:
        """Decode all frames from a video using OpenCV."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)

        cap.release()
        logger.debug(f"Decoded {len(frames)} frames from {video_path}")
        return frames

    def _decode_with_decord(self, video_path: str) -> list[np.ndarray]:
        """Decode all frames from a video using decord (GPU-accelerated)."""
        try:
            from decord import VideoReader, cpu, gpu

            ctx = gpu(0) if self.config.use_gpu_decode else cpu(0)
            vr = VideoReader(video_path, ctx=ctx)
            # Get all frames as numpy arrays
            frames = [vr[i].asnumpy() for i in range(len(vr))]
            logger.debug(f"Decoded {len(frames)} frames from {video_path} (decord)")
            return frames
        except ImportError:
            logger.warning("decord not installed, falling back to OpenCV")
            return self._decode_with_opencv(video_path)
        except Exception as e:
            logger.warning(f"decord failed ({e}), falling back to OpenCV")
            return self._decode_with_opencv(video_path)

    def _uniform_sampling(self, frames: list[np.ndarray], n: int) -> list[int]:
        """Select N evenly spaced frame indices."""
        total = len(frames)
        if total <= n:
            return list(range(total))
        # Evenly space indices across the total frame count
        indices = [int(i * (total - 1) / (n - 1)) for i in range(n)]
        return indices

    def _scene_change_sampling(
        self, frames: list[np.ndarray], n: int, threshold: float = None
    ) -> list[int]:
        """Select frames at scene change boundaries + fill with uniform."""
        if threshold is None:
            threshold = self.config.scene_change_threshold
        scene_indices = [0]  # Always include first frame

        for i in range(1, len(frames)):
            # Compute absolute difference between consecutive frames
            diff = cv2.absdiff(frames[i], frames[i - 1])
            mean_diff = np.mean(diff)
            if mean_diff > threshold:
                scene_indices.append(i)

        # If we found fewer than N scene changes, fill with uniform sampling
        if len(scene_indices) < n:
            uniform_indices = self._uniform_sampling(frames, n)
            # Merge and deduplicate, keeping order
            combined = sorted(set(scene_indices + uniform_indices))
            # Take the top N most spread out
            if len(combined) > n:
                step = len(combined) / n
                combined = [combined[int(i * step)] for i in range(n)]
            return combined
        elif len(scene_indices) > n:
            # Too many scene changes — subsample them
            step = len(scene_indices) / n
            return [scene_indices[int(i * step)] for i in range(n)]

        return scene_indices

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize a frame to the configured resolution."""
        h, w = self.config.resize_resolution
        return cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)

    def extract_frames(
        self,
        video_path: str,
        chunk_start_time: float = 0.0,
    ) -> list[dict]:
        """
        Extract representative frames from a video chunk.
        Uses a memory-efficient streaming approach for scene_change mode.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"Could not open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames <= 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            while cap.grab():
                total_frames += 1

        if total_frames == 0:
            cap.release()
            return []

        n = self.config.frames_per_chunk

        if self.config.frame_selection == "scene_change":
            # --- STREAMING scene change detection (memory-safe) ---
            # Pass 1: Stream through all frames but only keep prev_frame
            # to compute diffs. Store (index, diff_score) pairs.
            threshold = self.config.scene_change_threshold
            scene_indices = [0]  # Always include first frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, prev_frame = cap.read()
            if not ret:
                cap.release()
                return []

            frame_idx = 1
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                diff = cv2.absdiff(frame, prev_frame)
                if np.mean(diff) > threshold:
                    scene_indices.append(frame_idx)
                prev_frame = frame
                frame_idx += 1

            # Merge with uniform if too few scene cuts
            if len(scene_indices) < n:
                uniform_ids = self._uniform_sampling(list(range(total_frames)), n)
                combined = sorted(set(scene_indices + uniform_ids))
                if len(combined) > n:
                    step = len(combined) / n
                    combined = [combined[int(i * step)] for i in range(n)]
                selected_indices = combined
            elif len(scene_indices) > n:
                step = len(scene_indices) / n
                selected_indices = [scene_indices[int(i * step)] for i in range(n)]
            else:
                selected_indices = scene_indices

            # Pass 2: Seek to only the selected indices and read them
            selected_frames = []
            for idx in selected_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    selected_frames.append(frame)
        else:
            # --- Uniform sampling (already memory-efficient) ---
            if total_frames <= n:
                selected_indices = list(range(total_frames))
            else:
                selected_indices = [int(i * (total_frames - 1) / (n - 1)) for i in range(n)]

            selected_frames = []
            for idx in selected_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    selected_frames.append(frame)

        cap.release()

        # Build output
        results = []
        for idx, frame in zip(selected_indices, selected_frames):
            resized = self._resize_frame(frame)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb)
            timestamp = chunk_start_time + (idx / fps)
            results.append({
                "frame": pil_image,
                "timestamp": timestamp,
                "frame_index": idx,
            })

        logger.info(
            f"Selected {len(results)} frames from {video_path} "
            f"(strategy: {self.config.frame_selection})"
        )
        return results

