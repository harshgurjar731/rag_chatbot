"""
API routes for document chunking operations.

This module provides endpoints to preview (generate) chunks for files and
delete generated chunk files.
"""
# rag_app/backend/routes/chunking.py

from fastapi import APIRouter, HTTPException, Depends, Query
from pathlib import Path
from sqlmodel import Session
from models.FileRecord import FileRecord
from database import get_session
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from models.datastore import DataStore
import os
from config import CONFIG  # Load .env variables

router = APIRouter()


@router.get("/datastores/{datastore_id}/files/{file_id}/chunk")
def preview_chunks(
    datastore_id: int,
    file_id: int,
    method: str = Query(None, description="Chunking method"),
    chunk_size: int = Query(None, description="Chunk size"),
    chunk_overlap: int = Query(None, description="Chunk overlap"),
    session: Session = Depends(get_session),
):
    """
    Preview chunks for a specific file in a datastore.

    Chunks the file content based on the specified method and parameters,
    saves the chunks to a JSON file, and returns the chunk text.

    Args:
        datastore_id (int): The ID of the datastore.
        file_id (int): The ID of the file.
        method (str, optional): Chunking method (e.g., 'recursive'). Defaults to config.
        chunk_size (int, optional): Size of each chunk. Defaults to config.
        chunk_overlap (int, optional): Overlap between chunks. Defaults to config.
        session (Session): Database session.

    Returns:
        dict: A dictionary containing a list of chunk texts.
    
    Raises:
        HTTPException: If file or datastore is not found, or if processing fails.
    """
    # ✅ Use env/defaults if query params not provided
    method = method or CONFIG["default_chunk_method"]
    chunk_size = chunk_size or CONFIG["default_chunk_size"]
    chunk_overlap = chunk_overlap or CONFIG["default_chunk_overlap"]

    # 1️⃣ Validate file existence
    file = session.get(FileRecord, file_id)
    if not file or file.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found in specified datastore")

    # 2️⃣ Resolve file path
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    file_path = (
        CONFIG["project_root"]
        / CONFIG["datastore_data_folder"]
        / str(datastore.name)
        / file.filename
    )

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Original file not found on disk")

    # 3️⃣ Construct .json path
    json_path = file_path.with_suffix(".json")
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"JSON file not found: {json_path}")

    try:
        # 4️⃣ Load and chunk
        docs = load_docs_from_json(json_path)
        chunks = chunk_documents(
            docs, method=method, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        # 5️⃣ Save chunks into centralized chunks folder
        chunks_file_path = (
            CONFIG["project_root"]
            /CONFIG["datastore_data_folder"]
            / str(datastore.name)
            / f"{file.filename.rsplit('.', 1)[0]}_chunks.json"
        )
        chunks_file_path.parent.mkdir(parents=True, exist_ok=True)  # ensure folder exists
        save_chunks_to_json(chunks, chunks_file_path)

        return {"chunks": [chunk.page_content for chunk in chunks]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/datastores/{datastore_id}/files/{file_id}/chunk")
def delete_chunk_file(
    datastore_id: int,
    file_id: int,
    session: Session = Depends(get_session),
):
    """
    Delete the chunked JSON file for a specific file.

    Args:
        datastore_id (int): The ID of the datastore.
        file_id (int): The ID of the file.
        session (Session): Database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If file, datastore, or chunk file is not found, or invalid.
    """
    # 1️⃣ Validate file
    file = session.get(FileRecord, file_id)
    if not file or file.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found in specified datastore")

    # 2️⃣ Validate datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 3️⃣ Construct chunk file path from config
    name_without_extension = file.filename.rsplit(".", 1)[0]
    chunks_file_path = (
        CONFIG["project_root"]
        /CONFIG["datastore_data_folder"]
        / str(datastore.name)
        / f"{name_without_extension}_chunks.json"
    )

    if not chunks_file_path.exists():
        raise HTTPException(status_code=404, detail="Chunk file not found")

    try:
        os.remove(chunks_file_path)
        return {"status": "success", "message": "Chunk file deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chunk file: {str(e)}")
