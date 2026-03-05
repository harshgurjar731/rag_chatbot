
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pathlib import Path
from sqlmodel import Session, select, func
from models.FileRecord import FileRecord
from database import get_session
from models.datastore import DataStore
from models.FileRecord import DocumentRecord, ChunkRecord, Folder
import os
import redis
import json
from typing import List
from config import CONFIG  # Load .env variables
from ingestion_pipeline.ingestion_models import DataStoreCreate, DocumentRecordResponse, FolderCreate
from ingestion_pipeline.Config.Config import INGESTION_CONFIG
import shutil
import urllib.parse

# Redis Setup
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

router = APIRouter()

@router.post("/folders", response_model=Folder)
def create_folder(
    payload: FolderCreate,
    session: Session = Depends(get_session)
):
    parent = session.get(Folder, payload.parent_id)
    print("payload", payload)
    print("parent", parent)
    if not parent:
        raise HTTPException(404, "Parent folder not found")

    folder = Folder(
        name=payload.name,
        parent_id=parent.id,
        datastore_id=parent.datastore_id
    )

    session.add(folder)
    session.commit()
    session.refresh(folder)

    if parent.path:
        folder.path = f"{parent.path}{folder.id}/"
        session.add(folder)
        session.commit()

    return folder


@router.get("/datastore/{datastore_id}/folders")
def list_folder_contents(
    datastore_id: int,
    parent_id: int | None = Query(None),
    session: Session = Depends(get_session)
):
    # validate datastore exists (optional but recommended)
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(404, "Datastore not found")

    # if parent_id not provided → default to root folder
    if parent_id is None or parent_id == "":
        parent_id = datastore.root_folder_id

    # safety: ensure folder belongs to datastore
    folder = session.get(Folder, parent_id)
    if not folder or folder.datastore_id != datastore_id:
        raise HTTPException(400, "Invalid folder for this datastore")

    subfolders = session.exec(
        select(Folder).where(Folder.parent_id == parent_id)
    ).all()

    documents = session.exec(
        select(DocumentRecord).where(DocumentRecord.folder_id == parent_id)
    ).all()

    return {
        "current_folder": folder,
        "folders": subfolders,
        "documents": documents
    }

@router.get("/folders/{folder_id}/breadcrumbs")
def get_breadcrumbs(folder_id: int, session: Session = Depends(get_session)):

    folder = session.get(Folder, folder_id)
    if not folder:
        raise HTTPException(404, "Folder not found")

    trail = []

    while folder:
        trail.append(folder)
        folder = session.get(Folder, folder.parent_id) if folder.parent_id else None

    return list(reversed(trail))

@router.post("/datastore/{datastore_id}/upload", response_model=List[DocumentRecord])
async def upload_files_to_datastore(
    datastore_id: int,
    files: List[UploadFile] = File(...),
    documentDetails: List[str] = Form(...),
    session: Session = Depends(get_session)
):
    # Ensure same number of metadata entries and files
    if len(files) != len(documentDetails):
        raise HTTPException(
            status_code=400,
            detail="Number of files and documentDetails entries must match"
        )

    # Fetch datastore
    datastore = session.exec(
        select(DataStore).where(DataStore.id == datastore_id)
    ).first()

    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    saved_files = []

    # Determine target root directory
    datastore_root = (
        INGESTION_CONFIG["ingestion_root"] /
        INGESTION_CONFIG["ingestion_data_folder_name"] /
        datastore.name
    )
    os.makedirs(datastore_root, exist_ok=True)

    for idx, file in enumerate(files):
        # ----------- SAFETY: sanitize filenames --------------------
        safe_filename = Path(file.filename).name  # Prevents directory traversal
        # ------------------------------------------------------------

        # Construct final file path
        file_path = datastore_root / safe_filename
        existing = session.exec(
            select(DocumentRecord).where(
                DocumentRecord.datastore_id == datastore_id,
                DocumentRecord.filename == safe_filename
            )
        ).first()

        if existing and file_path.exists():
            print("Existing file: ", safe_filename)
            continue

        # Parse metadata
        try:
            meta = DocumentRecord.model_validate_json(documentDetails[idx])
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metadata JSON at index {idx}: {str(e)}"
            )
        meta.datastore_id = datastore_id
        meta.insert_vector_status = False
        # Write file to disk in chunks (safe for large files)
        try:
            with open(file_path, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    buffer.write(chunk)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file '{safe_filename}': {str(e)}"
            )

        meta.filePath = str(file_path)
        # Save metadata to DB
        try:
            session.add(meta)
            session.commit()
            session.refresh(meta)
        except Exception as e:
            session.rollback()
            # Clean up the file if DB write fails
            if file_path.exists():
                os.remove(file_path)
            raise HTTPException(
                status_code=500,
                detail=f"Database error saving metadata for '{safe_filename}': {str(e)}"
            )
        print("model dump:", meta.model_dump())
        saved_files.append(meta.model_copy(deep=True))
        print("Saved Files: ", saved_files)
    return saved_files

