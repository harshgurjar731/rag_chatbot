# rag_app/backend/models/datastore.py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class FileRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    datastore_id: int = Field(foreign_key="datastore.id")
