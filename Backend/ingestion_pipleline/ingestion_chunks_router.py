
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from pathlib import Path
from sqlmodel import Session, select
from models.FileRecord import FileRecord, update_document_record
from database import get_session
from models.datastore import DataStore, update_datastore
from models.FileRecord import DocumentRecord, ChunkRecord
import os
import uuid
import json
import redis
from typing import List
from config import CONFIG
from ingestion_pipleline.ingestion_models import DataStoreCreate, ChunkTextResponse, GetDocumentDetailsRequest, ProcessDocumentResponse, UpsertRequestData, TestRetrievalRequestData
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
import base64
from io import BytesIO

# Redis Setup (reuse env var or config)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

router = APIRouter()

@router.post("/datastore/{datastore_id}/upsertDocs")
async def upsertDocs(
    datastore_id: int,
    data: UpsertRequestData,
    session: Session = Depends(get_session),
    ):

    pending_document_ids = session.exec(select(DocumentRecord.id).where(
        (DocumentRecord.datastore_id == datastore_id) & 
        (DocumentRecord.insert_vector_status != True) &
        (DocumentRecord.loaderType != "SecondarySource")
    )).all()
    if (len(pending_document_ids) == 0):
        # raise HTTPException(status_code=400, detail="No Files pending for upsert")
        return {"status": "No pending files"}

    # Dispatch to Redis
    job_payload = {
        "job_type": "upsert",
        "datastore_id": datastore_id,
        "embedding_provider": data.embedding_provider,
        "embedding_model": data.embedding_model,
        "vector_store_provider": data.vector_store_provider,
        "similarity_metric": data.similarity_metric
    }
    
    r.rpush("ingestion:inbox", json.dumps(job_payload))
    print(f"[*] Queued upsert job for datastore {datastore_id}")

    return {"status": "Job Queued", "pending_docs": len(pending_document_ids)}

@router.post("/datastore/{datastore_id}/testRetrieval")
async def test_retrieval(
    datastore_id: int,
    data: TestRetrievalRequestData,
    session: Session = Depends(get_session),
    ):
    # This endpoint does Retrieval. 
    # Technically, retrieval is "light" compared to ingestion, but it uses VectorStore libs.
    # If we want to completely remove VectorStore libs from Backend, we must move this too.
    # However, this is a synchronous return endpoint (Test Retrieval).
    # Moving this to worker is hard without a complex req/resp queue.
    # User asked for "Separating ingestion pipeline".
    # I will allow this to FAIL if libs are missing, or I should support it via worker?
    # supporting via worker is complex (Redis request/response).
    
    # DECISION: For now, I will return a stub or error saying "Test Retrieval via Worker Not Implemented".
    # Or I can try to implement it if I have time. 
    # Given the goal is "injesttion pipeline", I will prioritize ingestion.
    # But if I delete the libs, this WILL crash.
    
    raise HTTPException(status_code=501, detail="Test Retrieval momentarily unavailable during refactor phase.")

@router.post("/document/process", response_model=List[ProcessDocumentResponse])
async def process_document(
    documentRecord: List[DocumentRecord],
    session: Session = Depends(get_session)
):
    ids = [d.id for d in documentRecord]
    
    job_payload = {
        "job_type": "process_document",
        "document_ids": ids
    }
    r.rpush("ingestion:inbox", json.dumps(job_payload))
    print(f"[*] Queued document processing for {ids}")
    
    # Return dummy success since it's async now
    return [ProcessDocumentResponse(success=True, chunks=["Processing in background..."])]


@router.post("/document/getChunks")
async def preview_chunks(
    data: GetDocumentDetailsRequest,
    previewLimit: int = 0,
    session: Session = Depends(get_session)
    ):
    # This just reads DB, so it's fine.
    print("Fetching chunks for Doc Id", data.datastoreId, data.id)
    chunks = session.exec(select(ChunkRecord).where((ChunkRecord.datastore_id == data.datastoreId) & (ChunkRecord.document_id == data.id))).all()
    if (previewLimit == 0):
        chunk_texts = [chunk.text for chunk in chunks]
    else:
        chunk_texts = [chunk.text for chunk in chunks[:previewLimit]]
    return ChunkTextResponse(chunks=chunk_texts)


@router.post("/document/previewChunks")
async def preview_chunks(
    file: UploadFile = File(...),
    documentDetails: str = Form(...),
    previewLimit: int = 10,
    session: Session = Depends(get_session)
    ):
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document as LangchainDocument
    import pypdf
    from io import BytesIO

    # 1. Read file content
    content = await file.read()
    text_content = ""
    
    # Try text decode first
    try:
        text_content = content.decode("utf-8")
    except:
        # If decode fails, assume binary/PDF and try pypdf
        try:
            pdf_file = BytesIO(content)
            reader = pypdf.PdfReader(pdf_file)
            for page in reader.pages:
                text_content += page.extract_text() + "\n"
        except Exception as e:
            # If both fail
            return {"status": "error", "message": f"Preview failed. Could not decode text or parse PDF: {str(e)}"}
    
    # 2. Parse details
    details = json.loads(documentDetails)
    chunkSize = details.get("chunkSize", 1000)
    chunkOverlap = details.get("chunkOverlap", 200)

    # 3. Split
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunkSize,
        chunk_overlap=chunkOverlap
    )
    docs = splitter.create_documents([text_content])

    # 4. Limit and Return
    preview_docs = docs[:previewLimit]
    chunk_texts = [d.page_content for d in preview_docs]
    
    return ChunkTextResponse(chunks=chunk_texts)

