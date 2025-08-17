
from pydantic import BaseModel
from Services.url_query import scrape_and_save_website
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

# --- Response Model ---
class ScrapeResponse(BaseModel):
    url: str
    file_path: str
    message: str


@router.post("/{datastore_id}", response_model=ScrapeResponse)
async def scrape_website(
    datastore_id: int,
    url: str = Query(..., description="Website URL to scrape"),
    session: Session = Depends(get_session)
):
    """
    Scrape website content and process it (save, preview, chunk, embed) 
    directly without making an extra upload API call.
    """

    # ✅ Validate datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # ✅ Resolve physical path
    project_root = Path(__file__).resolve().parent.parent.parent
    ds_folder = project_root / "Data" / str(datastore.name)
    if not ds_folder.exists():
        raise HTTPException(status_code=500, detail="Datastore folder not found")

    # ✅ Scrape → save file
    file_path = scrape_and_save_website(url, ds_folder)
    file_path = Path(file_path) 

    # ✅ Save metadata in DB
    file_bytes = file_path.read_bytes()
    file_record = FileRecord(
        filename=file_path.name,
        content_type="text/plain",
        size=len(file_bytes),
        datastore_id=datastore_id
    )
    session.add(file_record)
    session.commit()
    session.refresh(file_record)

    # === PREVIEW LOGIC ===
    try:
        loader_type = file_path.suffix.lstrip(".")  # e.g., "txt", "html"
        docs = load_file_with_loader(file_path, loader_type)
        preview = docs[0].page_content[:1000]
        length = len(docs[0].page_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")

    # === CHUNKING LOGIC ===
    try:
        json_path = file_path.with_suffix('.json')
        if not json_path.exists():
            raise HTTPException(status_code=404, detail=f"JSON file not found: {json_path}")

        docs_from_json = load_docs_from_json(json_path)
        chunks = chunk_documents(docs_from_json, method="recursive", chunk_size=512, chunk_overlap=50)

        chunks_file_path = ds_folder / f"{file_path.stem}_chunks.json"
        save_chunks_to_json(chunks, chunks_file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunking failed: {str(e)}")

    # === EMBEDDING LOGIC ===
    try:
        model_name = "all-MiniLM-L6-v2"
        vector_db = "faiss"
        embed_and_store(chunks_file_path, file_record.id, model_name, vector_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

    # ✅ Final response
    return {
         "url": url,
         "file_path": str(file_path),   # match response_model
         "file_id": file_record.id,
         "message": "Website scraped, file uploaded, and processed successfully"
    }
   
    

        