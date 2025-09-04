

from fastapi import HTTPException
from langchain.vectorstores import FAISS, Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from Services.multi_query_retriever import get_multiquery_retriever
from Services.multi_query_retriever_without_sources import get_multiquery_retriever_without_sources
from Services.general_retriever import get_llm_answer
from Services.step_back_retriever_with_source import get_stepback_retriever_with_sources
from Services.step_back_retriever_without_source import get_stepback_retriever_without_sources
from Services.rag_fusion_retriever_with_source import get_ragfusion_retriever_with_sources
from Services.rag_fusion_retriever_without_sources import get_ragfusion_retriever_without_sources
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
    
def retrieve_documents(query: str, query_optimizer: str, embedding_model_name: str,llm_model_name: str, vector_db: str, file_id:list,temperature:float,token_size:float,sources: bool,guardrailOption: str):
    embedding = HuggingFaceEmbeddings(model_name=embedding_model_name)
    if file_id == [0]:
        result=get_llm_answer(query, llm_model_name, temperature,token_size,sources,guardrailOption)
    else:
        db = None
        for f_id in file_id:
            new_db = load_embeddings(f_id, vector_db, embedding_model_name)
            if db is None:
                db = new_db
            else:
                db.merge_from(new_db)
        
        if query_optimizer == "Multi Query":
            if sources:
                result=get_multiquery_retriever(query,db, llm_model_name,temperature,token_size,guardrailOption)
            else:
                result=get_multiquery_retriever_without_sources(query,db, llm_model_name,temperature,token_size,guardrailOption)

        elif query_optimizer == "Step Back":
            if sources:
                result = get_stepback_retriever_with_sources(
                    query, db, llm_model_name, temperature, token_size, guardrailOption
                )
            else:
                result = get_stepback_retriever_without_sources(
                    query, db, llm_model_name, temperature, token_size, guardrailOption
                )
        elif query_optimizer == "Rag Fusion":
            if sources:
                result = get_ragfusion_retriever_with_sources(query, db, llm_model_name, temperature, token_size, guardrailOption)
            else:
                result = get_ragfusion_retriever_without_sources(query, db, llm_model_name, temperature, token_size, guardrailOption)
        else:
            retriever = db.as_retriever()
    return result