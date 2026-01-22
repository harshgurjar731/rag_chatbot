# rag_app/backend/routes/embeddings.py
from fastapi import APIRouter, Query, HTTPException, Depends
from Services.embedding_service import embed_and_store, check_embeddings_status, delete_vector_store
from pathlib import Path
from sqlmodel import Session
from database import get_session
from models.FileRecord import FileRecord
from models.datastore import DataStore
from config import CONFIG  # centralized config

router = APIRouter()


@router.post("/embedding/store")
def store_embeddings(
    datastore_id: int,
    file_id: int,
    model_name: str = Query(CONFIG["default_embedding_model"], description="Embedding model"),
    vector_db: str = Query(CONFIG["default_vector_db"], description="Vector DB name"),
    session: Session = Depends(get_session),
):
    # 1️⃣ Validate file
    file = session.get(FileRecord, file_id)
    if not file or file.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found in specified datastore")

    # 2️⃣ Get datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 3️⃣ Construct chunk file path dynamically (uses CHUNKS_FOLDER now)
    name_without_extension = file.filename.rsplit(".", 1)[0]
    chunks_file_path = (
    CONFIG["project_root"]
    /CONFIG["datastore_data_folder"]
    / str(datastore.name)
    / f"{name_without_extension}_chunks.json")

    if not chunks_file_path.exists():
        raise HTTPException(status_code=404, detail=f"Chunk file not found: {chunks_file_path}")

    # 4️⃣ Perform embedding
    try:
        result = embed_and_store(chunks_file_path, file_id, model_name, vector_db)
        return {"status": "success", "vector_db": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datastore/embedding/check")
def check_embeddings(
    file_id: int,
    model_name: str = Query(CONFIG["default_embedding_model"], description="Embedding model"),
    vector_db: str = Query(CONFIG["default_vector_db"], description="Vector DB name"),
):
    try:
        result = check_embeddings_status(file_id, vector_db, model_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/embedding/vector/delete")
def delete_vectors_for_file(
    datastore_id: int,
    file_id: int,
    vector_db: str = Query(CONFIG["default_vector_db"], description="Vector DB name"),
    session: Session = Depends(get_session),
):
    # 1️⃣ Validate file
    file = session.get(FileRecord, file_id)
    if not file or file.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found in specified datastore")

    # 2️⃣ Attempt vector deletion
    try:
        delete_vector_store(file_id, vector_db)
        return {"status": "success", "message": f"Vectors deleted for file_id={file_id} from {vector_db}"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
