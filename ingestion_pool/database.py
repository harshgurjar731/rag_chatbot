# ingestion_pool/database.py
from sqlmodel import SQLModel, create_engine, Session, text
from config import DATABASE_URL

# DATABASE_URL is now imported from config.py which handles env vars for Postgres
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
    Lists all tables currently present in the database.
    """
    with Session(engine) as session:
        # Postgres query to list tables
        result = session.exec(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
        print("Tables:", result.all())
