"""
Video Worker Process.

This script runs as a standalone worker process managed by the video processing pool.
It listens for video processing jobs on Redis (video_processing:inbox), processes them
using the Video_Query pipeline (chunking, ASR, CV, VLM, embedding, graph), and updates
the database/vector store.
"""

import os
import sys
import redis
import asyncio
import json
import uuid
import time
import traceback
from pathlib import Path
from sqlmodel import create_engine, Session, select
from typing import List

# Ensure we can import from local modules
sys.path.append(os.getcwd())

# Imports
from config import REDIS_HOST, DATABASE_URL, MISTRAL_API_KEY, OUTPUT_DIR, TEMP_DIR, GRAPH_DIR, DATA_DIRECTORY
from models.datastore import DataStore, update_datastore
from models.FileRecord import DocumentRecord, ChunkRecord, update_document_record
from langchain_core.documents import Document

# Video pipeline imports
from video_pipeline.pipeline_config import PipelineConfig
from video_pipeline.pipeline import IngestionPipeline, setup_logging

# Enable verbose terminal logging
setup_logging(verbose=True)

# Redis Connection
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# DB Engine
engine = create_engine(DATABASE_URL)


def build_pipeline_config(job_data: dict) -> PipelineConfig:
    """
    Build a PipelineConfig from job_data (sent from frontend via backend).
    Uses defaults from config.yaml, overridden by job_data.
    """
    config_path = os.path.join(os.getcwd(), "config.yaml")
    
    if os.path.exists(config_path):
        config = PipelineConfig.from_yaml(config_path)
    else:
        config = PipelineConfig.from_env()
    
    # Override with API key 
    config.mistral_api_key = MISTRAL_API_KEY
    
    # Override paths with env vars
    config.output_dir = OUTPUT_DIR
    config.temp_dir = TEMP_DIR
    
    # Ensure directories exist
    config.ensure_directories()
    Path(GRAPH_DIR).mkdir(parents=True, exist_ok=True)
    
    # Override with job-specific settings
    settings = job_data.get("settings", {})
    
    # Stream handler / video processing
    if "chunk_duration_seconds" in settings:
        config.stream_handler.chunk_duration_seconds = int(settings["chunk_duration_seconds"])
    if "frames_per_chunk" in settings:
        config.video_processing.frames_per_chunk = int(settings["frames_per_chunk"])
    if "frame_selection" in settings:
        config.video_processing.frame_selection = settings["frame_selection"]
    if "scene_change_threshold" in settings:
        config.video_processing.scene_change_threshold = float(settings["scene_change_threshold"])
    if "resize_resolution" in settings:
        res = settings["resize_resolution"]
        if isinstance(res, str):
            parts = res.split(",")
            config.video_processing.resize_resolution = (int(parts[0]), int(parts[1]))
        elif isinstance(res, list):
            config.video_processing.resize_resolution = tuple(res)
    
    # Force CPU only
    config.video_processing.use_gpu_decode = False
    
    # Audio settings
    audio_enabled = settings.get("audio", True)
    config.audio_processing.enabled = audio_enabled
    if "audio_model" in settings:
        config.audio_processing.model = settings["audio_model"]
    if "sample_rate" in settings:
        config.audio_processing.sample_rate = int(settings["sample_rate"])
    if "diarization" in settings:
        config.audio_processing.diarization = bool(settings["diarization"])
    if "language" in settings:
        lang = settings["language"]
        config.audio_processing.language = lang if lang else None
    
    # CV settings
    cv_enabled = settings.get("cv", True)
    config.cv_pipeline.enabled = cv_enabled
    if "detector" in settings:
        config.cv_pipeline.detector = settings["detector"]
    if "tracker" in settings:
        config.cv_pipeline.tracker = settings["tracker"]
    if "confidence_threshold" in settings:
        config.cv_pipeline.confidence_threshold = float(settings["confidence_threshold"])
    if "som_prompting" in settings:
        config.cv_pipeline.som_prompting = bool(settings["som_prompting"])
    if "custom_classes" in settings and settings["custom_classes"]:
        classes = [c.strip() for c in settings["custom_classes"].split(",") if c.strip()]
        if classes:
            config.cv_pipeline.classes_of_interest = classes
    
    # VLM settings
    if "vlm_model" in settings:
        config.vlm.model = settings["vlm_model"]
    if "vlm_max_tokens" in settings:
        config.vlm.max_tokens = int(settings["vlm_max_tokens"])
    if "vlm_temperature" in settings:
        config.vlm.temperature = float(settings["vlm_temperature"])
    if "vlm_frames_per_request" in settings:
        config.vlm.frames_per_request = int(settings["vlm_frames_per_request"])
    if "caption_prompt" in settings and settings["caption_prompt"]:
        config.vlm.caption_prompt = settings["caption_prompt"]
    
    # Pipeline settings
    if "inter_chunk_delay" in settings:
        config.inter_chunk_delay = float(settings["inter_chunk_delay"])
    
    return config


