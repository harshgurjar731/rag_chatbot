"""
CV Pipeline — Object detection and tracking.

Runs YOLOv8 object detection and ByteTrack multi-object tracking
on selected frames to produce structured CV metadata.
"""

import logging
from typing import Optional

import numpy as np
from PIL import Image

from .config import CVPipelineConfig
from .models import CVMetadata, DetectedObject

logger = logging.getLogger(__name__)


class CVPipeline:
    """Object detection + tracking using YOLO and ByteTrack."""

    def __init__(self, config: CVPipelineConfig):
        self.config = config
        self._model = None

    def _load_model(self):
        """Lazily load the YOLO model."""
        if self._model is None:
            from ultralytics import YOLO

            model_name = f"{self.config.detector}.pt"
            logger.info(f"Loading YOLO model: {model_name}")
            self._model = YOLO(model_name)
        return self._model

    def detect_objects(
        self,
        frames: list[dict],
    ) -> CVMetadata:
        """
        Run object detection and tracking on a list of frames.

        Args:
            frames: List of dicts from VideoProcessor.extract_frames(), each with:
                - "frame": PIL Image
                - "timestamp": float
                - "frame_index": int

        Returns:
            CVMetadata with detected and tracked objects.
        """
        if not self.config.enabled:
            logger.info("CV pipeline disabled, skipping")
            return CVMetadata()

        model = self._load_model()

        # Convert PIL images to numpy arrays for YOLO
        np_frames = []
        for frame_data in frames:
            img = frame_data["frame"]
            if isinstance(img, Image.Image):
                np_frames.append(np.array(img))
            else:
                np_frames.append(img)

        # Run detection with tracking
        # YOLO's `track()` method uses ByteTrack or BoT-SORT internally
        try:
            results = model.track(
                np_frames,
                conf=self.config.confidence_threshold,
                tracker=f"{self.config.tracker}.yaml",
                persist=True,
                verbose=False,
            )
        except Exception as e:
            logger.warning(f"Tracking failed ({e}), falling back to detection-only")
            results = model(
                np_frames,
                conf=self.config.confidence_threshold,
                verbose=False,
            )

        # Aggregate detections across frames
        # Track objects by their track_id and accumulate frames_seen
        tracked_objects: dict[int, DetectedObject] = {}
        detection_id_counter = 0

        for frame_idx, result in enumerate(results):
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id]

                # Filter by classes of interest (if configured)
                if self.config.classes_of_interest:
                    # Allow partial matching (e.g., "vehicle" matches "car", "truck", etc.)
                    vehicle_types = {"car", "truck", "bus", "motorcycle", "bicycle"}
                    if class_name not in self.config.classes_of_interest:
                        if "vehicle" in self.config.classes_of_interest and class_name in vehicle_types:
                            pass  # allow vehicle subtypes
                        else:
                            continue

                bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                confidence = float(box.conf[0])
                track_id = int(box.id[0]) if box.id is not None else detection_id_counter

                if track_id in tracked_objects:
                    # Update existing tracked object
                    obj = tracked_objects[track_id]
                    obj.frames_seen.append(frame_idx)
                    # Keep the highest confidence detection's bbox
                    if confidence > obj.confidence:
                        obj.bbox = bbox
                        obj.confidence = confidence
                else:
                    # New object
                    tracked_objects[track_id] = DetectedObject(
                        class_name=class_name,
                        bbox=bbox,
                        confidence=confidence,
                        track_id=track_id,
                        frames_seen=[frame_idx],
                    )
                    detection_id_counter += 1

        cv_metadata = CVMetadata(
            detector=self.config.detector,
            tracker=self.config.tracker,
            objects=list(tracked_objects.values()),
        )

        logger.info(
            f"CV pipeline: detected {len(cv_metadata.objects)} tracked objects "
            f"across {len(frames)} frames"
        )
        return cv_metadata

    def annotate_frames(
        self,
        frames: list[dict],
        cv_metadata: CVMetadata,
    ) -> list[dict]:
        """
        Overlay SOM (Set-of-Marks) annotations on frames for VLM input.

        Draws numbered bounding boxes and labels on each frame to help
        the VLM reference specific objects.

        Args:
            frames: List of frame dicts from VideoProcessor.
            cv_metadata: Detection results.

        Returns:
            Updated frame dicts with annotated PIL Images.
        """
        if not self.config.som_prompting:
            return frames

        import cv2

        annotated_frames = []
        for frame_idx, frame_data in enumerate(frames):
            img = np.array(frame_data["frame"])

            for obj in cv_metadata.objects:
                if frame_idx not in obj.frames_seen:
                    continue

                x1, y1, x2, y2 = [int(v) for v in obj.bbox]
                label = f"#{obj.track_id} {obj.class_name}"

                # Draw bounding box
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Draw label background
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                cv2.rectangle(img, (x1, y1 - th - 8), (x1 + tw + 4, y1), (0, 255, 0), -1)

                # Draw label text
                cv2.putText(
                    img, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1,
                )

            annotated_frames.append({
                "frame": Image.fromarray(img),
                "timestamp": frame_data["timestamp"],
                "frame_index": frame_data["frame_index"],
            })

        logger.info(f"Annotated {len(annotated_frames)} frames with SOM overlays")
        return annotated_frames
