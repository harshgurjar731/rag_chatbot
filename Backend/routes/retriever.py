# rag_app/backend/routes/query.py
from fastapi import APIRouter, Query
from Services.retriever_service import retrieve_documents
from typing import List
from config import CONFIG  # 🔹 centralized env-driven config



router = APIRouter()


@router.get("/query")
def retrieve(
    query: str = Query(..., description="User query"),
    query_optimizer: str = Query(
        CONFIG["default_query_optimizer"], description="Query optimizer to use"
    ),
    embedding_model_name: str = Query(
        CONFIG["default_embedding_model"], description="Embedding model"
    ),
    llm_model_name: str = Query(
        CONFIG["default_llm_model"], description="LLM model name"
    ),
    vector_db: str = Query(CONFIG["default_vector_db"], description="Vector DB name"),
    file_id: List[int] = Query(..., description="File IDs to search within"),
    temperature: float = Query(
        CONFIG["default_temperature"], description="LLM temperature"
    ),
    guardrailOption: str = Query(
        CONFIG["default_guardrail_option"], description="Guardrail option"
    ),
    token_size: int = Query(
        CONFIG["default_token_size"],
        ge=256,
        le=2048,
        description="Token size (between 256 and 2048)",
    ),
    sources: bool = Query(False, description="Include sources in the response"),
    rerankerOption: str = Query(
        CONFIG["default_reranker_option"], description="Reranker option to use"
    ),
):
    # 🔹 Call retriever service
    results = retrieve_documents(
        query,
        query_optimizer,
        embedding_model_name,
        llm_model_name,
        vector_db,
        file_id,
        temperature,
        token_size,
        sources,
        guardrailOption,
        rerankerOption,
    )

    return {"results": results["answer"]}
