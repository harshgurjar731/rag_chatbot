# rag_app/backend/db/database.py
from sqlmodel import SQLModel, create_engine, Session, text
from models.datastore import DataStore
from models.FileRecord import FileRecord

DATABASE_URL = "sqlite:////app/db/rag.db"
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

def list_tables():
    """
    Lists all tables currently present in the SQLite database.
    """
    with Session(engine) as session:
        result = session.exec(text("SELECT name FROM sqlite_master WHERE type='table';"))
        print("Tables:", result.all())

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