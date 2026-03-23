"""
Pipeline Orchestrator — Main entry point for video ingestion.

Coordinates all pipeline components: chunking, frame selection,
audio transcription, CV detection, and VLM captioning.
"""

import json
import logging
import argparse
import sys
from pathlib import Path
from typing import Optional

from .config import PipelineConfig
from .models import ChunkResult
from .stream_handler import StreamHandler
from .video_processor import VideoProcessor
from .audio_processor import AudioProcessor
from .cv_pipeline import CVPipeline
from .vlm_captioner import VLMCaptioner

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Main orchestrator for the video ingestion pipeline.

    Processes a video file through all pipeline stages:
    1. Chunking (Stream Handler)
    2. Frame Selection (Video Processor)
    3. Audio Transcription (Voxtral Mini Transcribe via Mistral API)
    4. Object Detection & Tracking (YOLO + ByteTrack)
    5. Dense Captioning (Mistral Large via Mistral API)
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        config.ensure_directories()

        # Initialize components
        self.stream_handler = StreamHandler(
            config.stream_handler, temp_dir=config.temp_dir
        )
        self.video_processor = VideoProcessor(config.video_processing)
        self.audio_processor = AudioProcessor(
            config.audio_processing, api_key=config.mistral_api_key, temp_dir=config.temp_dir
        )
        self.cv_pipeline = CVPipeline(config.cv_pipeline)
        self.vlm_captioner = VLMCaptioner(config.vlm, api_key=config.mistral_api_key)

        logger.info("Ingestion pipeline initialized")

    def process_chunk(self, chunk_metadata) -> ChunkResult:
        """
        Process a single video chunk through all pipeline stages.

        Args:
            chunk_metadata: ChunkMetadata from the stream handler.

        Returns:
            ChunkResult with transcript, caption, and CV metadata.
        """
        chunk_id = chunk_metadata.chunk_id
        video_path = chunk_metadata.chunk_path
        start_time = chunk_metadata.start_timestamp

        logger.info(
            f"Processing chunk {chunk_id}: {video_path} "
            f"({start_time:.1f}s - {chunk_metadata.end_timestamp:.1f}s)"
        )

        # --- Stage 1: Audio Processing ---
        transcript = None
        if self.config.audio_processing.enabled:
            try:
                logger.info(f"  [Chunk {chunk_id}] Transcribing audio...")
                transcript = self.audio_processor.process_chunk(video_path, start_time)
                logger.info(
                    f"  [Chunk {chunk_id}] Transcription: "
                    f"{len(transcript.segments)} segments"
                )
            except Exception as e:
                logger.error(f"  [Chunk {chunk_id}] Audio processing failed: {e}")

        # --- Stage 2: Frame Selection ---
        try:
            logger.info(f"  [Chunk {chunk_id}] Extracting frames...")
            frames = self.video_processor.extract_frames(video_path, start_time)
            logger.info(f"  [Chunk {chunk_id}] Selected {len(frames)} frames")
        except Exception as e:
            logger.error(f"  [Chunk {chunk_id}] Frame extraction failed: {e}")
            frames = []

        # --- Stage 3: CV Pipeline ---
        cv_metadata = None
        if self.config.cv_pipeline.enabled and frames:
            try:
                logger.info(f"  [Chunk {chunk_id}] Running CV pipeline...")
                cv_metadata = self.cv_pipeline.detect_objects(frames)
                logger.info(
                    f"  [Chunk {chunk_id}] CV: "
                    f"{len(cv_metadata.objects)} objects detected"
                )

                # SOM annotation for VLM
                if self.config.cv_pipeline.som_prompting:
                    frames = self.cv_pipeline.annotate_frames(frames, cv_metadata)
            except Exception as e:
                logger.error(f"  [Chunk {chunk_id}] CV pipeline failed: {e}")

        # --- Stage 4: VLM Captioning ---
        caption = None
        if frames:
            try:
                logger.info(f"  [Chunk {chunk_id}] Generating VLM caption...")
                caption = self.vlm_captioner.caption_frames(frames)
                logger.info(
                    f"  [Chunk {chunk_id}] Caption: {len(caption.text)} chars"
                )
            except Exception as e:
                logger.error(f"  [Chunk {chunk_id}] VLM captioning failed: {e}")

        # --- Build result ---
        result = ChunkResult(
            chunk_id=chunk_id,
            stream_id=chunk_metadata.stream_id,
            source_video=chunk_metadata.source_video,
            start_timestamp=chunk_metadata.start_timestamp,
            end_timestamp=chunk_metadata.end_timestamp,
            duration_seconds=chunk_metadata.end_timestamp - chunk_metadata.start_timestamp,
            transcript=transcript,
            caption=caption,
            cv_metadata=cv_metadata,
        )

        logger.info(f"  [Chunk {chunk_id}] Processing complete")
        return result

    def ingest(
        self,
        video_path: str,
        stream_id: str = "default",
        output_path: Optional[str] = None,
    ) -> list[ChunkResult]:
        """
        Ingest a complete video file.

        Args:
            video_path: Path to the input video file.
            stream_id: Identifier for the video source.
            output_path: Optional path to save results JSON. Defaults to output_dir.

        Returns:
            List of ChunkResult objects, one per chunk.
        """
        logger.info(f"Starting ingestion: {video_path}")

        # Step 1: Chunk the video
        chunks = self.stream_handler.chunk_video(video_path, stream_id)
        logger.info(f"Video split into {len(chunks)} chunks")

        # Step 2: Process each chunk using a thread pool for parallel API calls and processing
        from concurrent.futures import ThreadPoolExecutor
        
        # We use a configurable number of workers (default 4) to balance CPU load with API concurrency
        max_workers = getattr(self.config, "max_parallel_workers", 4)
        logger.info(f"Processing {len(chunks)} chunks in parallel with {max_workers} workers...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # We use list(executor.map) to block until all chunks are processed in order
            results = list(executor.map(self.process_chunk, chunks))

        # Step 3: Save results
        if output_path is None:
            output_path = str(
                Path(self.config.output_dir) / f"{stream_id}_results.json"
            )

        results_data = [r.to_dict() for r in results]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)

        logger.info(f"\nResults saved to: {output_path}")
        logger.info(f"Total chunks processed: {len(results)}")

        # Cleanup temp files
        self.stream_handler.cleanup(stream_id)

        return results


