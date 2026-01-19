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
    
    # --- Migration: Add document_id column to questionanswer if missing ---
    with Session(engine) as session:
        try:
            # Check if column exists by trying to select it
            session.exec(text("SELECT document_id FROM questionanswer LIMIT 1"))
        except Exception:
            print("[INFO] Migration: Adding missing 'document_id' column to 'questionanswer' table.")
            try:
                session.exec(text("ALTER TABLE questionanswer ADD COLUMN document_id INTEGER REFERENCES documentrecord(id)"))
                session.commit()
                print("[INFO] Migration successful.")
            except Exception as e:
                print(f"[ERROR] Migration failed: {e}")
                session.rollback()

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