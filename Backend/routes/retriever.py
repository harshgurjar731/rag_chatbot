from fastapi import APIRouter, Query
from Services.retriever_service import retrieve_documents
from typing import List
from config import CONFIG
from opentelemetry import trace
import uuid  # ✅ CHANGE: Added the import for generating unique IDs

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
    results_object = retrieve_documents(
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
    
    final_answer = ""
    if isinstance(results_object, dict):
        final_answer = results_object.get("result") or results_object.get("answer", "No answer found in results.")
    elif isinstance(results_object, str):
        final_answer = results_object
    else:
        final_answer = "Could not process the response from the service."

    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()

    trace_id = ""
    if span_context.is_valid:
        trace_id = format(span_context.trace_id, '032x')
        print(f"✅ Successfully captured Phoenix trace_id: {trace_id}")
    else:
        # ✅ CHANGE: Added a fallback to generate a UUID if no trace is found.
        # This ensures the feedback feature will always have a unique ID to work with.
        trace_id = str(uuid.uuid4())
        print(f"⚠️ WARNING: Could not find a valid span context. Using generated UUID as trace_id: {trace_id}")

    return {"answer": final_answer, "traceId": trace_id}