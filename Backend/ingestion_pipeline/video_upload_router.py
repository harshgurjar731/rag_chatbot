"""
Video Upload Router.

Handles video file uploads and dispatches video processing jobs to Redis
for the ingestion pool → video processing pool pipeline.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pathlib import Path
from sqlmodel import Session, select
from models.FileRecord import DocumentRecord
from database import get_session
from models.datastore import DataStore
import os
import redis
import json
import uuid
from typing import Optional
from ingestion_pipeline.Config.Config import INGESTION_CONFIG

# Redis Setup
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

router = APIRouter()


@router.post("/datastore/{datastore_id}/upload_video")
async def upload_video(
    datastore_id: int,
    file: UploadFile = File(...),
    settings: str = Form("{}"),
    session: Session = Depends(get_session)
):
    """
    Upload a video file, save to disk, create DocumentRecord, 
    and dispatch a process_video job through Redis.
    
    Flow: Backend → Redis (ingestion:inbox) → Ingestion Pool → Redis (video_processing:inbox) → Video Pool
    """
    # Validate datastore exists
    datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")
    
    # Validate file type
    allowed_extensions = {".mp4", ".mkv", ".avi", ".mov"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: {file_ext}. Supported: {', '.join(allowed_extensions)}"
        )
    
    # Safe filename
    safe_filename = Path(file.filename).name
    
    # Determine storage path
    datastore_root = (
        INGESTION_CONFIG["ingestion_root"] /
        INGESTION_CONFIG["ingestion_data_folder_name"] /
        datastore.name
    )
    os.makedirs(datastore_root, exist_ok=True)
    
    file_path = datastore_root / safe_filename
    
    # Check for duplicate
    existing = session.exec(
        select(DocumentRecord).where(
            DocumentRecord.datastore_id == datastore_id,
            DocumentRecord.filename == safe_filename
        )
    ).first()
    
    if existing:
        # Reuse existing record, but delete old chunks if any (to prevent duplicates on retry)
        from models.FileRecord import ChunkRecord
        old_chunks = session.exec(select(ChunkRecord).where(ChunkRecord.document_id == existing.id)).all()
        for chunk in old_chunks:
            session.delete(chunk)
        session.commit()
        doc_record = existing
    else:
        # Create new DocumentRecord
        try:
            doc_record = DocumentRecord(
                filename=safe_filename,
                loaderType="video",
                textSplitMethod="video_pipeline",
                chunkSize=0,
                chunkOverlap=0,
                filePath=str(file_path),
                datastore_id=datastore_id,
                insert_vector_status=False,
            )
            session.add(doc_record)
            session.commit()
            session.refresh(doc_record)
        except Exception as e:
            session.rollback()
            if file_path.exists():
                os.remove(file_path)
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(e)}"
            )
            
    # Save video file to disk (overwrite if exists)
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save video file: {str(e)}"
        )
    
    # Parse settings from frontend
    try:
        video_settings = json.loads(settings)
    except json.JSONDecodeError:
        video_settings = {}
    
    # Generate job ID for status tracking
    job_id = str(uuid.uuid4())
    
    # Dispatch process_video job to Redis (ingestion:inbox)
    # The ingestion worker will forward it to video_processing:inbox
    job_payload = {
        "job_type": "process_video",
        "job_id": job_id,
        "datastore_id": datastore_id,
        "document_id": doc_record.id,
        "video_path": str(file_path),
        "stream_id": video_settings.get("stream_id", safe_filename.rsplit(".", 1)[0]),
        "settings": video_settings,
    }
    
    r.rpush("ingestion:inbox", json.dumps(job_payload))
    print(f"[*] Queued video processing job {job_id} for datastore {datastore_id}")
    
    return {
        "status": "processing",
        "job_id": job_id,
        "document_id": doc_record.id,
        "filename": safe_filename,
        "message": "Video uploaded and processing job queued"
    }


@router.get("/video/status/{job_id}")
async def get_video_status(job_id: str):
    """
    Get the processing status of a video job.
    Frontend polls this endpoint to show progress.
    """
    status_key = f"video_processing:status:{job_id}"
    status_data = r.get(status_key)
    
    if not status_data:
        return {
            "job_id": job_id,
            "stage": "queued",
            "progress": 0,
            "message": "Job is queued for processing..."
        }
    
    try:
        return json.loads(status_data)
    except json.JSONDecodeError:
        return {
            "job_id": job_id,
            "stage": "unknown",
            "progress": 0,
            "message": "Unable to parse status"
        }


@router.get("/video/defaults")
async def get_video_defaults():
    """
    Return default video processing settings by reading from the actual config.yaml
    used by the video processing pool.
    """
    import yaml

    # Locate config.yaml relative to the project root
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "video_processing_pool", "config.yaml"
    )

    cfg = {}
    try:
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[video/defaults] Could not read config.yaml: {e}")

    sh = cfg.get("stream_handler", {})
    vp = cfg.get("video_processing", {})
    ap = cfg.get("audio_processing", {})
    cv = cfg.get("cv_pipeline", {})
    vlm = cfg.get("vlm", {})

    return {
        "chunk_duration_seconds": sh.get("chunk_duration_seconds", 30),
        "frames_per_chunk": vp.get("frames_per_chunk", 5),
        "frame_selection": vp.get("frame_selection", "scene_change"),
        "scene_change_threshold": vp.get("scene_change_threshold", 30.0),
        "resize_resolution": vp.get("resize_resolution", [1080, 1080]),
        "audio_model": ap.get("model", "voxtral-mini-latest"),
        "sample_rate": ap.get("sample_rate", 16000),
        "diarization": ap.get("diarization", True),
        "language": ap.get("language") or "",
        "detector": cv.get("detector", "yolov8x"),
        "tracker": cv.get("tracker", "bytetrack"),
        "confidence_threshold": cv.get("confidence_threshold", 0.3),
        "som_prompting": cv.get("som_prompting", True),
        "vlm_model": vlm.get("model", "mistral-large-2512"),
        "vlm_max_tokens": vlm.get("max_tokens", 4096),
        "vlm_temperature": vlm.get("temperature", 0.1),
        "vlm_frames_per_request": vlm.get("frames_per_request", 8),
        "caption_prompt": "",
        "inter_chunk_delay": cfg.get("inter_chunk_delay", 2),
        "classes_of_interest": cv.get("classes_of_interest", ["person", "vehicle", "backpack", "suitcase"]),
    }

