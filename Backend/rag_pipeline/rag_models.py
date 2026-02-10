from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlmodel import Session
from database import get_session 
from typing import List, Optional, Any, Literal

class CreateAssitantRequest(BaseModel):
    name: str
    description: str
    datastore_id: int
    department: str
    # intents removed

class KnowledgeAssistantResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: Any
    datastore_id: int
    department: str
    # intents removed


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatInterfaceDetails(BaseModel):
    messages: List[Message]
    selected_documents: List[str]
    search_image: str

class Prompt(BaseModel):
    use_knowledge_base: bool = True
    llm_temperature: float

class FeedbackRequest(BaseModel):
    trace_id: str
    span_id: Optional[str] = ""
    feedback: str
