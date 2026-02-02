# rag_app/backend/models/datastore.py
from sqlmodel import SQLModel, Field, Session, select
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
        # cascade_delete=True
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    
    has_secondary_sources: bool = Field(default=False)
    secondary_sources: List["SecondarySource"] = Relationship(
        back_populates="datastore",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class SecondarySource(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    datastore_id: Optional[int] = Field(default=None, foreign_key="datastore.id")
    intent: str
    description: str
    file_path: Optional[str] = None
    
    datastore: Optional[DataStore] = Relationship(back_populates="secondary_sources")

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


from uuid import uuid4
from sqlmodel import Column, JSON

class KnowledgeAssistant(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str
    description: Optional[str] = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    datastore_id:Optional[int]
    # intents removed as they are now part of datastore secondary sources

