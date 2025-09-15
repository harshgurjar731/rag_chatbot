# rag_app/backend/routes/datastore.py
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from database import get_session
from models.datastore import DataStore
from pydantic import BaseModel
from config import CONFIG  # ✅ centralized config

router = APIRouter()


class DataStoreCreate(BaseModel):
    name: str
    description: str = ""


@router.delete("/{datastore_id}", response_model=dict)
def delete_datastore(datastore_id: int, session: Session = Depends(get_session)):
    # 1️⃣ Fetch datastore from DB
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # 2️⃣ Resolve raw data + chunk folders
    ds_folder = CONFIG["project_root"] / CONFIG["datastore_data_folder"] / str(datastore.name)
    chunks_folder = CONFIG["project_root"] / CONFIG["datastore_data_folder"]/ str(datastore.name)

    # 3️⃣ Delete raw datastore folder
    if ds_folder.exists() and ds_folder.is_dir():
        try:
            for file in ds_folder.iterdir():
                if file.is_file():
                    file.unlink()
            ds_folder.rmdir()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete raw folder: {e}")

    # 4️⃣ Delete chunks folder
    if chunks_folder.exists() and chunks_folder.is_dir():
        try:
            for file in chunks_folder.iterdir():
                if file.is_file():
                    file.unlink()
            chunks_folder.rmdir()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete chunks folder: {e}")

    # 5️⃣ Delete datastore record from DB
    session.delete(datastore)
    session.commit()

    return {"message": f"Datastore '{datastore.name}' and its chunks deleted successfully."}
