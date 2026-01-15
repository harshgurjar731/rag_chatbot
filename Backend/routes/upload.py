"""
API routes for file management (upload/download/delete).

This module handles the full lifecycle of file ingestion, from upload to
chunking and embedding generation.
"""
# backend/routes/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, status
from sqlmodel import Session, select
from pathlib import Path
from typing import List
from database import get_session
from models.datastore import DataStore
from models.FileRecord import FileRecord
from fastapi.responses import FileResponse
from Services.document_loader import load_file_with_loader
from Services.embedding_service import embed_and_store, check_embeddings_status, delete_vector_store
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from config import CONFIG  # ✅ centralized env-driven config
import os
# from Evaluation.delete_qna import delete_qna_by_file,delete_generated_files  
router = APIRouter()


@router.post("/datastores/{datastore_id}/upload")
def upload_file_to_datastore(
    datastore_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)
):
    """
    Upload a file to a datastore and trigger processing.

    This endpoint handles:
    1. Saving the file to disk.
    2. Creating a DB record.
    3. Generating a preview.
    4. Chunking the document.
    5. Generating and storing embeddings.

    Args:
        datastore_id (int): ID of the datastore.
        file (UploadFile): The file to upload.
        session (Session): Database session.

    Returns:
        dict: Success message and file details.

    Raises:
        HTTPException: If datastore not found or any processing step fails.
    """
    # 1️⃣ Validate datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 2️⃣ Resolve physical path (✅ use CONFIG instead of hardcoded "Data")
    ds_folder = CONFIG["project_root"]/ CONFIG["datastore_data_folder"] / str(datastore.name)
    if not ds_folder.exists():
        raise HTTPException(status_code=500, detail="Datastore folder not found")

    # 3️⃣ Save file
    file_path = ds_folder / file.filename
    file_bytes = file.file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # 4️⃣ Record metadata in DB
    file_record = FileRecord(
        filename=file.filename,
        content_type=file.content_type,
        size=len(file_bytes),
        datastore_id=datastore_id,
    )
    session.add(file_record)
    session.commit()
    session.refresh(file_record)

    # === 5. Preview Logic ===
    try:
        loader_type = file.filename.split(".")[-1]  # infer from extension
        docs = load_file_with_loader(file_path, loader_type)
        preview = docs[0].page_content[:1000]
        length = len(docs[0].page_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")

    # === 6. Chunking Logic ===
    try:
        json_path = file_path.with_suffix(".json")
        if not json_path.exists():
            raise HTTPException(status_code=404, detail=f"JSON file not found: {json_path}")

        docs_from_json = load_docs_from_json(json_path)
        chunks = chunk_documents(docs_from_json, method="recursive", chunk_size=512, chunk_overlap=50)

        chunks_file_path = ds_folder / f"{file.filename.rsplit('.', 1)[0]}_chunks.json"
        save_chunks_to_json(chunks, chunks_file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunking failed: {str(e)}")

    # === 7. Store Embeddings Logic ===
    try:
        model_name = CONFIG["default_embedding_model"]
        vector_db = CONFIG["default_vector_db"]
        result = embed_and_store(chunks_file_path, file_record.id, model_name, vector_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

    return {
        "message": "File uploaded, previewed, chunked, and embeddings stored",
        "file_id": file_record.id,
        "filename": file_record.filename,
        "preview": preview,
        "length": length,
    }


@router.get("/datastores/{datastore_id}/files", response_model=List[FileRecord])
def list_files_in_datastore(datastore_id: int, session: Session = Depends(get_session)):
    """
    List all files in a datastore.

    Args:
        datastore_id (int): ID of the datastore.
        session (Session): Database session.

    Returns:
        List[FileRecord]: List of file records.
    """
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    files = session.exec(select(FileRecord).where(FileRecord.datastore_id == datastore_id)).all()
    return files


@router.delete("/datastores/{datastore_id}/files/{file_id}", status_code=status.HTTP_200_OK)
def delete_file_from_datastore(
    datastore_id: int,
    file_id: int,
    vector_db: str = Query(CONFIG["default_vector_db"], description="Vector DB name"),
    session: Session = Depends(get_session),
):
    """
    Delete a file from a datastore.

    This removes the physical file, its chunks, embeddings, QA pairs, and DB record.

    Args:
        datastore_id (int): ID of the datastore.
        file_id (int): ID of the file.
        vector_db (str, optional): Vector DB name.
        session (Session): Database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If file/datastore not found or deletion fails.
    """
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    file_record = session.get(FileRecord, file_id)
    if not file_record or file_record.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found in this datastore")

    data_folder = CONFIG["project_root"]/ CONFIG["datastore_data_folder"] / str(datastore.name)
    original_file_path = data_folder / file_record.filename
    preview_file_path = original_file_path.with_suffix(".json")
    chunk_file_path = data_folder / (file_record.filename.rsplit(".", 1)[0] + "_chunks.json")

    # Delete files safely
    for path, label in [
        (original_file_path, "original file"),
        (preview_file_path, "preview file"),
        (chunk_file_path, "chunked file"),
    ]:
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete {label}: {str(e)}")

    # Delete embeddings
    try:
        delete_vector_store(file_id, vector_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete vectors: {str(e)}")

    # ✅ Delete QA pairs associated with this file
    try:
        deleted_count = delete_qna_by_file(session, file_id)
        print(f"[INFO] Deleted {deleted_count} QA pairs for file_id {file_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete QA pairs: {str(e)}")
    
    try:
        delete_generated_files(original_file_path)   
    except FileNotFoundError as fnf_error:
        print(f"[WARN] File not found: {fnf_error}")
    except PermissionError as perm_error:
        print(f"[ERROR] Permission denied: {perm_error}")
    except Exception as e:
        print(f"[ERROR] Failed to delete files: {e}")

    json_file=Path(CONFIG["project_root"] / "Data" / datastore.name / f"{datastore.name}_evaluation_qa.json")
    json_file1=Path(CONFIG["project_root"] / "Data" / datastore.name / f"{file_record.filename}_qa_pairs_cleaned.json")

    try:
        if json_file.exists() and json_file1.exists():
            json_file.unlink()
            json_file1.unlink()
            print(f"[INFO] Deleted: {json_file}")
            print(f"[INFO] Deleted: {json_file1}")
    except Exception as e:
        print(f"[ERROR] Failed to delete {json_file}: {e}")

    # Delete the file record
    session.delete(file_record)
    session.commit()

    return {
        "message": "File, preview, chunks, embeddings, and QA pairs deleted successfully",
        "file_id": file_id,
        "filename": file_record.filename,
    }


@router.get("/datastores/{datastore_id}/files/{filename}", response_class=FileResponse)
def get_file(datastore_id: int, filename: str, session: Session = Depends(get_session)):
    """
    Download/Serve a file from the datastore.

    Args:
        datastore_id (int): ID of the datastore.
        filename (str): Name of the file.
        session (Session): Database session.

    Returns:
        FileResponse: The file content.
    """
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    statement = select(FileRecord).where(FileRecord.filename == filename, FileRecord.datastore_id == datastore_id)
    file_record = session.exec(statement).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in database")

    file_path = CONFIG["project_root"]/ CONFIG["datastore_data_folder"] / str(datastore.name) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=file_record.content_type or "application/octet-stream",
    )


@router.delete("/datastores/{datastore_id}/files/{filename}")
def delete_file(datastore_id: int, filename: str, session: Session = Depends(get_session)):
    """
    Delete a file by filename (deprecated, prefer by ID).

    Args:
        datastore_id (int): ID of the datastore.
        filename (str): Name of the file.
        session (Session): Database session.

    Returns:
        dict: Success message.
    """
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    statement = select(FileRecord).where(FileRecord.filename == filename, FileRecord.datastore_id == datastore_id)
    file_record = session.exec(statement).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in database")

    file_path = CONFIG["project_root"]/ CONFIG["datastore_data_folder"] / str(datastore.name) / filename
    if file_path.exists():
        try:
            os.remove(file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="File not found on disk")

    session.delete(file_record)
    session.commit()
    return {"detail": f"File '{filename}' deleted successfully"}


@router.get("/datastores/{datastore_id}/files/{filename}/id")
def get_file_id(datastore_id: int, filename: str, session: Session = Depends(get_session)):
    print("In the API")
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    statement = select(FileRecord).where(FileRecord.filename == filename, FileRecord.datastore_id == datastore_id)
    file_record = session.exec(statement).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in database")

    return {"file_id": file_record.id}

@router.get("/datastores/{datastore_id}/files/{file_id}/name")
def get_file_name(datastore_id: int, file_id: int, session: Session = Depends(get_session)):
    """
    Get the filename for a specific file_id in a datastore.
    """
    # Check if datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Query file record
    statement = select(FileRecord).where(
        FileRecord.id == file_id,
        FileRecord.datastore_id == datastore_id
    )
    file_record = session.exec(statement).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in database")

    return {"file_name": file_record.filename}