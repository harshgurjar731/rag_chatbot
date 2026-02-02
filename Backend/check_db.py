from sqlmodel import Session, select
from database import get_session
from models.FileRecord import DocumentRecord

session = next(get_session())
docs = session.exec(select(DocumentRecord).where(DocumentRecord.datastore_id == 1)).all()
print(f"--- Documents in Datastore 1 ({len(docs)}) ---")
for doc in docs:
    print(f"ID: {doc.id}, Filename: '{doc.filename}'")
