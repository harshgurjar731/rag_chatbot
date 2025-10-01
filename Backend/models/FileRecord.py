# rag_app/backend/models/datastore.py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from typing import List
from sqlmodel import Relationship
from models.datastore import DataStore

class FileRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    datastore_id: int = Field(foreign_key="datastore.id")

class QuestionAnswer(SQLModel, table=True):
    # Use question_id as primary key with autoincrement
    question_id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    answer: str

    datastore_id: int = Field(foreign_key="datastore.id")
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")