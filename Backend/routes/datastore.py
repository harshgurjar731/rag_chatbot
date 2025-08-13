# rag_app/backend/routes/datastore.py
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException,Query
from sqlmodel import Session, select
from database import get_session
from models.datastore import DataStore
from typing import List
from pydantic import BaseModel
from models.FileRecord import FileRecord  

router = APIRouter()

class DataStoreCreate(BaseModel):
    name: str
    description: str = ""


@router.post("/", response_model=DataStore)
def create_datastore(data: DataStoreCreate, session: Session = Depends(get_session)):
    # Check for duplicate name
    existing = session.exec(select(DataStore).where(DataStore.name == data.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Datastore already exists")

    new_store = DataStore(name=data.name, description=data.description)
    session.add(new_store)
    session.commit()
    session.refresh(new_store)

    # Create physical folder on disk
    # Adjust this path to go OUTSIDE backend/
    project_root = Path(__file__).resolve().parent.parent.parent
    data_root = project_root / "Data"
    storage_root = data_root
    storage_root.mkdir(exist_ok=True)
    ds_folder = storage_root / str(new_store.name)
    ds_folder.mkdir(parents=True, exist_ok=True)
    #print(f"Created datastore folder: {ds_folder}")
    #new_store.storage_path = str(ds_folder)
    #session.add(new_store)
    #session.commit()
    return new_store

@router.get("/", response_model=List[DataStore])
def list_datastores(session: Session = Depends(get_session)):
    return session.exec(select(DataStore)).all()

@router.delete("/{datastore_id}", response_model=dict)
def delete_datastore(datastore_id: int, session: Session = Depends(get_session)):
    # Get the datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Get associated files
    files = session.exec(select(FileRecord).where(FileRecord.datastore_id == datastore_id)).all()

    # Path to physical directory
    project_root = Path(__file__).resolve().parent.parent.parent
    ds_folder = project_root / "Data" / str(datastore.name)

    # Delete physical files
    for file in files:
        file_path = ds_folder / file.filename
        if file_path.exists():
            os.remove(file_path)

    # Remove file records from DB
    for file in files:
        session.delete(file)

    # Delete datastore
    session.delete(datastore)
    session.commit()

    return {"message": f"Datastore {datastore.name} and all associated files deleted."}


@router.put("/{datastore_id}", response_model=DataStore)
def update_datastore_chatbot_id(
    datastore_id: int,
    chatbot_id: str = Query(...),  # ⬅️ Now accepted as a query parameter
    session: Session = Depends(get_session)
):
    # Get the datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Update chatbotId
    datastore.chatbotId = chatbot_id
    session.add(datastore)
    session.commit()
    session.refresh(datastore)

    return datastore