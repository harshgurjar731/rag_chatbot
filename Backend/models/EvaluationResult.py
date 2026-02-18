"""
Evaluation Result Model
Stores evaluation results for caching and historical tracking.
"""
from sqlmodel import SQLModel, Field, Column, JSON
from typing import Optional, List, Dict, Any
from datetime import datetime


class EvaluationResult(SQLModel, table=True):
    """
    Stores evaluation results from Phoenix or RAGAS frameworks.
    Enables caching and historical tracking of evaluations.
    """
    __tablename__ = "evaluation_result"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    evaluation_id: str = Field(index=True, unique=True)  # Unique identifier for this evaluation run
    
    # Evaluation configuration (for cache matching)
    datastore_id: int = Field(foreign_key="datastore.id", index=True)
    chatbot_id: Optional[str] = Field(default=None, index=True)
    settings_id: Optional[int] = Field(default=None)  # ChatbotSettings version used
    framework: str = Field(index=True)  # "phoenix" or "ragas"
    metrics: str = Field(sa_column=Column(JSON))  # JSON array of metric names
    
    # Results data
    results: str = Field(sa_column=Column(JSON))  # Full evaluation results as JSON
    eval_metadata: Optional[str] = Field(default=None, sa_column=Column("metadata", JSON))  # Additional info (Q&A count, execution time, etc.)
    
    # Status and validity
    is_valid: bool = Field(default=True)  # Can be set to False to invalidate cache
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Performance tracking
    execution_time_seconds: Optional[float] = None
    qa_count: Optional[int] = None  # Number of Q&A pairs evaluated
