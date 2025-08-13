# rag_app/backend/routes/datastore.py
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from database import get_session
from models.datastore import DataStore
from typing import List
from pydantic import BaseModel

router = APIRouter()

class DataStoreCreate(BaseModel):
    name: str
    description: str = ""


@router.delete("/{datastore_id}", response_model=dict)
def delete_datastore(datastore_id: int, session: Session = Depends(get_session)):
    # Fetch datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Determine folder path
    project_root = Path(__file__).resolve().parent.parent.parent
    ds_folder = project_root / "Data" / str(datastore.name)

    # Attempt to delete folder if it exists
    if ds_folder.exists() and ds_folder.is_dir():
        try:
            for file in ds_folder.iterdir():
                file.unlink()
            ds_folder.rmdir()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete folder: {e}")

    # Delete from database
    session.delete(datastore)
    session.commit()

    return {"message": f"Datastore '{datastore.name}' deleted successfully."}
