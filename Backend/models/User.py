from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class DepartmentEnum(str, Enum):
    HR = "HR"
    IT = "IT"
    Finance = "Finance"
    Legal = "Legal"
    Admin = "Admin"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    username: str = Field(index=True, unique=True)
    password_hash: str

    department: DepartmentEnum

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
