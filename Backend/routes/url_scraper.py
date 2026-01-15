"""
API route for URL scraping.

This module provides an endpoint to scrape a website and ingest the content
directly into a datastore.
"""
# rag_app/backend/routes/url_scraper.py

from pydantic import BaseModel
from Services.url_query import scrape_and_save_website
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session
from pathlib import Path
from database import get_session
from models.datastore import DataStore
from models.FileRecord import FileRecord
from Services.document_loader import load_file_with_loader
from Services.embedding_service import embed_and_store
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from config import CONFIG  # ✅ centralized config

router = APIRouter()


# --- Response Model ---
class ScrapeResponse(BaseModel):
    url: str
    file_path: str
    file_id: int
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

    Args:
        datastore_id (int): ID of the datastore.
        url (str): The URL to scrape.
        session (Session): Database session.

    Returns:
        ScrapeResponse: Details of the scraped file.

    Raises:
        HTTPException: If datastore not found or processing fails.
    """

    # ✅ Validate datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # ✅ Resolve physical path using config
    ds_folder = (
        CONFIG["project_root"]
        / CONFIG["datastore_data_folder"]
        / str(datastore.name)
    )
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
        datastore_id=datastore_id,
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
        json_path = file_path.with_suffix(".json")
        if not json_path.exists():
            raise HTTPException(status_code=404, detail=f"JSON file not found: {json_path}")

        docs_from_json = load_docs_from_json(json_path)
        chunks = chunk_documents(
            docs_from_json,
            method=CONFIG["default_chunk_method"],
            chunk_size=CONFIG["default_chunk_size"],
            chunk_overlap=CONFIG["default_chunk_overlap"],
        )

        chunks_file_path = (
            CONFIG["project_root"]
            / CONFIG["datastore_data_folder"]
            / str(datastore.name)
            / f"{file_path.stem}_chunks.json"
        )
        save_chunks_to_json(chunks, chunks_file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunking failed: {str(e)}")

    # === EMBEDDING LOGIC ===
    try:
        model_name = CONFIG["default_embedding_model"]
        vector_db = CONFIG["default_vector_db"]
        embed_and_store(chunks_file_path, file_record.id, model_name, vector_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

    # ✅ Final response
    return {
        "url": url,
        "file_path": str(file_path),   # match response_model
        "file_id": file_record.id,
        "message": "Website scraped, file uploaded, and processed successfully",
    }
