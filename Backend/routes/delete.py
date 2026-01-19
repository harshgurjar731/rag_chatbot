# rag_app/backend/routes/datastore.py
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from sqlmodel import select
from database import get_session
from models.datastore import DataStore
from pydantic import BaseModel
from models.FileRecord import FileRecord
from config import CONFIG 
from Evaluation.delete_qna import delete_qna_by_file, delete_qna_by_datastore # ✅ centralized config

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

    # 1.1 Delete all QA pairs for this datastore (covers any orphaned QAs)
    try:
        deleted_qna_count = delete_qna_by_datastore(session, datastore.id)
        print(f"[INFO] Deleted {deleted_qna_count} QA pairs for datastore_id {datastore.id}")
    except Exception as e:
        print(f"[ERROR] Failed to delete QA pairs for datastore_id {datastore.id}: {e}")
        # Proceeding despite error to ensure datastore deletion isn't blocked completely, 
        # or you could raise HTTPException if strict consistency is required.

    # 2️⃣ Get all files for this datastore
    files = session.exec(select(FileRecord).where(FileRecord.datastore_id == datastore_id)).all()

        # 3️⃣ Delete all QA pairs and file records for these files
    for file in files:
        try:
            # Delete QA pairs for this file
            deleted_count = delete_qna_by_file(session, file.id)
            print(f"[INFO] Deleted {deleted_count} QA pairs for file_id {file.id}")

            # Delete the file record itself
            session.delete(file)
            session.commit()
            print(f"[INFO] Deleted file record for file_id {file.id}")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete QA pairs or file record for file_id {file.id}: {str(e)}"
            )
    # 4️⃣ Resolve raw data + chunk folders
    ds_folder = CONFIG["project_root"] / CONFIG["datastore_data_folder"] / str(datastore.name)
    chunks_folder = CONFIG["project_root"] / CONFIG["datastore_data_folder"] / str(datastore.name)

    # 5️⃣ Delete raw datastore folder
    if ds_folder.exists() and ds_folder.is_dir():
        try:
            for file in ds_folder.iterdir():
                if file.is_file():
                    file.unlink()
            ds_folder.rmdir()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete raw folder: {e}")

    # 6️⃣ Delete chunks folder
    if chunks_folder.exists() and chunks_folder.is_dir():
        try:
            for file in chunks_folder.iterdir():
                if file.is_file():
                    file.unlink()
            chunks_folder.rmdir()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete chunks folder: {e}")

    # 7️⃣ Delete datastore record from DB
    session.delete(datastore)
    session.commit()

    return {"message": f"Datastore '{datastore.name}' and its files, QA pairs, and chunks deleted successfully."}
