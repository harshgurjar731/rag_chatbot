from fastapi import APIRouter, Query, Path
from Services.retriever_service import retrieve_documents
from typing import List
from config import CONFIG
from opentelemetry import trace
import uuid
from phoenix.otel import register
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
import phoenix as px
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
# from opentelemetry.instrumentation.langchain import LangchainInstrumentor # etc.

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

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
    sources: bool = Query(False, description="Include that context which was used  in the response"),
    rerankerOption: str = Query(
        CONFIG["default_reranker_option"], description="Reranker option to use"
    ),
):
    # Get the current trace (span) and tag it with the chatbot.id attribute.
    current_span = trace.get_current_span()
    current_span.set_attribute("chatbot.id", chatbot_id)

    def update_phoenix_project_name(chatbot_id: str):
        os.environ["PHOENIX_PROJECT_NAME"] = chatbot_id

        tracer_provider = register(project_name=chatbot_id,endpoint="http://localhost:6006/v1/traces",auto_instrument=True)
        #  ,  # Automatically instruments supported libraries
        return tracer_provider
    
    tracer_provider = update_phoenix_project_name(chatbot_id)
    


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

    # Get the traceId to send back to the frontend for the feedback feature.
    span_context = current_span.get_span_context()
    trace_id = ""
    if span_context.is_valid:
        trace_id = format(span_context.trace_id, '032x')
        print(f"✅ Successfully captured Phoenix trace_id: {trace_id}")
    else:
        trace_id = str(uuid.uuid4())
        print(f"⚠️ WARNING: Could not find a valid span context. Using generated UUID as trace_id: {trace_id}")


    # def reset_tracing():
    #     provider = trace.get_tracer_provider()
    #     if isinstance(provider, TracerProvider):
    #         provider.shutdown()
    #         trace.set_tracer_provider(TracerProvider())

    #     print("✅ OpenTelemetry traces reset successfully.")
    
    # reset_tracing()
    


#     def reset_tracing():
    
#         # Step 1: Gracefully shut down the current provider to flush all buffered traces.
#         provider = trace.get_tracer_provider()
#         if isinstance(provider, TracerProvider):
#             provider.shutdown()

#     # Step 2: CRITICAL - Un-instrument the libraries to remove the old configuration.
#     # You must add a line here for every library you are tracing.
#         LangchainInstrumentor().uninstrument()
#         OpenAIInstrumentor().uninstrument()

#     # LangchainInstrumentor().uninstrument() # Add this line if you trace LangChain

#     # Step 3: Reset the global provider to a clean, default state for the next session.
#         trace.set_tracer_provider(TracerProvider())

#         print("✅ OpenTelemetry traces reset successfully.")

# # Example of how you'd call it after a session ends
#     reset_tracing()



    del tracer_provider
    return {"answer": final_answer, "traceId": trace_id,"citations": results_object.get("document_pages_dict", [])}