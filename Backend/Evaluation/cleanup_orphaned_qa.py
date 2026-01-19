from sqlmodel import Session, select, delete
from database import engine
from models.FileRecord import QuestionAnswer, DocumentRecord

def cleanup_orphaned_qa():
    with Session(engine) as session:
        # Find QAs with document_id that doesn't exist in DocumentRecord
        statement = select(QuestionAnswer).where(QuestionAnswer.document_id != None)
        qas = session.exec(statement).all()
        
        orphaned_count = 0
        for qa in qas:
            doc = session.get(DocumentRecord, qa.document_id)
            if not doc:
                print(f"Deleting orphaned QA {qa.question_id} linked to missing document {qa.document_id}")
                session.delete(qa)
                orphaned_count += 1
        
        session.commit()
        print(f"Cleanup complete. Deleted {orphaned_count} orphaned QA pairs.")

if __name__ == "__main__":
    cleanup_orphaned_qa()
