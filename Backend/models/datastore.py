# rag_app/backend/models/datastore.py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class DataStore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = ""
    #storage_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    chatbotId: Optional[str]= ""

