# rag_app/backend/db/database.py
"""
Database Management Module

This module handles database connection, session management, and table operations
for the worker pool service.
"""

from sqlmodel import SQLModel, create_engine, Session, text
from models.datastore import DataStore
from models.FileRecord import FileRecord

DATABASE_URL = "sqlite:////app/db/rag.db"
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

def list_tables():
    """
    List all tables in the SQLite database.
    """
    with Session(engine) as session:
        result = session.exec(text("SELECT name FROM sqlite_master WHERE type='table';"))
        print("Tables:", result.all())

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