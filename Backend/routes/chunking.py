# Backend/routes/chunking.py

from fastapi import APIRouter, HTTPException, Depends, Query
from pathlib import Path
from sqlmodel import Session
from models.FileRecord import FileRecord
from database import get_session
from Services.document_loader import load_file_with_loader
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from models.datastore import DataStore
import os   

router = APIRouter()

@router.get("/datastores/{datastore_id}/files/{file_id}/chunk")
def preview_chunks(
    datastore_id: int,
    file_id: int,
    method: str = Query("recursive", description="Chunking method"),
    chunk_size: int = Query(512, description="Chunk size"),
    chunk_overlap: int = Query(50, description="Chunk overlap"),
    session: Session = Depends(get_session)
):
    # 1. Validate file existence
    file = session.get(FileRecord, file_id)
    print(f"File Record: {file}")
    if not file or file.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found in specified datastore")

    # 2. Resolve file path
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    project_root = Path(__file__).resolve().parent.parent.parent
    base_folder = project_root / "Data" / str(datastore.name)
    file_path = base_folder / file.filename

    print(f"File Path: {file_path}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Original file not found on disk")

    # 3. Construct .json path
    json_path = file_path.with_suffix('.json')
    print(f"JSON Path: {json_path}")
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"JSON file not found: {json_path}")

    try:
        # 4. Load and chunk
        docs = load_docs_from_json(json_path)
        chunks = chunk_documents(docs, method=method, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        # 5. Save chunks to a new .json file
        chunks_file_path = base_folder / f"{file.filename.rsplit('.', 1)[0]}_chunks.json"
        save_chunks_to_json(chunks, chunks_file_path)

        print(f"Chunks File Path: {chunks_file_path}")
        return {"chunks": [chunk.page_content for chunk in chunks]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/datastores/{datastore_id}/files/{file_id}/chunk")
def delete_chunk_file(
    datastore_id: int,
    file_id: int,
    session: Session = Depends(get_session)
):
    # Validate file
    file = session.get(FileRecord, file_id)
    if not file or file.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found in specified datastore")

    # Get datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Construct chunk file path
    project_root = Path(__file__).resolve().parent.parent.parent
    name_without_extension = file.filename.rsplit('.', 1)[0]
    chunks_file_path = project_root / "Data" / str(datastore.name) / (name_without_extension + "_chunks.json")

    if not chunks_file_path.exists():
        raise HTTPException(status_code=404, detail="Chunk file not found")

    try:
        os.remove(chunks_file_path)
        return {"status": "success", "message": "Chunk file deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chunk file: {str(e)}")