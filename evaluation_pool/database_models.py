from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON
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


class EvaluationResult(SQLModel, table=True):
    """
    Stores evaluation results from Phoenix or RAGAS frameworks.
    Enables caching and historical tracking of evaluations.
    """
    __tablename__ = "evaluation_result"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    evaluation_id: str = Field(index=True, unique=True)
    
    # Evaluation configuration (for cache matching)
    datastore_id: int = Field(index=True)
    chatbot_id: Optional[str] = Field(default=None, index=True)
    settings_id: Optional[int] = Field(default=None)
    framework: str = Field(index=True)  # "phoenix" or "ragas"
    metrics: str = Field(sa_column=Column(JSON))  # JSON array of metric names
    
    # Results data
    results: str = Field(sa_column=Column(JSON))
    meta_info: Optional[str] = Field(default=None, sa_column=Column(JSON))
    
    # Status and validity
    is_valid: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Performance tracking
    execution_time_seconds: Optional[float] = None
    qa_count: Optional[int] = None

