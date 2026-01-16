
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pathlib import Path
from sqlmodel import Session, select, func
from models.FileRecord import FileRecord
from database import get_session
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from models.datastore import DataStore
from models.FileRecord import DocumentRecord, ChunkRecord
import os
from typing import List
from config import CONFIG  # Load .env variables
from ingestion_pipleline.ingestion_models import DataStoreCreate, DocumentRecordResponse
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from ingestion_pipleline.VectorStores.vector_store_generator import create_vector_store
import shutil
import urllib.parse



router = APIRouter()

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
    documents = session.exec(select(DocumentRecord).where(DocumentRecord.datastore_id == datastore_id)).all()
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
        document = session.exec(select(DocumentRecord).where((DocumentRecord.filename == doc_name) & (DocumentRecord.datastore_id == datastore_id))).first()
        if not document:
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

        if ((datastore.vector_store_provider != None) & (len(chunk_indexes) > 0)):
            try:
                vectorDB = create_vector_store(provider=datastore.vector_store_provider)
                vectorDB.delete(collection=f"datastore_{datastore.id}", ids = chunk_indexes)
            except Exception as e:
                 print(f"Warning: Failed to delete vectors: {e}")

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
