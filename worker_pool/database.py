# rag_app/backend/db/database.py
"""
Database Management Module

This module handles database connection, session management, and table operations
for the worker pool service.
"""

from sqlmodel import SQLModel, create_engine, Session, text
from models.datastore import DataStore
from models.FileRecord import FileRecord

import os

user = os.getenv("DB_USER", "user")
password = os.getenv("DB_PASSWORD", "password")
host = os.getenv("DB_HOST", "db")
dbname = os.getenv("DB_NAME", "chatbot_db")
DATABASE_URL = f"postgresql://{user}:{password}@{host}/{dbname}"

engine = create_engine(DATABASE_URL, echo=True)



def get_session():
    """
    Yield a database session.
    
    Yields:
        Session: A SQLModel session.
    """
    with Session(engine) as session:
        yield session

def init_db():
    """
    Initialize the database by creating all tables defined in SQLModel metadata.
    """
    SQLModel.metadata.create_all(engine)

from sqlalchemy import inspect

def list_tables():
    """
    List all tables in the database.
    """
    inspector = inspect(engine)
    print("Tables:", inspector.get_table_names())

def list_tables_content():
    """
    List contents of the 'datastore' table.
    """
    with Session(engine) as session:
        result = session.exec(text("SELECT * FROM datastore;"))
        print("Tables:", result.all())

def list_file_content():
    """
    List contents of the 'FileRecord' table.
    """
    with Session(engine) as session:
        result = session.exec(text("SELECT * FROM FileRecord;"))
        print("Tables:", result.all())