"""
Ingestion Worker Process.

This script runs as a standalone worker process managed by the ingestion pool.
It listens for ingestion jobs on Redis (ingestion:inbox), processes them (chunking, embedding),
and updates the database/vector store.
"""

import os
import redis
import asyncio
import json
import uuid
import sys
from sqlmodel import create_engine, Session, select
from typing import List

# Ensure we can import from local modules
sys.path.append(os.getcwd())

# Imports
from config import REDIS_HOST, DATABASE_URL
from models.datastore import DataStore, update_datastore
from models.FileRecord import DocumentRecord, ChunkRecord, update_document_record
from langchain_core.documents import Document

# Heavy Lifters (Local)
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from ingestion_pipleline.Loaders.document_loader import load_document_with_metadata 
from ingestion_pipleline.TextSplitters.document_splitter import split_document
from ingestion_pipleline.Embeddings.embedding_models import create_embedding_model
from ingestion_pipleline.VectorStores.vector_store_generator import create_vector_store

# Redis Connection
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# DB Engine
engine = create_engine(DATABASE_URL)

async def process_upsert_job(job_data: dict):
    datastore_id = job_data.get("datastore_id")
    embedding_provider = job_data.get("embedding_provider")
    embedding_model = job_data.get("embedding_model")
    vector_store_provider = job_data.get("vector_store_provider")
    similarity_metric = job_data.get("similarity_metric")

    print(f"[*] Processing UPSERT job for Datastore {datastore_id}")

    with Session(engine) as session:
        # pending_document_ids = session.exec(select(DocumentRecord.id).where((DocumentRecord.datastore_id == datastore_id) & (DocumentRecord.insert_vector_status != True))).all()
        # Better: get the specific documents if passed, or query pending
        
        # Original logic: fetch ALL pending for this datastore
        pending_document_ids = session.exec(select(DocumentRecord.id).where((DocumentRecord.datastore_id == datastore_id) & (DocumentRecord.insert_vector_status != True))).all()
        
        if len(pending_document_ids) == 0:
            print("[*] No pending documents for upsert.")
            return

        # --- Self-Healing: Generate chunks if missing ---
        # Logic: If a doc is pending upsert but has no chunks, it likely skipped 'process_document'.
        # We should generate them now.
        
        # 1. Identify docs with 0 chunks
        chunks_check = session.exec(select(ChunkRecord.document_id).where((ChunkRecord.datastore_id == datastore_id) & (ChunkRecord.document_id.in_(pending_document_ids)))).all()
        docs_with_chunks = set(chunks_check) # Set of IDs
        
        docs_needing_chunks = [doc_id for doc_id in pending_document_ids if doc_id not in docs_with_chunks]
        
        if docs_needing_chunks:
            print(f"[*] Found {len(docs_needing_chunks)} documents missing chunks. Generating now...")
            db_docs_to_process = session.exec(select(DocumentRecord).where(DocumentRecord.id.in_(docs_needing_chunks))).all()
            
            new_chunk_records = []
            for document in db_docs_to_process:
                 print(f"Processing (Lazy Load) doc: {document.filename}")
                 try:
                     list_of_documents = load_document_with_metadata(document)
                     splitted_chunks = split_document(document, list_of_documents)
                     
                     for chunk in splitted_chunks:
                        new_chunk_records.append(ChunkRecord(
                            datastore_id=document.datastore_id,
                            document_id=document.id,
                            chunk_index=str(uuid.uuid4()),
                            text=chunk.page_content,
                            metadatas=chunk.metadata
                        ))
                 except Exception as e:
                     print(f"[!] Error processing doc {document.filename}: {e}")
            
            if new_chunk_records:
                session.add_all(new_chunk_records)
                session.commit()
                print(f"[*] Lazy Chunking Complete. Inserted {len(new_chunk_records)} chunks.")
        
        # 2. Proceed to fetch all chunks (now populated)
        chunks_to_be_uploaded = session.exec(select(ChunkRecord).where((ChunkRecord.datastore_id == datastore_id) & (ChunkRecord.document_id.in_(pending_document_ids)))).all()
        
        list_of_text_documents: List[Document] = []
        list_of_img_documents: List[Document] = []
        text_chunk_ids: List[str] = []
        img_chunk_ids: List[str] = []

        for idx, chunk in enumerate(chunks_to_be_uploaded):
            if chunk.metadatas.get("content_type") == "image":
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

        insert_success = False

        # Text Flow
        if len(list_of_text_documents) > 0:
            embeddingModel = create_embedding_model(
                provider=embedding_provider,
                model_name=embedding_model
            )
            vectordb = create_vector_store(provider=vector_store_provider)
            vectordb.create_collection(
                name=f"datastore_{datastore_id}",
                embedding=embeddingModel
            )
            insert_success = vectordb.insert_docs(
                collection=f"datastore_{datastore_id}",
                documents=list_of_text_documents,
                chunkids=text_chunk_ids,
                embedding=embeddingModel
            )

        # Image Flow
        if len(list_of_img_documents) > 0:
            embeddingModel = create_embedding_model(
                provider=embedding_provider,
                model_name=embedding_model 
            )
            vectordb = create_vector_store(provider=vector_store_provider)
            vectordb.create_collection(
                name=f"datastore_{datastore_id}_image",
                embedding=embeddingModel
            )
            
            list_img_uri: List[str] = []
            list_img_texts: List[str] = []
            list_metadata: List[dict] = []
            for id, imageDoc in enumerate(list_of_img_documents):
                list_img_uri.append(imageDoc.metadata["source"])
                list_img_texts.append(imageDoc.page_content)
                list_metadata.append({"page_content": imageDoc.page_content, "metadata": imageDoc.metadata})

            if hasattr(embeddingModel, "embed_image"):
                embeddingVectors = embeddingModel.embed_image(uris=list_img_uri)
            else:
                embeddingVectors = embeddingModel.embed_documents(list_img_texts)
            
            # Note: insert_success logic merging logic simplified here
            success_img = vectordb.insert_vectors(
                collection=f"datastore_{datastore_id}_image",
                vectors=embeddingVectors,
                metadata=list_metadata,
                chunk_ids=img_chunk_ids
            )
            insert_success = insert_success or success_img

        if insert_success:
            updateData = {
                "embedding_model": embedding_model,
                "embedding_provider": embedding_provider,
                "vector_store_provider": vector_store_provider,
                "similarity_metric": similarity_metric,
            }
            update_datastore(session=session, store_id=datastore_id, update_data=updateData)
            for doc_id in pending_document_ids:
                updateDocData = {
                    "insert_vector_status": True,
                }
                update_document_record(session=session, doc_id=doc_id, update_data=updateDocData)
            
            print(f"[*] Upsert Job Complete for Datastore {datastore_id}")


