from sentence_transformers import SentenceTransformer
#from langchain.vectorstores import FAISS, Chroma
#from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

import json
from pathlib import Path

from pathlib import Path
import json
from fastapi import HTTPException


def load_chunks(chunks_file_path: str):
   
    chunks_file = chunks_file_path
    if not chunks_file.exists():
        raise FileNotFoundError("Chunks file not found.")
    with open(chunks_file, "r", encoding="utf-8") as f:
        data = json.load(f)
 
    return [chunk["content"] for chunk in data]

def embed_and_store(chunks_file_path: str,file_id:int, model_name: str, vector_db: str):
    print("1")
    chunks = load_chunks(chunks_file_path)

    print("2")
    # Step 1: Load embedding model
    embedding = HuggingFaceEmbeddings(model_name=model_name)

    print("3")
    # Step 2: Prepare documents
    from langchain.schema import Document
    docs = [Document(page_content=chunk) for chunk in chunks]

    print("4")
    # Step 3: Store into vector DB
    if vector_db == "faiss":
        db = FAISS.from_documents(docs, embedding)
        db.save_local(f"vectorstores/faiss_file_{file_id}")
        return "faiss"
    elif vector_db == "chroma":
        db = Chroma.from_documents(docs, embedding, persist_directory=f"vectorstores/chroma_file_{file_id}")
        db.persist()
        return "chroma"
    else:
        raise ValueError(f"Unsupported vector DB: {vector_db}")

# utils/vector_ops.py or any suitable utils file

from pathlib import Path
import shutil

def delete_vector_store(file_id: int, vector_db: str) -> None:
    """
    Deletes the vector store directory for the given file ID and vector DB type.
    
    Args:
        file_id (int): ID of the file for which vector store should be deleted.
        vector_db (str): Type of the vector DB ("faiss" or "chroma").
    
    Raises:
        ValueError: If the vector DB type is unsupported.
        FileNotFoundError: If the vector store directory doesn't exist.
        Exception: If deletion fails.
    """
    project_root = Path(__file__).resolve().parent.parent
    if vector_db == "faiss":
        vector_path = project_root / "vectorstores" / f"faiss_file_{file_id}"
    elif vector_db == "chroma":
        vector_path = project_root / "vectorstores" / f"chroma_file_{file_id}"
    else:
        raise ValueError("Unsupported vector DB type")

    if not vector_path.exists() or not vector_path.is_dir():
        raise FileNotFoundError("Vector store directory does not exist")

    try:
        shutil.rmtree(vector_path)
    except Exception as e:
        raise Exception(f"Error while deleting vector store: {str(e)}")


def check_embeddings_status(file_id: int, vector_db: str, model_name: str):
    embedding = HuggingFaceEmbeddings(model_name=model_name)

    if vector_db == "faiss":
        db = FAISS.load_local(f"vectorstores/faiss_file_{file_id}", embedding,allow_dangerous_deserialization=True)
        return {"vector_db": "faiss", "vector_count": len(db.index_to_docstore_id)}

    elif vector_db == "chroma":
        db = Chroma(persist_directory=f"vectorstores/chroma_file_{file_id}", embedding_function=embedding)
        return {"vector_db": "chroma", "vector_count": db._collection.count()}

    else:
        raise HTTPException(status_code=400, detail="Unsupported vector DB")

