# rag_app/backend/db/database.py
from sqlmodel import SQLModel, create_engine, Session, text
from models.datastore import DataStore
from models.FileRecord import FileRecord

DATABASE_URL = "sqlite:///./rag.db"
engine = create_engine(DATABASE_URL, echo=True)



def get_session():
    with Session(engine) as session:
        yield session

def init_db():
    SQLModel.metadata.create_all(engine)

def list_tables():
    with Session(engine) as session:
        result = session.exec(text("SELECT name FROM sqlite_master WHERE type='table';"))
        print("Tables:", result.all())

def list_tables_content():
    with Session(engine) as session:
        result = session.exec(text("SELECT * FROM datastore;"))
        print("Tables:", result.all())

def list_file_content():
    with Session(engine) as session:
        result = session.exec(text("SELECT * FROM FileRecord;"))
        print("Tables:", result.all())