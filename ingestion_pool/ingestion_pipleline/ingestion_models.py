from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlmodel import Session
from database import get_session 
from typing import List, Optional, Any

class DataStoreCreate(BaseModel):
    name: str
    description: str = ""

class FolderCreate(BaseModel):
    name: str
    parent_id: int

class GetDocumentDetailsRequest(BaseModel):
    datastoreId: int
    id: int

class DocumentRecord(BaseModel):
    filename: str
    loaderType: str
    textSplitMethod: str
    chunkSize: int
    chunkOverlap: int
    filePath: str|None = None

class UpsertRequestData(BaseModel):
    embedding_provider: str
    embedding_model: str
    similarity_metric: str
    vector_store_provider: str
    normalize_embedding: bool = False

class TestRetrievalRequestData(BaseModel):
    query_str: str
    image_base64: str
    top_k: int
    rerank_enabled: bool
    embedding_provider: str
    embedding_model: str
    similarity_metric: str
    vector_store_provider: str
    is_vision_search: bool

class ProcessDocumentResponse(BaseModel):
    success: bool
    chunks: List[str]

class ChunkTextResponse(BaseModel):
    chunks: List[str]

class DataStoreResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = ""
    created_at: Any
    chatbotId: Optional[str]= ""
    embedding_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    vector_store_provider: Optional[str] = None
    similarity_metric: Optional[str] = None
    document_count: Optional[int]
    root_folder_id: Optional[int]

class DocumentRecordResponse(BaseModel):
    id: int
    filename: str
    loaderType: str
    textSplitMethod: str
    chunkSize: int
    chunkOverlap: int
    filePath: str|None = None
    uploaded_at: Any
    datastore_id: int
    insert_vector_status: bool = False
    chunk_count: int
