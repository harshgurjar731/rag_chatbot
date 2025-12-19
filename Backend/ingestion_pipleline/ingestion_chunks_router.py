
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
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
from ingestion_pipleline.ingestion_models import DataStoreCreate, ChunkTextResponse, GetDocumentDetailsRequest, ProcessDocumentResponse
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from ingestion_pipleline.Loaders.document_loader import load_document_with_metadata 
from ingestion_pipleline.TextSplitters.document_splitter import split_document
import base64
from io import BytesIO
from PIL import Image
import tempfile


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
    list_of_text_documents: List[Document] = []
    list_of_img_documents: List[Document] = []
    text_chunk_ids: List[str] = []
    img_chunk_ids: List[str] = []
    for idx, chunk in enumerate(chunks_to_be_uploaded):
        if (chunk.metadatas["content_type"] == "image"):
            list_of_img_documents.append(Document(
                page_content=chunk.text,
                metadata=chunk.metadatas
            ))
            img_chunk_ids.append(chunk.chunk_index)
        else:
            list_of_text_documents.append(Document(
                page_content=chunk.text,
                metadata=chunk.metadatas
            ))
            text_chunk_ids.append(chunk.chunk_index)

    if(len(list_of_text_documents) > 0):
        embeddingModel = create_embedding_model(
            provider=data.embedding_provider,
            model_name=data.embedding_model
        )
        print("Embedding Created")

        vectordb = create_vector_store(provider=data.vector_store_provider)
        print("Before Create Collection")
        vectordb.create_collection(
            name=f"datastore_{datastore_id}",
            embedding=embeddingModel
        )
        print("After Create Collection")
        insert_success = vectordb.insert_docs(
            collection=f"datastore_{datastore_id}",
            documents=list_of_text_documents,
            chunkids=text_chunk_ids,
            embedding=embeddingModel
        )
    if(len(list_of_img_documents) > 0):
        embeddingModel = create_embedding_model(
            provider=data.embedding_provider,
            model_name=data.embedding_model  #TODOANKIT: Replace with image_embedding_model -> when supporting multiple models for text and image
        )

        print("Embedding Model Created", img_chunk_ids)
        vectordb = create_vector_store(provider=data.vector_store_provider)
        print("Before Create Collection")
        vectordb.create_collection(
            name=f"datastore_{datastore_id}_image",
            embedding=embeddingModel
        )
        list_img_uri: List[str] = []
        list_metadata: List[dict] = []
        for id, imageDoc in enumerate(list_of_img_documents):
            list_img_uri.append(imageDoc.metadata["source"])
            list_metadata.append({"page_content": imageDoc.page_content, "metadata": imageDoc.metadata})

        embeddingVectors = embeddingModel.embed_image(uris=list_img_uri)
        print("After Create Collection", embeddingVectors)
        insert_success = vectordb.insert_vectors(
            collection=str(datastore_id) + "_image",
            vectors=embeddingVectors,
            metadata=list_metadata,
            chunk_ids=img_chunk_ids
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

    if (data.is_vision_search == True):
        embeddingModel = create_embedding_model(
            provider=data.embedding_provider,
            model_name=data.embedding_model, #TODOANKIT: Replace with image_embedding_model -> when supporting multiple models for text and image
        )
        if(data.image_base64 and len(data.image_base64)):
            print("In Image embedding flow")
            b64_string = data.image_base64.split(",", 1)[1]
            image_bytes = base64.b64decode(b64_string)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")  
            temp_file.write(image_bytes)
            temp_file.close()
            queries_embedded = embeddingModel.embed_image([temp_file.name])
        else:
            queries_embedded = embeddingModel.embed_documents([data.query_str])
    else:
        embeddingModel = create_embedding_model(
            provider=data.embedding_provider,
            model_name=data.embedding_model
        )
        queries_embedded = embeddingModel.embed_documents([data.query_str])

    vectordb = create_vector_store(provider=data.vector_store_provider)
    collection_name = str(datastore_id) if data.is_vision_search == False else str(datastore_id) + "_image"
    # vector_store already initialized earlier (same collection & embedding)
    print("Collection Name", collection_name)
    results = vectordb.retrieve_docs_for_embeddings(collection=collection_name, embeddings=queries_embedded, topk= data.top_k)
    print(results)
    # if(data.rerank_enabled and data.is_vision_search):
        
    # else if(data.rerank_enabled):
    results = apply_reranker(INGESTION_CONFIG["ingestion_reranker_type"], INGESTION_CONFIG["ingestion_reranker_model_name"], data.query_str, results[0], INGESTION_CONFIG["ingestion_reranker_topk"])

    return results

#@router.post("/document/process", response_model=ProcessDocumentResponse)
# async def process_document(
#     data: DocumentRecord,
#     session: Session = Depends(get_session)
#     ):
#     document = session.exec(select(DocumentRecord).where(DocumentRecord.id == data.id)).first()

#     file_extension = document.filename.lower().split('.')[-1]

#     if (file_extension in ["jpg", "jpeg", "png", "bmp"]):
#         return ProcessDocumentResponse(success=True, chunks=[])
#     else:
#         chunks = process_text_document(document=document, session=session)
#         return ProcessDocumentResponse(success=True, chunks=chunks)

    
# @router.post("/document/process", response_model=List[ProcessDocumentResponse])
# async def process_document(
#     documentRecord: List[DocumentRecord],
#     session: Session = Depends(get_session)
#     ) -> List[str]:

#     processed_doc_responses = []
#     for idx, doc in enumerate(documentRecord):    
#         document = session.exec(select(DocumentRecord).where(DocumentRecord.id == doc.id)).first()
#         print("Received document details:", document)   

#         list_of_documets = load_document_with_metadata(document)
#         splitted_chunks = split_document(document, list_of_documets)
        

#         chunk_texts: List[str] = []
#         chunk_ids = [str(uuid.uuid4()) for _ in range(len(splitted_chunks))]

#         # 4️⃣ Store in SQL DB too
#         for idx, chunk in enumerate(splitted_chunks):
#             chunk_record = ChunkRecord(
#                 datastore_id=document.datastore_id,
#                 document_id=document.id,
#                 chunk_index=chunk_ids[idx],
#                 text=chunk.page_content,
#                 metadatas=chunk.metadata
#             )
#             chunk_texts.append(chunk.page_content)
#             print("CHUNK_RECORD", chunk_record)
#             session.add(chunk_record)
#         session.commit()
#         processed_doc_responses.append(ProcessDocumentResponse(success=True, chunks=chunk_texts))
#     return processed_doc_responses

@router.post("/document/process", response_model=List[ProcessDocumentResponse])
async def process_document(
    documentRecord: List[DocumentRecord],
    session: Session = Depends(get_session)
):

    # 1️⃣ Batch fetch all docs
    ids = [d.id for d in documentRecord]
    db_docs = session.exec(
        select(DocumentRecord).where(DocumentRecord.id.in_(ids))
    ).all()

    responses = []

    for document in db_docs:

        # 2️⃣ Move CPU-heavy operations off event loop
        list_of_documents = await run_in_threadpool(
            load_document_with_metadata, document
        )
        
        splitted_chunks = await run_in_threadpool(
            split_document, document, list_of_documents
        )

        # 3️⃣ Prepare bulk insert
        chunk_records = [
            ChunkRecord(
                datastore_id=document.datastore_id,
                document_id=document.id,
                chunk_index=str(uuid.uuid4()),
                text=chunk.page_content,
                metadatas=chunk.metadata
            )
            for chunk in splitted_chunks
        ]

        # 4️⃣ Bulk insert
        session.add_all(chunk_records)
        session.commit()

        responses.append(
            ProcessDocumentResponse(
                success=True,
                chunks=[c.text for c in chunk_records]
            )
        )

    return responses


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