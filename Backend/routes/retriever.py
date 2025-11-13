# rag_app/backend/routes/query.py
from fastapi import APIRouter, Query
from Services.retriever_service import retrieve_documents
# from Services.agent_retriever_service import retrieve_documents
from typing import List
from config import CONFIG  # 🔹 centralized env-driven config
import uuid
from fastapi import Path
from phoenix import trace
from phoenix.otel import register
from Services.VisRag.query_pipeline import query_pipeline  # ✅ Import VisRAG multimodal query




router = APIRouter()


# @router.get("/query/{chatbot_id}", response_model=dict)
# def retrieve(
#     chatbot_id: str = Path(..., description="The ID of the chatbot being queried"),
#     query: str = Query(..., description="User query"),
#     query_optimizer: str = Query(
#         CONFIG["default_query_optimizer"], description="Query optimizer to use"
#     ),
#     embedding_model_name: str = Query(
#         CONFIG["default_embedding_model"], description="Embedding model"
#     ),
#     llm_model_name: str = Query(
#         CONFIG["default_llm_model"], description="LLM model name"
#     ),
#     vector_db: str = Query(CONFIG["default_vector_db"], description="Vector DB name"),
#     file_id: List[int] = Query(..., description="File IDs to search within"),
#     temperature: float = Query(
#         CONFIG["default_temperature"], description="LLM temperature"
#     ),
#     guardrailOption: str = Query(
#         CONFIG["default_guardrail_option"], description="Guardrail option"
#     ),
#     token_size: int = Query(
#         CONFIG["default_token_size"],
#         ge=256,
#         le=2048,
#         description="Token size (between 256 and 2048)",
#     ),
#     sources: bool = Query(False, description="Include sources in the response"),
#     rerankerOption: str = Query(
#         CONFIG["default_reranker_option"], description="Reranker option to use"
#     ),

# ):
    
#     tracer_provider = register(
#         # project_name="testing1",
#         project_name=chatbot_id,
#         endpoint="http://localhost:6006/v1/traces",
#         auto_instrument=True  # Automatically instruments supported libraries
#     )

#     # Call your existing service logic.
#     results_object = retrieve_documents(
#         query,
#         query_optimizer,
#         embedding_model_name,
#         llm_model_name,
#         vector_db,
#         file_id,
#         temperature,
#         token_size,
#         sources,
#         guardrailOption,
#         rerankerOption,
#         chatbot_id
#     )
    
    
#     # Process the final answer.
#     final_answer = ""
#     if isinstance(results_object, dict):
#         final_answer = results_object.get("result") or results_object.get("answer", "No answer found in results.")
#     elif isinstance(results_object, str):
#         final_answer = results_object
#     else:
#         final_answer = "Could not process the response from the service."

#     trace_id = ""
   
#     return {"answer": final_answer, "traceId": trace_id,"citations": results_object.get("document_pages_dict", [])}




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
    useVRAG: bool = Query(
        False,
        description="If True, use VisRAG multimodal query pipeline (Pixtral + FAISS multimodal)",
    ),
):
    """
    Retrieves answers using the standard RAG pipeline or the VisRAG multimodal pipeline.
    If `useVRAG` is true, the Pixtral-powered vision-text query pipeline is used.
    """

    tracer_provider = register(
        project_name=chatbot_id,
        endpoint="http://localhost:6006/v1/traces",
        auto_instrument=True,
    )

    # -----------------------------------------
    # 🧠 If useVRAG=True → Run Vision RAG (Pixtral)
    # -----------------------------------------
    if useVRAG:
        print(f"🚀 Running VisRAG multimodal query pipeline for chatbot {chatbot_id} ...")

        # Convert numeric DB file IDs to VisRAG file_id strings
        visrag_file_ids = [f"file_{fid}" for fid in file_id]

        try:
            vrag_result = query_pipeline(visrag_file_ids, query)
            final_answer = vrag_result.get("answer", "No answer generated.")
            trace_id = ""

            # Match return format of standard RAG API
            return {
                "answer": final_answer,
                "traceId": trace_id,
                "citations": vrag_result.get("document_pages_dict", []),
            }

        except Exception as e:
            print(f"❌ VisRAG pipeline failed: {e}")
            return {
                "answer": f"Error running VisRAG pipeline: {str(e)}",
                "traceId": "",
                "citations": [],
            }

    # -----------------------------------------
    # 🔍 Else → Run existing RAG flow unchanged
    # -----------------------------------------
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
        chatbot_id,
    )

    # Process the final answer (existing logic preserved)
    if isinstance(results_object, dict):
        final_answer = results_object.get("result") or results_object.get("answer", "No answer found in results.")
    elif isinstance(results_object, str):
        final_answer = results_object
    else:
        final_answer = "Could not process the response from the service."

    trace_id = ""

    return {
        "answer": final_answer,
        "traceId": trace_id,
        "citations": results_object.get("document_pages_dict", []),
    }