def setup_logging(verbose: bool = False):
    """Configure logging for the pipeline."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    """CLI entry point for the ingestion pipeline."""
    parser = argparse.ArgumentParser(
        description="Video Ingestion Pipeline — Process videos into structured data"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input video file",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path to save results JSON (default: ./data/output/<stream_id>_results.json)",
    )
    parser.add_argument(
        "--stream-id", "-s",
        default="default",
        help="Identifier for the video source (default: 'default')",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Disable audio transcription",
    )
    parser.add_argument(
        "--no-cv",
        action="store_true",
        help="Disable CV pipeline (object detection/tracking)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Load configuration
    if args.config:
        config = PipelineConfig.from_yaml(args.config)
    else:
        config = PipelineConfig.from_env()

    # Apply CLI overrides
    if args.no_audio:
        config.audio_processing.enabled = False
    if args.no_cv:
        config.cv_pipeline.enabled = False

    # Validate
    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    if not config.mistral_api_key:
        logger.error(
            "MISTRAL_API_KEY not set. Set it via the MISTRAL_API_KEY environment variable.\n"
            "Example: set MISTRAL_API_KEY=your_key_here"
        )
        sys.exit(1)

    # Run pipeline
    pipeline = IngestionPipeline(config)
    results = pipeline.ingest(
        video_path=args.input,
        stream_id=args.stream_id,
        output_path=args.output,
    )

    logger.info(f"\nDone! Processed {len(results)} chunks.")


if __name__ == "__main__":
    main()