@router.get("/datastore/{datastore_id}/documents" , response_model=List[DocumentRecordResponse])
async def get_documents(
    datastore_id: int,
    session: Session = Depends(get_session)):
    
    return_documents: List[DocumentRecordResponse] = []
    return_documents: List[DocumentRecordResponse] = []
    documents = session.exec(select(DocumentRecord).where(
        (DocumentRecord.datastore_id == datastore_id) & 
        (DocumentRecord.loaderType != "SecondarySource")
    )).all()
    for document in documents:
        statement = (
            select(func.count(ChunkRecord.id))
            .where(ChunkRecord.document_id == document.id)
        )
        chunkCount = session.exec(statement).one()
        # datastore["documentCount"] = len(docs)
        return_documents.append(DocumentRecordResponse(
            **document.model_dump(),
            chunk_count = chunkCount
        ))
    print(f"Found {len(documents)} documents.")
    return return_documents

@router.get("/download/{datastore_id}/{doc_name}")
async def download_file(
    datastore_id: int,
    doc_name: str,
    session: Session = Depends(get_session)):

    try:
        safe_filename = urllib.parse.unquote(doc_name)
        print(f"Downloading file. Raw: {doc_name}, Safe: {safe_filename}, DS: {datastore_id}")
        document = session.exec(select(DocumentRecord).where((DocumentRecord.filename == safe_filename) & (DocumentRecord.datastore_id == datastore_id))).first()
        
        if not document:
            print(f"Exact match failed for {safe_filename}. Trying case-insensitive match.")
            document = session.exec(select(DocumentRecord).where((func.lower(DocumentRecord.filename) == safe_filename.lower()) & (DocumentRecord.datastore_id == datastore_id))).first()
            
        if not document:
             print(f"Document record not found for {safe_filename} in DS {datastore_id}")
             raise HTTPException(status_code=404, detail="Document record not found")

        datastore = session.exec(select(DataStore.name).where(DataStore.id == document.datastore_id)).first()

        datastore_root = INGESTION_CONFIG["ingestion_root"] / INGESTION_CONFIG["ingestion_data_folder_name"]
        file_path = datastore_root / datastore / document.filename

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on server")

        return FileResponse(
            path=file_path,
            filename=document.filename,
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@router.post("/deleteDocument/{document_id}")
async def delete_document(
    document_id: int, 
    session: Session = Depends(get_session)):

    try:
        document = session.exec(select(DocumentRecord).where(DocumentRecord.id == document_id)).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
            
        datastore = session.exec(select(DataStore).where(DataStore.id == document.datastore_id)).first()
        chunk_indexes = session.exec(select(ChunkRecord.chunk_index).where(ChunkRecord.document_id == document_id)).all()

        if ((datastore.vector_store_provider != None) and (len(chunk_indexes) > 0)):
            # Dispatch delete job to Redis
            job_payload = {
                "job_type": "delete_vectors",
                "datastore_id": datastore.id,
                "document_id": document_id,
                "vector_store_provider": datastore.vector_store_provider,
                "chunk_indexes": chunk_indexes
            }
            r.rpush("ingestion:inbox", json.dumps(job_payload))
            print(f"[*] Queued vector deletion for document {document_id}")

        if os.path.exists(document.filePath):
            try:
                os.remove(document.filePath)
                print("File deleted successfully.")
            except OSError as e:
                print(f"Warning: Failed to delete physical file: {e}")
        else:
            print("File not found.")
        
        session.delete(document)
        session.commit()
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        print(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.get("/datastore/{datastore_id}/documents/{document_id}/name")
def get_document_name(
    datastore_id: int, 
    document_id: int, 
    session: Session = Depends(get_session)
):
    doc = session.get(DocumentRecord, document_id)
    if not doc or doc.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"file_name": doc.filename}

@router.get("/datastore/{datastore_id}/files/{file_id}/name")
def get_file_name_by_id(
    datastore_id: int, 
    file_id: int, 
    session: Session = Depends(get_session)
):
    # Assuming file_id maps to DocumentRecord.id as hinted by the frontend code
    doc = session.get(DocumentRecord, file_id)
    if not doc or doc.datastore_id != datastore_id:
         raise HTTPException(status_code=404, detail="File (Document) not found")
    return {"file_name": doc.filename}

@router.get("/datastore/{datastore_id}/files/{filename}/id")
def get_file_id_by_name(
    datastore_id: int, 
    filename: str, 
    session: Session = Depends(get_session)
):
    safe_filename = urllib.parse.unquote(filename)
    doc = session.exec(
        select(DocumentRecord).where(
            DocumentRecord.datastore_id == datastore_id,
            DocumentRecord.filename == safe_filename
        )
    ).first()
    
    if not doc:
         raise HTTPException(status_code=404, detail="File not found")
    return {"file_id": doc.id}
