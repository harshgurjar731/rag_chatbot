"""
Pydantic models for the ingestion pipeline.

This module defines the data schemas used for API requests and responses within
the ingestion pipeline services.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlmodel import Session
from database import get_session 
from typing import List, Optional, Any

class DataStoreCreate(BaseModel):
    """Schema for creating a new datastore."""
    name: str
    description: str = ""

class GetDocumentDetailsRequest(BaseModel):
    """Schema for requesting document details."""
    datastoreId: int
    id: int

class DocumentRecord(BaseModel):
    """Schema representing a document record."""
    filename: str
    loaderType: str
    textSplitMethod: str
    chunkSize: int
    chunkOverlap: int
    filePath: str|None = None

class UpsertRequestData(BaseModel):
    """Schema for upserting documents into vector store."""
    embedding_provider: str
    embedding_model: str
    similarity_metric: str
    vector_store_provider: str
    normalize_embedding: bool = False

class TestRetrievalRequestData(BaseModel):
    """Schema for testing retrieval from vector store."""
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
    """Response schema for document processing."""
    success: bool
    chunks: List[str]

class ChunkTextResponse(BaseModel):
    """Response schema for fetching chunk texts."""
    chunks: List[str]

class DataStoreResponse(BaseModel):
    """Response schema for datastore details."""
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

class DocumentRecordResponse(BaseModel):
    """Response schema for document record details."""
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