def publish_status(job_id: str, stage: str, progress: int, message: str):
    """Publish processing status to Redis for frontend polling."""
    status_data = {
        "job_id": job_id,
        "stage": stage,
        "progress": progress,
        "message": message,
        "timestamp": time.time()
    }
    r.set(f"video_processing:status:{job_id}", json.dumps(status_data), ex=3600)  # TTL 1 hour


async def process_video_job(job_data: dict):
    """
    Process a video file through the full pipeline:
    1. FFmpeg chunking → frame selection
    2. Audio transcription (Voxtral)
    3. Object detection (YOLO)
    4. VLM captioning (Mistral Large)
    5. Save results as ChunkRecords in Postgres
    6. Optionally build embeddings and graph
    """
    job_id = job_data.get("job_id", str(uuid.uuid4()))
    video_path = job_data.get("video_path")
    datastore_id = job_data.get("datastore_id")
    document_id = job_data.get("document_id")
    stream_id = job_data.get("stream_id", "default")
    do_embedding = job_data.get("settings", {}).get("embedding", False)
    do_graph = job_data.get("settings", {}).get("graph", False)
    
    print(f"[*] Processing VIDEO job {job_id} for Datastore {datastore_id}, Document {document_id}")
    
    # Resolve video path relative to project root if it's relative
    if video_path and not os.path.isabs(video_path):
        # Most paths coming from DB/backend start with 'data_directory' or are relative to rag_chatbot root
        project_root = os.path.dirname(DATA_DIRECTORY)
        candidate_path = os.path.abspath(os.path.join(project_root, video_path))
        if os.path.exists(candidate_path):
            video_path = candidate_path
        else:
            # Fallback: try relative to DATA_DIRECTORY itself
            candidate_path = os.path.abspath(os.path.join(DATA_DIRECTORY, video_path))
            if os.path.exists(candidate_path):
                video_path = candidate_path

    print(f"    Video path: {video_path}")
    
    try:
        # Build pipeline config from job settings
        config = build_pipeline_config(job_data)
        
        # Update status: starting
        publish_status(job_id, "ingesting", 10, "Starting video pipeline...")
        
        # Run the ingestion pipeline
        pipeline = IngestionPipeline(config)
        
        publish_status(job_id, "ingesting", 15, "Chunking video with FFmpeg...")
        
        # Run pipeline (this is the heavy processing)
        results = await asyncio.to_thread(
            pipeline.ingest,
            video_path,
            stream_id
        )
        
        publish_status(job_id, "ingesting", 60, f"Pipeline complete. {len(results)} chunks processed.")
        
        # Convert results to ChunkRecords and save to Postgres
        with Session(engine) as session:
            chunk_records = []
            for idx, chunk_result in enumerate(results):
                # Build text content from all available data
                text_parts = []
                
                # Transcript (use .full_text string, not the object)
                if chunk_result.transcript and chunk_result.transcript.full_text:
                    text_parts.append(f"[Transcript] {chunk_result.transcript.full_text}")
                
                # VLM Caption (field is 'caption', not 'vlm_caption')
                if chunk_result.caption and chunk_result.caption.text:
                    text_parts.append(f"[Visual Description] {chunk_result.caption.text}")
                
                # CV detections (field is 'cv_metadata', not 'cv_detections')
                if chunk_result.cv_metadata and chunk_result.cv_metadata.objects:
                    det_summary = ", ".join([
                        f"{obj.class_name} (conf: {obj.confidence:.2f})"
                        for obj in chunk_result.cv_metadata.objects[:10]
                    ])
                    text_parts.append(f"[Detected Objects] {det_summary}")
                
                text_content = "\n\n".join(text_parts) if text_parts else f"Video chunk {idx + 1}"
                
                # Build metadata
                metadata = {
                    "content_type": "video",
                    "source": video_path,
                    "stream_id": stream_id,
                    "chunk_index": idx,
                    "filename": os.path.basename(video_path),
                    "folder_id": None,
                    "loaderType": "video",
                }
                
                # Add timestamps if available
                if hasattr(chunk_result, 'start_time'):
                    metadata["start_timestamp"] = chunk_result.start_time
                if hasattr(chunk_result, 'end_time'):
                    metadata["end_timestamp"] = chunk_result.end_time
                if hasattr(chunk_result, 'chunk_id'):
                    metadata["video_chunk_id"] = chunk_result.chunk_id
                
                chunk_record = ChunkRecord(
                    datastore_id=datastore_id,
                    document_id=document_id,
                    chunk_index=str(uuid.uuid4()),
                    text=text_content,
                    metadatas=metadata
                )
                chunk_records.append(chunk_record)
            
            # Bulk insert
            if chunk_records:
                session.add_all(chunk_records)
                session.commit()
                print(f"[*] Saved {len(chunk_records)} video chunk records to DB")
            
            publish_status(job_id, "ingesting", 70, f"Saved {len(chunk_records)} chunks to database.")
        
        # Optional: Embedding (using rag_chatbot's existing embedding pipeline via upsert)
        # The embedding is handled by the existing upsert flow when user clicks "Upsert"
        # so we skip it here unless explicitly requested for immediate embedding
        if do_embedding:
            publish_status(job_id, "embedding", 75, "Embedding will be handled by Upsert flow...")
            # Embedding is handled by the existing ingestion pool upsert mechanism
            # We just mark the status
        
        # Optional: Graph building
        if do_graph:
            publish_status(job_id, "graph", 85, "Building knowledge graph...")
            try:
                from video_pipeline.graph.config import GraphConfig
                from video_pipeline.graph.entity_extractor import LLMEntityExtractor
                from video_pipeline.graph.graph_builder import GraphBuilder
                
                # Initialize config and extractor
                graph_config = GraphConfig()
                extractor = LLMEntityExtractor(graph_config)
                
                # Convert VideoResult chunks to dicts for graph builder
                chunk_list = results.chunks if hasattr(results, 'chunks') else results
                chunk_dicts = [
                    c.to_dict() if hasattr(c, 'to_dict') else dict(c) if isinstance(c, dict) else c
                    for c in chunk_list
                ]
                
                # Build graph
                builder = GraphBuilder(graph_config)
                builder.build_from_chunks(chunk_dicts, extractor)
                
                # Save graph to persistent directory
                graph_path = os.path.join(GRAPH_DIR, f"graph_{datastore_id}_{stream_id}.graphml")
                builder.save(graph_path)
                
                publish_status(job_id, "graph", 95, f"Knowledge graph saved to {graph_path}")
                print(f"[*] Knowledge graph saved: {graph_path}")
            except Exception as e:
                print(f"[!] Graph building error (non-fatal): {e}")
                traceback.print_exc()
                publish_status(job_id, "graph", 95, f"Graph building failed: {str(e)}")
        
        # Complete
        publish_status(job_id, "complete", 100, "✅ Video processing complete!")
        print(f"[*] Video job {job_id} completed successfully")
        
    except Exception as e:
        error_msg = f"❌ Error processing video: {str(e)}"
        print(f"[!] {error_msg}")
        traceback.print_exc()
        publish_status(job_id, "error", 0, error_msg)


