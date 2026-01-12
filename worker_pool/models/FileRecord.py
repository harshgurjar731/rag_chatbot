# rag_app/backend/models/datastore.py
from sqlmodel import SQLModel, Field, Column, JSON
from typing import Optional, Dict
from datetime import datetime
from typing import List, Any
from sqlmodel import Relationship, ForeignKey, select, Session
from models.datastore import DataStore

class DocumentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    loaderType: str
    textSplitMethod: str
    chunkSize: int
    chunkOverlap: int
    filePath: str|None = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    # datastore_id: Optional[int] = Field(default=None, foreign_key="datastore.id")
    insert_vector_status: bool = False

    datastore_id: Optional[int] = Field(
        default=None,
        # foreign_key="datastore.id", 
        # sa_column_kwargs={"ondelete": "CASCADE"}
        sa_column=Column(ForeignKey("datastore.id", ondelete="CASCADE"))
    )
    datastore: Optional[DataStore] = Relationship(back_populates="documents")

    chunks: List["ChunkRecord"] = Relationship(
        back_populates="document", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    model_config = {
        "from_attributes": True   # <- THIS IS REQUIRED
    }

def update_document_record(session: Session, doc_id: int, update_data: dict):
    statement = select(DocumentRecord).where(DocumentRecord.id == doc_id)
    result = session.exec(statement)
    doc = result.one_or_none()
    print("updating values", doc_id, update_data)
    if not doc:
        print("Store not found")

    for key, value in update_data.items():
        if hasattr(doc, key):
            print("updating values")
            setattr(doc, key, value)

    session.add(doc)
    session.commit()
    session.refresh(doc)

    return doc

class ChunkRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    #datastore_id: int = Field(foreign_key="datastore.id")
    #document_id: int = Field(foreign_key="documentrecord.id")
    chunk_index: str
    text: str
    page_number: Optional[int] = None
    
    metadatas: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    datastore_id: int = Field(
        sa_column=Column(ForeignKey("datastore.id", ondelete="CASCADE"))
        # foreign_key="datastore.id",
        # sa_column_kwargs={"ondelete": "CASCADE"}
    )
    document_id: int = Field(
        sa_column=Column(ForeignKey("documentrecord.id", ondelete="CASCADE"))
        # foreign_key="documentrecord.id", 
        # sa_column_kwargs={"ondelete": "CASCADE"}
    )

    document: Optional[DocumentRecord] = Relationship(back_populates="chunks")

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