# models/citation_model.py
from pydantic import BaseModel, Field
from typing import List

class CitedAnswer(BaseModel):
    answer: str = Field(...)
    citations: List[dict] = Field(...)