async def process_document_job(job_data: dict):
    # document_ids should be passed
    document_ids = job_data.get("document_ids", [])
    print(f"[*] Processing DOCUMENT job for IDs: {document_ids}")
    
    with Session(engine) as session:
        db_docs = session.exec(
            select(DocumentRecord).where(DocumentRecord.id.in_(document_ids))
        ).all()
        
        chunk_records_batch = []
        
        for document in db_docs:
            print(f"Processing doc: {document.filename}")
            
            # Load
            list_of_documents = load_document_with_metadata(document)
            
            # Split
            splitted_chunks = split_document(document, list_of_documents)
            
            # Prepare records
            for chunk in splitted_chunks:
                enriched_metadata = {
                    **(chunk.metadata or {}),   # existing metadata (safe even if None)
                    "folder_id": document.folder_id,
                    "filename": document.filename
                }
                chunk_records_batch.append(
                    ChunkRecord(
                        datastore_id=document.datastore_id,
                        document_id=document.id,
                        chunk_index=str(uuid.uuid4()),
                        text=chunk.page_content,
                        metadatas=enriched_metadata
                    )
                )

        
        # Bulk Insert
        if chunk_records_batch:
            session.add_all(chunk_records_batch)
            session.commit()
            print(f"[*] Document processing complete. Inserted {len(chunk_records_batch)} chunks.")

async def process_delete_collection_job(job_data: dict):
    datastore_id = job_data.get("datastore_id")
    vector_store_provider = job_data.get("vector_store_provider")
    
    print(f"[*] Processing DELETE COLLECTION job for Datastore {datastore_id}")
    
    try:
        if vector_store_provider:
            vectorDB = create_vector_store(provider=vector_store_provider)
            vectorDB.delete_collection(name=str(datastore_id))
            # Also try delete image collection if exists
            try:
                 vectorDB.delete_collection(name=f"datastore_{datastore_id}_image")
            except:
                pass
            print(f"[*] Collection {datastore_id} deleted from {vector_store_provider}")
    except Exception as e:
        print(f"[!] Error deleting collection: {e}")

async def process_delete_vectors_job(job_data: dict):
    datastore_id = job_data.get("datastore_id")
    vector_store_provider = job_data.get("vector_store_provider")
    chunk_indexes = job_data.get("chunk_indexes")
    
    print(f"[*] Processing DELETE VECTORS job for Datastore {datastore_id}, {len(chunk_indexes)} chunks")
    
    try:
        if vector_store_provider and chunk_indexes:
            vectorDB = create_vector_store(provider=vector_store_provider)
            vectorDB.delete(collection=f"datastore_{datastore_id}", ids=chunk_indexes)
            print(f"[*] Deleted vectors from {vector_store_provider}")
    except Exception as e:
        print(f"[!] Error deleting vectors: {e}")

async def message_loop():
    inbox_key = "ingestion:inbox"
    print(f"[*] Ingestion Worker listening on {inbox_key}")
    
    while True:
        try:
            result = r.blpop(inbox_key, timeout=1)
            
            if result:
                _, message_json = result
                job_data = json.loads(message_json)
                job_type = job_data.get("job_type")
                
                if job_type == "upsert":
                    await process_upsert_job(job_data)
                elif job_type == "process_document":
                    await process_document_job(job_data)
                elif job_type == "delete_collection":
                    await process_delete_collection_job(job_data)
                elif job_type == "delete_vectors":
                    await process_delete_vectors_job(job_data)
                else:
                    print(f"[!] Unknown job type: {job_type}")
                    
            else:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"[!] Worker Loop Error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(message_loop())
