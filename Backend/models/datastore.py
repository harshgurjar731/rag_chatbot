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
    intents: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))

