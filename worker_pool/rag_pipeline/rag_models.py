"""
RAG Pipeline Models.

Defines Pydantic models used by the RAG router and services for request/response validation.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlmodel import Session
from database import get_session 
from typing import List, Optional, Any, Literal

class CreateAssitantRequest(BaseModel):
    """Schema for creating a new knowledge assistant."""
    name: str
    description: str
    datastore_id: int

class KnowledgeAssistantResponse(BaseModel):
    """Response schema for knowledge assistant details."""
    id: int
    name: str
    description: str
    created_at: Any
    datastore_id: int


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatInterfaceDetails(BaseModel):
    """Schema for chat interface details including history and files."""
    messages: List[Message]
    selected_documents: List[str]
    search_image: str

class Prompt(BaseModel):
    use_knowledge_base: bool = True
    llm_temperature: float

class FeedbackRequest(BaseModel):
    """Schema for submitting user feedback."""
    trace_id: str
    span_id: Optional[str] = ""
    feedback: str
