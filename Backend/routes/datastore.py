# rag_app/backend/routes/datastore.py
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from database import get_session
from models.datastore import DataStore
from typing import List
from pydantic import BaseModel
from models.FileRecord import FileRecord
from config import CONFIG  # ✅ centralized config
from Evaluation.delete_qna import delete_qna_by_datastore  # ✅ Import deletion utility

router = APIRouter()


class DataStoreCreate(BaseModel):
    name: str
    description: str = ""


@router.post("/", response_model=DataStore)
def create_datastore(data: DataStoreCreate, session: Session = Depends(get_session)):
    # 1️⃣ Check for duplicate name
    existing = session.exec(select(DataStore).where(DataStore.name == data.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Datastore already exists")

    # 2️⃣ Create datastore record
    new_store = DataStore(name=data.name, description=data.description)
    session.add(new_store)
    session.commit()
    session.refresh(new_store)

    # 3️⃣ Create physical datastore + chunks folders
    datastore_root = CONFIG["project_root"] / CONFIG["datastore_data_folder"]
    datastore_root.mkdir(exist_ok=True)
    ds_folder = datastore_root / str(new_store.name)
    ds_folder.mkdir(parents=True, exist_ok=True)

    chunks_root = CONFIG["project_root"] / CONFIG["datastore_data_folder"]
    chunks_root.mkdir(exist_ok=True)
    chunks_ds_folder = chunks_root / str(new_store.name)
    chunks_ds_folder.mkdir(parents=True, exist_ok=True)

    return new_store


@router.get("/", response_model=List[DataStore])
def list_datastores(session: Session = Depends(get_session)):
    return session.exec(select(DataStore)).all()


@router.delete("/{datastore_id}", response_model=dict)
def delete_datastore(datastore_id: int, session: Session = Depends(get_session)):
    # 1️⃣ Get datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 2️⃣ Get associated files
    files = session.exec(select(FileRecord).where(FileRecord.datastore_id == datastore_id)).all()

    # 3️⃣ Resolve paths
    ds_folder = CONFIG["project_root"] / CONFIG["datastore_data_folder"] / str(datastore.name)
    chunks_ds_folder = CONFIG["project_root"] / CONFIG["datastore_data_folder"]/ str(datastore.name)

    # 4️⃣ Delete physical files
    for file in files:
        file_path = ds_folder / file.filename
        if file_path.exists():
            os.remove(file_path)

    # 5️⃣ Delete chunked files
    if chunks_ds_folder.exists():
        for chunk_file in chunks_ds_folder.glob("*"):
            chunk_file.unlink()
        try:
            chunks_ds_folder.rmdir()
        except OSError:
            pass  # in case folder isn’t empty

    # 6️⃣ Remove file records from DB
    for file in files:
        session.delete(file)

    # 6a️⃣ Delete associated QA pairs
    try:
        deleted_count = delete_qna_by_datastore(session, datastore_id)
        if deleted_count > 0:
            print(f"[INFO] Deleted {deleted_count} QA pairs for datastore_id {datastore_id}")
    except Exception as e:
        print(f"[ERROR] Failed to delete QA pairs for datastore {datastore_id}: {str(e)}")
        # Proceed with datastore deletion anyway? Or raise? Prefer logging and proceeding to clean up as much as possible.

    # 7️⃣ Delete datastore
    session.delete(datastore)
    session.commit()

    return {"message": f"Datastore {datastore.name} and all associated files deleted."}


@router.put("/{datastore_id}", response_model=DataStore)
def update_datastore_chatbot_id(
    datastore_id: int,
    chatbot_id: str = Query(...),
    session: Session = Depends(get_session),
):
    # 1️⃣ Get datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 2️⃣ Update chatbotId
    datastore.chatbotId = chatbot_id
    session.add(datastore)
    session.commit()
    session.refresh(datastore)

    return datastore
