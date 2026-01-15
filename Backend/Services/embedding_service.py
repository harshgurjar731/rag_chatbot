"""
Service for generating and managing text embeddings.

This module helps in loading document chunks, generating embeddings using
HuggingFace models, and storing them in vector databases (FAISS/Chroma).
"""
from sentence_transformers import SentenceTransformer
#from langchain.vectorstores import FAISS, Chroma
#from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS, Chroma
# from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
import json
from pathlib import Path
from typing import List



# def load_chunks(chunks_file_path: str):
   
#     chunks_file = chunks_file_path
#     if not chunks_file.exists():
#         raise FileNotFoundError("Chunks file not found.")
#     with open(chunks_file, "r", encoding="utf-8") as f:
#         data = json.load(f)
 
#     return [chunk["content"] for chunk in data]

# def embed_and_store(chunks_file_path: str,file_id:int, model_name: str, vector_db: str):
#     print("1")
#     chunks = load_chunks(chunks_file_path)

#     print("2")
#     # Step 1: Load embedding model
#     embedding = HuggingFaceEmbeddings(model_name=model_name)

#     print("3")
#     # Step 2: Prepare documents
#     from langchain.schema import Document
#     docs = [Document(page_content=chunk) for chunk in chunks]

#     print("4")
#     # Step 3: Store into vector DB
#     if vector_db == "faiss":
#         db = FAISS.from_documents(docs, embedding)
#         db.save_local(f"vectorstores/faiss_file_{file_id}")
#         return "faiss"
#     elif vector_db == "chroma":
#         db = Chroma.from_documents(docs, embedding, persist_directory=f"vectorstores/chroma_file_{file_id}")
#         db.persist()
#         return "chroma"
#     else:
#         raise ValueError(f"Unsupported vector DB: {vector_db}")

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
    """
    Checks the status of embeddings for a given file.

    Args:
        file_id (int): The ID of the file to check.
        vector_db (str): The type of vector database ("faiss" or "chroma").
        model_name (str): The name of the embedding model used.

    Returns:
        dict: A dictionary containing the vector DB type and the count of vectors.

    Raises:
        HTTPException: If the vector DB type is unsupported.
    """
    embedding = HuggingFaceEmbeddings(model_name=model_name)

    if vector_db == "faiss":
        db = FAISS.load_local(f"vectorstores/faiss_file_{file_id}", embedding,allow_dangerous_deserialization=True)
        return {"vector_db": "faiss", "vector_count": len(db.index_to_docstore_id)}

    elif vector_db == "chroma":
        db = Chroma(persist_directory=f"vectorstores/chroma_file_{file_id}", embedding_function=embedding)
        return {"vector_db": "chroma", "vector_count": db._collection.count()}

    else:
        raise HTTPException(status_code=400, detail="Unsupported vector DB")

