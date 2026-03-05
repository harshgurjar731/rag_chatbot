from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import shutil
import os
import tempfile
from ingestion_pipeline.video_processor import process_video
from sqlmodel import Session, select
from database import get_session
from models.datastore import DataStore, SecondarySource
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()

from ingestion_pipeline.Config.Config import INGESTION_CONFIG
from fastapi.responses import FileResponse
import urllib.parse

class SecondarySourceRequest(BaseModel):
    intent: str
    description: str
    file_path: Optional[str] = None

class SecondarySourceResponse(SecondarySourceRequest):
    id: int
    datastore_id: int

@router.post("/datastore/{datastore_id}/secondary_sources", response_model=List[SecondarySourceResponse])
async def add_secondary_sources(
    datastore_id: int,
    sources: List[SecondarySourceRequest],
    session: Session = Depends(get_session)
):
    datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    print(f"Adding {len(sources)} secondary sources to datastore {datastore_id}")
    
    new_records = []
    for source in sources:
        clean_intent = source.intent.strip() if source.intent else ""
        new_source = SecondarySource(
            datastore_id=datastore_id,
            intent=clean_intent,
            description=source.description,
            file_path=source.file_path
        )
        session.add(new_source)
        new_records.append(new_source)
    
    # Update datastore flag
    datastore.has_secondary_sources = True
    session.add(datastore)
    
    try:
        session.commit()
        for record in new_records:
            session.refresh(record)
            
        # Logging tables as requested
        print("\n--- Current DataStore Table ---")
        all_datastores = session.exec(select(DataStore)).all()
        for ds in all_datastores:
            print(f"ID: {ds.id}, Name: {ds.name}, HasSecondary: {ds.has_secondary_sources}")
            
        print("\n--- Current SecondarySource Table ---")
        all_sources = session.exec(select(SecondarySource)).all()
        for src in all_sources:
             print(f"ID: {src.id}, DS_ID: {src.datastore_id}, Intent: {src.intent}, File: {src.file_path}")
        print("--------------------------------\n")

        return new_records
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/datastore/{datastore_id}/secondary_sources", response_model=List[SecondarySourceResponse])
async def get_secondary_sources(
    datastore_id: int,
    session: Session = Depends(get_session)
):
    query = select(SecondarySource).where(SecondarySource.datastore_id == datastore_id)
    results = session.exec(query).all()
    return results

@router.delete("/secondary_sources/{source_id}")
async def delete_secondary_source(
    source_id: int,
    session: Session = Depends(get_session)
):
    source = session.exec(select(SecondarySource).where(SecondarySource.id == source_id)).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    datastore_id = source.datastore_id
    session.delete(source)
    
    # Check if there are any remaining sources
    remaining = session.exec(select(SecondarySource).where(SecondarySource.datastore_id == datastore_id)).all()
    if not remaining:
        datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
        if datastore:
            datastore.has_secondary_sources = False
            session.add(datastore)
            
    session.commit()
    return {"message": "Deleted successfully"}
    return {"message": "Deleted successfully"}

@router.post("/datastore/{datastore_id}/upload_video_source")
async def upload_video_source(
    datastore_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    print(f"Received video upload: {file.filename} for datastore {datastore_id}")
    
    # Validate file type
    if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
         raise HTTPException(status_code=400, detail="Invalid file type. Only video files are allowed.")

    # Save uploaded file temporarily for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_video:
        shutil.copyfileobj(file.file, temp_video)
        temp_video_path = temp_video.name
    
    print(f"Saved temp video to {temp_video_path}")
    
    try:
        # Process video
        metadata = await process_video(temp_video_path)
        
        # Save to DB
        datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
        if not datastore:
            raise HTTPException(status_code=404, detail="Datastore not found")

        # Define permanent storage path
        datastore_root = INGESTION_CONFIG["ingestion_root"] / INGESTION_CONFIG["ingestion_data_folder_name"] / datastore.name
        os.makedirs(datastore_root, exist_ok=True)
        
        # Sanitize filename
        safe_filename = os.path.basename(file.filename)
        permanent_path = datastore_root / safe_filename
        
        # Copy file to permanent location
        shutil.copy2(temp_video_path, permanent_path)
        print(f"Saved permanent video to {permanent_path}")

        new_source = SecondarySource(
            datastore_id=datastore_id,
            intent=metadata.get("intent", "Video Source"),
            description=metadata.get("description", ""),
            file_path=file.filename # Storing filename as reference
        )
        session.add(new_source)
        
        datastore.has_secondary_sources = True
        session.add(datastore)
        session.commit()
        session.refresh(new_source)
        
        return new_source
        
    except Exception as e:
        session.rollback()
        print(f"Error processing video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")
    finally:
        # Cleanup temp video
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)


@router.get("/datastore/{datastore_id}/secondary_download/{filename}")
async def download_secondary_source(
    datastore_id: int,
    filename: str,
    session: Session = Depends(get_session)
):
    try:
        safe_filename = urllib.parse.unquote(filename)
        
        # Find the source record to verify existence and get context (though we mostly need datastore name)
        # We search by suffix or partial match if needed, but exact match on stored filePath is best
        # The stored file_path is currently just the filename.
        
        datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
        if not datastore:
             raise HTTPException(status_code=404, detail="Datastore not found")

        datastore_root = INGESTION_CONFIG["ingestion_root"] / INGESTION_CONFIG["ingestion_data_folder_name"] / datastore.name
        file_path = datastore_root / safe_filename

        if not os.path.exists(file_path):
            print(f"File not found at {file_path}")
            raise HTTPException(status_code=404, detail="File not found on server")

        return FileResponse(
            path=file_path,
            filename=safe_filename,
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error downloading secondary file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

