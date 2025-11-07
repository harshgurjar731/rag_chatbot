
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pathlib import Path
from sqlmodel import Session, select
from models.FileRecord import FileRecord
from database import get_session
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from models.datastore import DataStore
from models.FileRecord import DocumentRecord, ChunkRecord
import os
from typing import List
from config import CONFIG  # Load .env variables
from ingestion_pipleline.ingestion_models import DataStoreCreate
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from ingestion_pipleline.VectorStores.vector_store_generator import create_vector_store
import shutil

router = APIRouter()


@router.post("/datastore/{datastore_id}/upload")
async def upload_file_to_datastore(
    datastore_id: int,
    file: UploadFile = File(...),
    documentDetails: str = Form(...),
    session: Session = Depends(get_session)):

    print("Uploading file to datastore ID:", datastore_id)
    print("Received document details:", documentDetails)    

    documentDetailsObj = DocumentRecord.model_validate_json(documentDetails)
    documentDetailsObj.datastore_id = datastore_id
    documentDetailsObj.insert_vector_status = False
    print("Parsed document details:", documentDetailsObj)

    datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
    
    existing = session.exec(select(DocumentRecord).where((DocumentRecord.datastore_id == datastore_id) & (DocumentRecord.filename == file.filename))).first()
    if existing:
        raise HTTPException(status_code=400, detail="Document already exists")

     # 3️⃣ Save file
    datastore_root = INGESTION_CONFIG["ingestion_root"] / INGESTION_CONFIG["ingestion_data_folder_name"]
    os.makedirs(datastore_root, exist_ok=True)

    file_path = datastore_root / datastore.name / file.filename
    file_bytes = file.file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    print("File saved at: ", file_path)
    documentDetailsObj.filePath = str(file_path)

    session.add(documentDetailsObj)
    session.commit()
    session.refresh(documentDetailsObj)

    return documentDetailsObj

@router.get("/datastore/{datastore_id}/documents" , response_model=List[DocumentRecord])
async def get_documents(
    datastore_id: int,
    session: Session = Depends(get_session)):
    
    documents = session.exec(select(DocumentRecord).where(DocumentRecord.datastore_id == datastore_id)).all()
    print(f"Found {len(documents)} documents.")
    return documents

@router.get("/download/{doc_id}")
async def download_file(
    doc_id: int,
    session: Session = Depends(get_session)):

    document = session.exec(select(DocumentRecord).where(DocumentRecord.id == doc_id)).first()
    datastore = session.exec(select(DataStore.name).where(DataStore.id == document.datastore_id)).first()

    datastore_root = INGESTION_CONFIG["ingestion_root"] / INGESTION_CONFIG["ingestion_data_folder_name"]
    file_path = datastore_root / datastore.name / document.filename

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=document.filename,
        media_type="application/octet-stream"
    )

@router.post("/deleteDocument/{document_id}")
async def delete_document(
    document_id: int, 
    session: Session = Depends(get_session)):

    document = session.exec(select(DocumentRecord).where(DocumentRecord.id == document_id)).first()
    datastore = session.exec(select(DataStore).where(DataStore.id == document.datastore_id)).first()
    chunk_indexes = session.exec(select(ChunkRecord.chunk_index).where(ChunkRecord.document_id == document_id)).all()

    if ((datastore.vector_store_provider != None) & (len(chunk_indexes) > 0)):
        vectorDB = create_vector_store(provider=datastore.vector_store_provider)
        vectorDB.delete(collection=datastore.id, ids = chunk_indexes)

    if os.path.exists(document.filePath):
        os.remove(document.filePath)
        print("File deleted successfully.")
    else:
        print("File not found.")
    
    session.delete(document)
    session.commit()
