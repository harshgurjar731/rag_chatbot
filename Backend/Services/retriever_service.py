

from fastapi import HTTPException
from langchain.vectorstores import FAISS, Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from Services.multi_query_retriever import get_multiquery_retriever


def load_embeddings(file_id: int, vector_db: str, model_name: str):
    embedding = HuggingFaceEmbeddings(model_name=model_name)

    if vector_db == "faiss":
        db = FAISS.load_local(f"vectorstores/faiss_file_{file_id}", embedding,allow_dangerous_deserialization=True)
        return db

    elif vector_db == "chroma":
        db = Chroma(persist_directory=f"vectorstores/chroma_file_{file_id}", embedding_function=embedding)
        return db

    else:
        raise HTTPException(status_code=400, detail="Unsupported vector DB")
    
def retrieve_documents(query: str, query_optimizer: str, embedding_model_name: str,llm_model_name: str, vector_db: str, file_id: int,temperature:float):
    embedding = HuggingFaceEmbeddings(model_name=embedding_model_name)

    db = load_embeddings(file_id, vector_db, embedding_model_name)
    if query_optimizer == "Multi Query":
        result=get_multiquery_retriever(query,db, llm_model_name,temperature)
    else:
        retriever = db.as_retriever()

    return result