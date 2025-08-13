# backend/routes/upload.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends,Query
from sqlmodel import Session
from uuid import UUID
from pathlib import Path
from typing import List
from database import get_session
from models.datastore import DataStore
from models.FileRecord import FileRecord  # already imported above
from sqlmodel import select
from fastapi import status
import os
from fastapi.responses import FileResponse
from Services.document_loader import load_file_with_loader
from Services.embedding_service import embed_and_store, check_embeddings_status,  delete_vector_store
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json



router = APIRouter()
""""
#@router.post("/datastores/{datastore_id}/upload")
@router.post("/datastores/{datastore_id}/upload")
def upload_file_to_datastore(datastore_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)):
    # Validate datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Resolve physical path
    project_root = Path(__file__).resolve().parent.parent.parent
    ds_folder = project_root / "Data" / str(datastore.name)
    if not ds_folder.exists():
        raise HTTPException(status_code=500, detail="Datastore folder not found")

    # Save file
    file_path = ds_folder / file.filename
    file_bytes = file.file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    #return {"message": "File uploaded successfully", "filename": file.filename}

    # Record metadata in DB
    file_record = FileRecord(
        filename=file.filename,
        content_type=file.content_type,
        size=len(file_bytes),
        datastore_id=datastore_id
    )
    session.add(file_record)
    session.commit()
    session.refresh(file_record)

    return {
        "message": "File uploaded and recorded",
        "file_id": file_record.id,
        "filename": file_record.filename
    }

"""



