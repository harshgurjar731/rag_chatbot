from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores import FAISS, Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import json
from pathlib import Path
from typing import List
import shutil
from fastapi import HTTPException
from langchain_core.documents import Document

def load_chunks(chunks_file_path: str) -> List[Document]:
    """
    Loads document chunks from a JSON file, including both content and metadata.

    Args:
        chunks_file_path (str): The path to the JSON file containing the chunks.

    Returns:
        List[Document]: A list of LangChain Document objects, each with page content and metadata.
    
    Raises:
        FileNotFoundError: If the specified chunks file does not exist.
    """
    chunks_file = Path(chunks_file_path)
    if not chunks_file.exists():
        raise FileNotFoundError(f"Chunks file not found at: {chunks_file_path}")

    with open(chunks_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return [
        Document(page_content=d["content"], metadata=d["metadata"])
        for d in data
    ]

def embed_and_store(chunks_file_path: str, file_id: int, model_name: str, vector_db: str):
    """
    Loads documents with metadata, embeds them, and stores them in a vector database.

    The metadata is preserved during the embedding and storage process.
    """
    print("Step 1: Loading chunks from file...")
    # ✅ Correctly load Document objects, which already contain content and metadata
    chunks = load_chunks(chunks_file_path)

    print(f"Step 2: Loaded {len(chunks)} chunks. Example metadata: {chunks[0].metadata}")
    
    # Step 3: Load embedding model
    embedding = HuggingFaceEmbeddings(model_name=model_name)
    
    # Step 4: Store into vector DB
    # ✅ Pass the 'chunks' list directly. The methods automatically handle content and metadata.
    print("Step 5: Storing documents in vector DB...")
    if vector_db == "faiss":
        db = FAISS.from_documents(chunks, embedding)
        db.save_local(f"vectorstores/faiss_file_{file_id}")
        print("FAISS vector store created successfully.")
        return "faiss"
    elif vector_db == "chroma":
        db = Chroma.from_documents(chunks, embedding, persist_directory=f"vectorstores/chroma_file_{file_id}")
        db.persist()
        print("Chroma vector store created successfully.")
        return "chroma"
    else:
        raise ValueError(f"Unsupported vector DB: {vector_db}")


# utils/vector_ops.py or any suitable utils file

def delete_vector_store(file_id: int, vector_db: str) -> None:
    """
    Deletes the vector store directory for the given file ID and vector DB type.
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
    """
    Checks the status of the vector store and returns the number of vectors.
    """
    embedding = HuggingFaceEmbeddings(model_name=model_name)

    if vector_db == "faiss":
        db = FAISS.load_local(f"vectorstores/faiss_file_{file_id}", embedding, allow_dangerous_deserialization=True)
        return {"vector_db": "faiss", "vector_count": len(db.index_to_docstore_id)}

    elif vector_db == "chroma":
        db = Chroma(persist_directory=f"vectorstores/chroma_file_{file_id}", embedding_function=embedding)
        return {"vector_db": "chroma", "vector_count": db._collection.count()}

    else:
        raise HTTPException(status_code=400, detail="Unsupported vector DB")