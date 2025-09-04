from fastapi import APIRouter, Query
from Services.retriever_service import retrieve_documents
from typing import List, Optional

router = APIRouter()

@router.get("/query")
def retrieve(query: str = Query(...),
             query_optimizer: str = Query("Multi Query", description="Query optimizer to use"),
             embedding_model_name: str = Query("all-MiniLM-L6-v2", description="Embedding model"),
             llm_model_name: str = Query("llama3-8b-8192", description="LLM model name"),
             vector_db: str = Query(...),
             file_id: List[int] = Query(...),
             temperature:float=Query(0.0),
             guardrailOption:str=Query("none"),
             token_size:int=Query(256, ge=256, le=2048, description="Token size (between 256 and 2048)"),
             sources: bool= Query(False, description="Include sources in the response")):
    results = retrieve_documents(query,query_optimizer,embedding_model_name,llm_model_name, vector_db, file_id,temperature,token_size,sources,guardrailOption)
    return {"results": results["answer"]}
# +"\n\n"+str(results["sources"])