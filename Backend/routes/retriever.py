from fastapi import APIRouter, Query
from Services.retriever_service import retrieve_documents

router = APIRouter()

@router.get("/query")
def retrieve(query: str = Query(...),
             query_optimizer: str = Query("Multi Query", description="Query optimizer to use"),
             embedding_model_name: str = Query("all-MiniLM-L6-v2", description="Embedding model"),
             llm_model_name: str = Query("llama3-8b-8192", description="LLM model name"),
             vector_db: str = Query(...),
             file_id: int = Query(...),
             temperature:float=Query(0.0),
             guardrailOption:str=Query("none"),):
    results = retrieve_documents(query,query_optimizer,embedding_model_name,llm_model_name, vector_db, file_id,temperature)
    return {"results": results["answer"]}
# +"\n\n"+str(results["sources"])