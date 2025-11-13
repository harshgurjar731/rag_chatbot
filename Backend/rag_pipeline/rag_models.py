from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlmodel import Session
from database import get_session 
from typing import List, Optional, Any, Literal

class CreateAssitantRequest(BaseModel):
    name: str
    description: str
    datastore_id: int

class KnowledgeAssistantResponse(BaseModel):
    id: int
    name: str
    description: str
    created_at: Any
    datastore_id: int


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatInterfaceDetails(BaseModel):
    messages: List[Message]
    selectedDocuments: List[str]

class Prompt(BaseModel):
    use_knowledge_base: bool = True
    llm_temperature: float
