from database import get_session
from Services.document_loader import load_file_with_loader
from models.FileRecord import FileRecord
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlmodel import Session
from pathlib import Path
from models.datastore import DataStore

router = APIRouter()

@router.get("/datastores/{datastore_id}/files/{file_id}/loader/{loader_type}/preview")
def preview_file(datastore_id: int, file_id: int, loader_type:str, session: Session = Depends(get_session)):
    file_record = session.get(FileRecord, file_id)
    if not file_record or file_record.datastore_id != datastore_id:
        raise HTTPException(status_code=404, detail="File not found for datastore")

    datastore = session.get(DataStore, datastore_id)
    
    # Construct file path
    project_root = Path(__file__).resolve().parent.parent.parent
    file_path = project_root / "Data" / str(datastore.name) / file_record.filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Load document content
    docs = load_file_with_loader(file_path,loader_type)
    preview = docs[0].page_content[:1000]  # Limit preview to 1000 characters

    return {
        "filename": file_record.filename,
        "preview": preview,
        "length": len(docs[0].page_content)
    }