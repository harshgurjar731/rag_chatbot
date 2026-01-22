from sqlmodel import Session
from sqlmodel import select
from pathlib import Path
import json
from models.FileRecord import QuestionAnswer
from models.FileRecord import FileRecord, DocumentRecord
from models.datastore import DataStore
from Evaluation.qna_curation import *
from config import CONFIG
import os

def get_file_path(datastore_id: int, datastore_name: str, filename: str, base_folder: str = "..\Data") -> Path:
    """
    Constructs a full file path dynamically based on datastore id, name, and filename.
    
    Args:
        datastore_id (int): The datastore ID
        datastore_name (str): The name of the datastore
        filename (str): Name of the file (e.g., 'hr policies.pdf')
        base_folder (str): Base folder where all datastores are stored
    
    Returns:
        Path: Full path to the file
    """
    # Replace invalid filesystem characters in datastore name if needed
    safe_name = "".join(c for c in datastore_name if c.isalnum() or c in (" ", "_")).strip()
    
    # Construct full path
    file_path = Path(base_folder) / f"{safe_name}" / filename
    return file_path

def insert_qna(session: Session, datastore_id: int, qna_json: dict, file_id: int = None, document_id: int = None):
    """
    Inserts QA pairs from JSON into the QuestionAnswer table.

    Args:
        session (Session): SQLModel database session.
        datastore_id (int): The datastore ID to link these QA pairs.
        qna_json (dict): Dictionary containing 'qa_pairs' list.
        file_id (int, optional): FileRecord ID if QA is linked to a specific file.
        document_id(int, optional): DocumentRecord ID if QA is linked to a specific document.
    
    Returns:
        int: Number of QA pairs inserted.
    """
    if "qa_pairs" not in qna_json:
        raise ValueError("Invalid JSON format: missing 'qa_pairs' key")

    inserted_count = 0
    for qa in qna_json["qa_pairs"]:
        question = qa.get("question")
        answer = qa.get("answer")
        if not question or not answer:
            continue  # skip incomplete QA

        qa_entry = QuestionAnswer(
            question=question,
            answer=answer,
            datastore_id=datastore_id,
            file_id=file_id,
            document_id=document_id
        )
        session.add(qa_entry)
        inserted_count += 1

    session.commit()
    return inserted_count
  # your insert_qna function

def insert_qna_for_datastore(session: Session, datastore_id: int):
    """
    Loop through all files in a datastore and insert QA pairs into QuestionAnswer table
    only if the curated QA JSON file does not exist.
    """
    base_input_path = Path("Backend/Evaluation/data/input")
    base_data_path = Path("data/curated")

    total_inserted = 0

    # Check datastore exists
    datastore = session.exec(
        select(DataStore).where(DataStore.id == datastore_id)
    ).first()
    if not datastore:
        print(f"[WARN] Datastore {datastore_id} not found.")
        return 0

    # Get all files for this datastore
    files = session.exec(select(DocumentRecord).where(DocumentRecord.datastore_id == datastore_id)).all()
    if not files:
        print(f"[WARN] No files found for datastore {datastore_id}")
        return 0


    # Build the dynamic path (points to Data folder inside project)
    data_folder = Path(CONFIG["project_root"]) / CONFIG["datastore_data_folder"]
    output_dir = data_folder / datastore.name
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

    for file in files:
        # Define JSON output path
        qa_file_name = f"{os.path.splitext(file.filename)[0]}_qa_pairs_cleaned.json"
        qa_file_path = output_dir / qa_file_name

        # Check if Q&A for this document already exists in DB
        existing_qa_count = session.exec(
            select(QuestionAnswer).where(QuestionAnswer.document_id == file.id)
        ).first()

        if existing_qa_count:
             print(f"[INFO] QA pairs already exist in DB for file {file.filename}, skipping.")
             # We might still want to ensure JSON file exists if needed, but primary goal is DB
             continue

        # If JSON exists but not in DB, load and insert
        if qa_file_path.exists():
            print(f"[INFO] QA file exists for {file.filename} but not in DB. Importing...")
            try:
                with open(qa_file_path, "r", encoding="utf-8") as f:
                    qna_json = json.load(f)
                inserted = insert_qna(session, datastore_id=datastore_id, qna_json=qna_json, document_id=file.id)
                total_inserted += inserted
                print(f"[INFO] Inserted {inserted} QA pairs for file {file.filename} from existing JSON.")
                continue
            except Exception as e:
                print(f"[ERROR] Failed to load existing QA file {qa_file_name}: {e}. Reprocessing...")
                # If load fails, fall through to regenerate

        # Construct input file path
        # Construct input file path
        # Always use the standardized path based on container config, ignoring legacy DB paths
        file_path = Path(CONFIG["project_root"]) / CONFIG["datastore_data_folder"] / datastore.name / file.filename
        
        print(f"[INFO] Processing file: {file_path}")

        if not file_path.exists():
            print(f"[WARN] File not found: {file_path}, skipping.")
            continue

        # Process file → generate curated QAs
        try:
            process_file(file_path=str(file_path), output_dir=str(output_dir),datastore_name=datastore.name)
        except Exception as e:
            print(f"[ERROR] Failed to process file {file.filename}: {e}")
            continue

        # Load curated QA JSON after processing
        if not qa_file_path.exists():
            print(f"[WARN] QA file not found after processing {file.filename}, skipping.")
            continue

        with open(qa_file_path, "r", encoding="utf-8") as f:
            qna_json = json.load(f)

        # Insert QA into DB
        inserted = insert_qna(session, datastore_id=datastore_id, qna_json=qna_json, document_id=file.id)
        total_inserted += inserted
        print(f"[INFO] Inserted {inserted} QA pairs for file {file.filename}")

    print(f"[INFO] Total QA pairs inserted for datastore {datastore_id}: {total_inserted}")
    return total_inserted