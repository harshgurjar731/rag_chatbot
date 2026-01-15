"""
API route for file preview.

This module provides an endpoint to preview the actual text content of a file
before it is chunked or embedded, helping users verify data quality.
"""
# rag_app/backend/routes/file_preview.py
from database import get_session
from Services.document_loader import load_file_with_loader
from models.FileRecord import FileRecord
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from config import CONFIG  # centralized env-driven config
from models.datastore import DataStore
from pathlib import Path

router = APIRouter()


@router.get("/datastores/{datastore_id}/files/{file_id}/loader/{loader_type}/preview")
def preview_file(
    datastore_id: int,
    file_id: int,
    loader_type: str,
    session: Session = Depends(get_session),
):
    """
    Preview the content of a file using a specific loader.

    Args:
        datastore_id (int): ID of the datastore.
        file_id (int): ID of the file.
        loader_type (str): Type of loader to use (e.g., 'pdf', 'txt').
        session (Session): Database session.

    Returns:
        dict: Filename, preview text, and total length.

    Raises:
        HTTPException: If file/datastore not found.
    """
    # 1️⃣ Validate file
    file_record = session.get(FileRecord, file_id)
    if not file_record or file_record.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found for datastore")

    # 2️⃣ Validate datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 3️⃣ Construct file path (raw files live in DATA_FOLDER)
    file_path = (
    CONFIG["project_root"]
    / CONFIG["datastore_data_folder"]
    / str(datastore.name)
    / file_record.filename)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk: {file_path}")

    # 4️⃣ Load document content
    docs = load_file_with_loader(file_path, loader_type)
    preview = docs[0].page_content[:1000]  # limit preview length

    return {
        "filename": file_record.filename,
        "preview": preview,
        "length": len(docs[0].page_content),
    }
