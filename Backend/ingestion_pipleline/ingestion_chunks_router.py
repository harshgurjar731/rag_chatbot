
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from pathlib import Path
from sqlmodel import Session, select
from models.FileRecord import FileRecord, update_document_record
from database import get_session
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from models.datastore import DataStore, update_datastore
from models.FileRecord import DocumentRecord, ChunkRecord
import os
import uuid
from typing import List
from config import CONFIG  # Load .env variables
from langchain_core.documents import Document
from ingestion_pipleline.ingestion_models import DataStoreCreate, ChunkTextResponse, GetDocumentDetailsRequest
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from ingestion_pipleline.Loaders.document_loader import load_document_with_metadata 
from ingestion_pipleline.TextSplitters.document_splitter import split_document

router = APIRouter()



from ingestion_pipleline.ingestion_models import UpsertRequestData, TestRetrievalRequestData
from ingestion_pipleline.Embeddings.embedding_models import create_embedding_model
from ingestion_pipleline.VectorStores.vector_store_generator import create_vector_store
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from ingestion_pipleline.Reranker.reranking_helper import apply_reranker
from sqlmodel import Session, select


@router.post("/datastore/{datastore_id}/upsertDocs")
async def upsertDocs(
    datastore_id: int,
    data: UpsertRequestData,
    session: Session = Depends(get_session),
    ):

    pending_document_ids = session.exec(select(DocumentRecord.id).where((DocumentRecord.datastore_id == datastore_id) & (DocumentRecord.insert_vector_status != True))).all()
    if (len(pending_document_ids) == 0):
        raise HTTPException(status_code=400, detail="No Files pending for upsert")
    chunks_to_be_uploaded = session.exec(select(ChunkRecord).where((ChunkRecord.datastore_id == datastore_id) & (ChunkRecord.document_id.in_(pending_document_ids)))).all()
    list_of_documents: List[Document] = []
    chunk_ids: List[str] = []
    for idx, chunk in enumerate(chunks_to_be_uploaded):
        list_of_documents.append(Document(
            page_content=chunk.text,
            metadata=chunk.metadatas
        ))
        chunk_ids.append(chunk.chunk_index)

    embeddingModel = create_embedding_model(
        provider=data.embedding_provider,
        model_name=data.embedding_model
    )
    print("Embedding Created")

    vectordb = create_vector_store(provider=data.vector_store_provider)
    print("Before Create Collection")
    vectordb.create_collection(
        name=str(datastore_id),
        dimension=384
    )
    print("After Create Collection")
    insert_success = vectordb.insert_docs(
        collection=str(datastore_id),
        documents=list_of_documents,
        chunkids=chunk_ids,
        embedding=embeddingModel
    )

    if (insert_success):
        updateData = {
        "embedding_model": data.embedding_model,
        "embedding_provider": data.embedding_provider,
        "vector_store_provider": data.vector_store_provider,
        "similarity_metric": data.similarity_metric,
        }
        print("Updating DataStore", updateData)
        update_datastore(session=session, store_id=datastore_id, update_data=updateData)
        for doc_id in pending_document_ids:
            updateDocData = {
                "insert_vector_status": True,
            }
            update_document_record(session=session, doc_id=doc_id, update_data=updateDocData)

    print("After Insert Collection")
    
    return True

@router.post("/datastore/{datastore_id}/testRetrieval")
async def test_retrieval(
    datastore_id: int,
    data: TestRetrievalRequestData,
    session: Session = Depends(get_session),
    ):

    embeddingModel = create_embedding_model(
        provider=data.embedding_provider,
        model_name=data.embedding_model
    )
    print("Embedding Created")

    vectordb = create_vector_store(provider=data.vector_store_provider)
    # vector_store already initialized earlier (same collection & embedding)
    results = vectordb.test_retrieval(collection=str(datastore_id), embedding=embeddingModel, queryList= [data.query_str], topk= data.top_k)
    if(data.rerank_enabled): 
        results = apply_reranker(INGESTION_CONFIG["ingestion_reranker_type"], INGESTION_CONFIG["ingestion_reranker_model_name"], data.query_str, results[0], INGESTION_CONFIG["ingestion_reranker_topk"])

    return results

    
@router.post("/document/processChunks", response_model=ChunkTextResponse)
async def process_chunks(
    data: DocumentRecord,
    session: Session = Depends(get_session)
    ):

    document = session.exec(select(DocumentRecord).where(DocumentRecord.id == data.id)).first()
    print("Received document details:", document)   

    list_of_documets = load_document_with_metadata(document)
    print("Loaded Docs", list_of_documets.count)    
    splitted_chunks = split_document(document, list_of_documets)
    print("Splitted Docs", splitted_chunks.count)    
    

    chunk_texts: List[str] = []
    chunk_ids = [str(uuid.uuid4()) for _ in range(len(splitted_chunks))]

    # 4️⃣ Store in SQL DB too
    for idx, chunk in enumerate(splitted_chunks):
        chunk_record = ChunkRecord(
            datastore_id=document.datastore_id,
            document_id=document.id,
            chunk_index=chunk_ids[idx],
            text=chunk.page_content,
            metadatas=chunk.metadata
        )
        chunk_texts.append(chunk.page_content)
        session.add(chunk_record)
    session.commit()
    return ChunkTextResponse(chunks=chunk_texts)


@router.post("/document/getChunks")
async def preview_chunks(
    data: GetDocumentDetailsRequest,
    previewLimit: int = 0,
    session: Session = Depends(get_session)
    ):
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

    documentDetailsObj = DocumentRecord.model_validate_json(documentDetails)
    datastore_temp_root = INGESTION_CONFIG["ingestion_root"] / INGESTION_CONFIG["ingestion_temp_folder_name"]
    os.makedirs(datastore_temp_root, exist_ok=True)

    file_path = datastore_temp_root / file.filename
    print("Received document details:", documentDetailsObj)   
    print("Temp document path:", file_path) 
    file_bytes = file.file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    print("File saved at: ", file_path)
    documentDetailsObj.filePath = str(file_path)


    list_of_documets = load_document_with_metadata(documentDetailsObj)
    splitted_chunks = split_document(documentDetailsObj, list_of_documets)
    print("Splitted Docs", len(splitted_chunks))    
    
    requested_chunks = splitted_chunks[:previewLimit]

    # ✅ Delete the uploaded file after processing
    if os.path.exists(file_path):
        os.remove(file_path)
        print("Temporary file deleted:", file_path)
    
    # Extract only the text of each chunk
    chunk_texts = [chunk.page_content for chunk in requested_chunks]

    return ChunkTextResponse(chunks=chunk_texts)