async def delete_video_job(job_data: dict):
    """
    Deletes the video's GraphML and other output files from the local storage
    when the document is deleted by the user.
    """
    datastore_id = job_data.get("datastore_id")
    document_id = job_data.get("document_id")
    if not datastore_id or not document_id:
        return
        
    print(f"[*] Deleting graph data for document {document_id}")
    
    # Delete Graph files
    import glob
    from config import GRAPH_DIR, OUTPUT_DIR
    
    pattern = os.path.join(GRAPH_DIR, f"graph_{datastore_id}_{document_id}.*")
    for file_path in glob.glob(pattern):
        try:
            os.remove(file_path)
            print(f"[*] Deleted graph file {file_path}")
        except Exception as e:
            print(f"[!] Error deleting {file_path}: {e}")

async def message_loop():
    inbox_key = "video_processing:inbox"
    print(f"[*] Video Worker listening on {inbox_key}")
    
    while True:
        try:
            result = r.blpop(inbox_key, timeout=1)
            
            if result:
                _, message_json = result
                job_data = json.loads(message_json)
                job_type = job_data.get("job_type", "process_video")
                
                if job_type == "process_video":
                    await process_video_job(job_data)
                elif job_type == "delete_video":
                    await delete_video_job(job_data)
                else:
                    print(f"[!] Unknown job type: {job_type}")
            else:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"[!] Worker Loop Error: {e}")
            traceback.print_exc()
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(message_loop())