#@router.post("/datastores/{datastore_id}/upload")
@router.post("/datastores/{datastore_id}/upload")
def upload_file_to_datastore(datastore_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)):
    # Validate datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Resolve physical path
    project_root = Path(__file__).resolve().parent.parent.parent
    ds_folder = project_root / "Data" / str(datastore.name)
    if not ds_folder.exists():
        raise HTTPException(status_code=500, detail="Datastore folder not found")

    # Save file
    file_path = ds_folder / file.filename
    file_bytes = file.file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    #return {"message": "File uploaded successfully", "filename": file.filename}

    # Record metadata in DB
    file_record = FileRecord(
        filename=file.filename,
        content_type=file.content_type,
        size=len(file_bytes),
        datastore_id=datastore_id
    )
    session.add(file_record)
    session.commit()
    session.refresh(file_record)

     # === PREVIEW LOGIC CALL (formerly its own API) ===
    try:
        file_path = project_root / "Data" / str(datastore.name) / file_record.filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        # You can hardcode or extract loader_type from file extension
        loader_type = file.filename.split(".")[-1]  # e.g., 'pdf', 'docx'

        docs = load_file_with_loader(file_path, loader_type)
        preview = docs[0].page_content[:1000]
        length = len(docs[0].page_content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")
    
     # === 6. Chunking Logic ===
    try:
        # Resolve JSON path
        json_path = file_path.with_suffix('.json')
        if not json_path.exists():
            raise HTTPException(status_code=404, detail=f"JSON file not found: {json_path}")

        # Load and chunk
        docs_from_json = load_docs_from_json(json_path)
        chunks = chunk_documents(docs_from_json, method="recursive", chunk_size=512, chunk_overlap=50)

        # Save chunks
        chunks_file_path = ds_folder / f"{file.filename.rsplit('.', 1)[0]}_chunks.json"
        save_chunks_to_json(chunks, chunks_file_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunking failed: {str(e)}")
    
    # === 7. Store Embeddings Logic ===
    try:
        model_name = "all-MiniLM-L6-v2"
        vector_db = "faiss"
        chunks_for_embedding_path = chunks_file_path  # already defined above
        result = embed_and_store(chunks_for_embedding_path, file_record.id, model_name, vector_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

    return {
        "message": "File uploaded and recorded",
        "file_id": file_record.id,
        "filename": file_record.filename
    }

@router.get("/datastores/{datastore_id}/files", response_model=List[FileRecord])
def list_files_in_datastore(datastore_id: int, session: Session = Depends(get_session)):
    # Check if datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Query all files linked to this datastore
    files = session.exec(
        select(FileRecord).where(FileRecord.datastore_id == datastore_id)
    ).all()

    return files

# @router.delete("/datastores/{datastore_id}/files/{file_id}", status_code=status.HTTP_200_OK)
# def delete_file_from_datastore(datastore_id: int, file_id: int, session: Session = Depends(get_session)):
#     # Validate datastore
#     datastore = session.get(DataStore, datastore_id)
#     if not datastore:
#         raise HTTPException(status_code=404, detail="Datastore not found")

#     # Validate file record
#     file_record = session.get(FileRecord, file_id)
#     if not file_record or file_record.datastore_id != datastore_id:
#         raise HTTPException(status_code=404, detail="File not found in this datastore")

#     # Resolve file path
#     project_root = Path(__file__).resolve().parent.parent.parent
#     file_path = project_root / "Data" / str(datastore.name) / file_record.filename

#     # Attempt to delete file from filesystem
#     try:
#         if file_path.exists():
#             file_path.unlink()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

#     # Remove DB record
#     session.delete(file_record)
#     session.commit()

#     return {
#         "message": "File deleted successfully",
#         "file_id": file_id,
#         "filename": file_record.filename
#     }


@router.delete("/datastores/{datastore_id}/files/{file_id}", status_code=status.HTTP_200_OK)
def delete_file_from_datastore(
    datastore_id: int,
    file_id: int,
    vector_db: str = Query("faiss", description="Vector DB name"),
    session: Session = Depends(get_session)
):
    # 1. Validate datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 2. Validate file record
    file_record = session.get(FileRecord, file_id)
    if not file_record or file_record.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found in this datastore")

    # 3. Resolve paths
    project_root = Path(__file__).resolve().parent.parent.parent
    data_folder = project_root / "Data" / str(datastore.name)
    original_file_path = data_folder / file_record.filename
    preview_file_path = original_file_path.with_suffix(".json")
    chunk_file_path = data_folder / (file_record.filename.rsplit('.', 1)[0] + "_chunks.json")

    # 4. Delete original file
    try:
        if original_file_path.exists():
            original_file_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete original file: {str(e)}")

    # 5. Delete preview file
    try:
        if preview_file_path.exists():
            preview_file_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete preview file: {str(e)}")

    # 6. Delete chunked file
    try:
        if chunk_file_path.exists():
            chunk_file_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chunked file: {str(e)}")

    # 7. Delete vector embeddings
    try:
        delete_vector_store(file_id, vector_db)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete vectors: {str(e)}")

    # 8. Remove DB record
    session.delete(file_record)
    session.commit()

    return {
        "message": "File, preview, chunked data, and vectors deleted successfully",
        "file_id": file_id,
        "filename": file_record.filename
    }

@router.get("/datastores/{datastore_id}/files/{filename}", response_class=FileResponse)
def get_file(datastore_id: int, filename: str, session: Session = Depends(get_session)):
    # Validate datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Validate file record exists
    statement = select(FileRecord).where(
        FileRecord.filename == filename,
        FileRecord.datastore_id == datastore_id
    )
    file_record = session.exec(statement).first()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in database")

    # Resolve file path
    project_root = Path(__file__).resolve().parent.parent.parent
    file_path = project_root / "Data" / str(datastore.name) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=file_record.content_type or "application/octet-stream"
        # media_type="application/octet-stream",
        # headers={"Content-Disposition": f"attachment; filename={filename}"}

    )

@router.delete("/datastores/{datastore_id}/files/{filename}")
def delete_file(datastore_id: int, filename: str, session: Session = Depends(get_session)):
    # 1. Validate datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 2. Validate file record exists in DB
    statement = select(FileRecord).where(
        FileRecord.filename == filename,
        FileRecord.datastore_id == datastore_id
    )
    file_record = session.exec(statement).first()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in database")

    # 3. Delete the physical file from disk
    project_root = Path(__file__).resolve().parent.parent.parent
    file_path = project_root / "Data" / str(datastore.name) / filename

    if file_path.exists():
        try:
            os.remove(file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="File not found on disk")

    # 4. Delete the file record from DB
    session.delete(file_record)
    session.commit()

    return {"detail": f"File '{filename}' deleted successfully"}


@router.get("/datastores/{datastore_id}/files/{filename}/id")
def get_file_id(datastore_id: int, filename: str, session: Session = Depends(get_session)):
    # 1. Check if the datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 2. Fetch the file record by filename and datastore_id
    statement = select(FileRecord).where(
        FileRecord.filename == filename,
        FileRecord.datastore_id == datastore_id
    )
    file_record = session.exec(statement).first()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in database")

    # 3. Return the file ID
    return {"file_id": file_record.id}