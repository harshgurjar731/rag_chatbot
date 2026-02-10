from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class DocumentRecord(SQLModel, table=True):
    __tablename__ = "documentrecord"
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    filePath: str | None = None
    datastore_id: Optional[int] = Field(default=None)

class DataStore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    root_folder_id: Optional[int] = Field(default=None)
    vector_store_provider: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QuestionAnswerV2(SQLModel, table=True):
    __tablename__ = "question_answer_v2"
    question_id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    answer: str
    datastore_id: int
    document_id: int
    file_name: str



class RAGResponse(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int
    chatbot_id: str
    user_query: str
    generated_answer: str
    citations: Optional[str] = None # Storing as JSON string or text
    context_text: Optional[str] = None # Added for RAGAS evaluation (raw text)
    settings_id: Optional[int] = Field(default=None) # Link to specific settings version
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatbotSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chatbot_id: str = Field(index=True) # Removed unique=True
    llm_provider: Optional[str] = "azure-openai"
    llm_model: Optional[str] = "gpt-4o-mini"
    temperature: Optional[float] = 0.0
    optimizer: Optional[str] = "None"
    token_size: Optional[int] = 512
    guardrail_option: Optional[str] = "off"
    reranker_option: Optional[str] = "none"
    show_sources: Optional[bool] = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
