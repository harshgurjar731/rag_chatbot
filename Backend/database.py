# rag_app/backend/db/database.py
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
    Dependency that provides a SQLModel database session.

    Yields:
        Session: A database session object.
    """
    with Session(engine) as session:
        yield session

def init_db():
    """
    Initializes the database by creating all tables defined in SQLModel metadata.
    """
    SQLModel.metadata.create_all(engine)

from sqlalchemy import inspect

def list_tables():
    """
    Lists all tables currently present in the database.
    """
    inspector = inspect(engine)
    print("Tables:", inspector.get_table_names())

def list_tables_content():
    """
    Lists the content of the 'datastore' table for debugging purposes.
    """
    with Session(engine) as session:
        result = session.exec(text("SELECT * FROM datastore;"))
        print("Datastore Content:", result.all())

def list_file_content():
    """
    Lists the content of the 'FileRecord' table for debugging purposes.
    """
    with Session(engine) as session:
        result = session.exec(text("SELECT * FROM FileRecord;"))
        print("FileRecord Content:", result.all())