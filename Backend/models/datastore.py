# rag_app/backend/models/datastore.py
from sqlmodel import SQLModel, Field, Session, select, Relationship, Column, ForeignKey
from typing import Optional
from datetime import datetime
from typing import List
from sqlmodel import Relationship

class DataStore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = ""
    #storage_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    embedding_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    vector_store_provider: Optional[str] = None
    similarity_metric: Optional[str] = None

    documents: List["DocumentRecord"] = Relationship(
        back_populates="datastore", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    
    files: List["FileRecord"] = Relationship(
        back_populates="datastore",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

def update_datastore(session: Session, store_id: int, update_data: dict):
    statement = select(DataStore).where(DataStore.id == store_id)
    result = session.exec(statement)
    store = result.one_or_none()

    if not store:
        print("Store not found")

    for key, value in update_data.items():
        if hasattr(store, key):
            setattr(store, key, value)

    session.add(store)
    session.commit()
    session.refresh(store)

    return store

class KnowledgeAssistant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    datastore_id:Optional[int]

class ChatbotSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chatbot_id: str = Field(index=True, unique=True)
    llm_model: Optional[str] = None
    llm_provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    reranker_type: Optional[str] = None
    query_optimizer: Optional[str] = None
    guardrail_type: Optional[str] = None
    embedding_model: Optional[str] = None 
    vector_db: Optional[str] = None
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RAGResponse(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Links to the question generated for evaluation
    question_id: int = Field(
        sa_column=Column(ForeignKey("questionanswer.question_id", ondelete="CASCADE"))
    )
    
    # Identify which chatbot (settings) this response belongs to
    chatbot_id: str = Field(index=True)

    # The actual content
    generated_answer: str
    
    # Store as JSON string or use JSON column type if supported
    citations: str  # Storing as JSON string for simplicity, or could use SA JSON type
    
    # Snapshot of settings used to generate this response
    # These are used to invalidate the cache if settings change
    llm_model: Optional[str] = None
    llm_provider: Optional[str] = None
    temperature: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

