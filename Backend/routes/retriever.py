# rag_app/backend/routes/query.py
from fastapi import APIRouter, Query, Depends
from Services.retriever_service import retrieve_documents
from typing import List
from config import CONFIG  # 🔹 centralized env-driven config
import uuid
from fastapi import Path
from phoenix import trace
from phoenix.otel import register
from rag_pipeline.Config.rag_config import RAG_CONFIG
from models.datastore import DataStore
from sqlmodel import Session, select
from database import get_session




router = APIRouter()

@router.get("/query/{chatbot_id}", response_model=dict)
def retrieve(
    chatbot_id: str = Path(..., description="The ID of the chatbot being queried"),
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
    # # 🔹 Call retriever service
    # results = retrieve_documents(
    #     query,
    #     query_optimizer,
    #     embedding_model_name,
    #     llm_model_name,
    #     vector_db,
    #     file_id,
    #     temperature,
    #     token_size,
    #     sources,
    #     guardrailOption,
    #     rerankerOption,
    # )

    # return {"results": results["answer"]}

     # Get the current trace (span) and tag it with the chatbot.id attribute.
    # current_span = trace.get_current_span()
    # current_span.set_attribute("chatbot.id", chatbot_id)

    # tracer_provider = register(
    #     # project_name="testing1",
    #     project_name=chatbot_id,
    #     endpoint="http://localhost:6006/v1/traces",
    #     auto_instrument=True  # Automatically instruments supported libraries
    # )

    # Call your existing service logic.
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
        chatbot_id
    )
    
    
    # Process the final answer.
    final_answer = ""
    if isinstance(results_object, dict):
        final_answer = results_object.get("result") or results_object.get("answer", "No answer found in results.")
    elif isinstance(results_object, str):
        final_answer = results_object
    else:
        final_answer = "Could not process the response from the service."

    # Get the current trace (span) to export trace_id
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()
    
    trace_id = ""
    if span_context.is_valid:
        trace_id = format(span_context.trace_id, '032x')
        # print(f"✅ Captured Trace ID: {trace_id}")
    else:
        # Fallback if no active trace
        trace_id = ""
        print("⚠️ No active trace found for this request.")

    return {"answer": final_answer, "traceId": trace_id,"citations": results_object.get("document_pages_dict", [])}


