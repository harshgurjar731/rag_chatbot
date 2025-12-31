from fastapi import APIRouter, HTTPException, Depends, Query
from pathlib import Path
from sqlmodel import Session, select
from database import get_session
import os
import shutil
import time
from typing import List
from models.datastore import KnowledgeAssistant, DataStore
from models.FileRecord import DocumentRecord
from rag_pipeline.rag_models import CreateAssitantRequest, KnowledgeAssistantResponse, ChatInterfaceDetails

from rag_pipeline.Config.rag_config import RAG_CONFIG
from rag_pipeline.Services.retrieve_service import retrieve_documents
from opentelemetry import trace
# from opentelemetry.sdk.trace import TracerProvider
from phoenix.otel import register, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from openinference.instrumentation.langchain import LangChainInstrumentor
from openinference.instrumentation.openai import OpenAIInstrumentor
# from openinference.instrumentation import dangerously_using_project
from dotenv import load_dotenv
from rag_pipeline.Services.otel_tracer_singleton import OtelTracerSingleton

load_dotenv(override=True)
trace_provider = None

router = APIRouter()
# otel_tracer_singleton = OtelTracerSingleton()

def configure_opentelemetry_for_phoenix(project_name="default"):
    """
    Configures OpenTelemetry with a standard OTLP exporter pointing to Phoenix.
    """
    endpoint = "http://localhost:6006/v1/traces"
    # project_name = "RAGBOT"
    os.environ["PHOENIX_PROJECT_NAME"] = project_name

    print(f"📡 Configuring Phoenix Tracing to: {endpoint} (Project: {project_name})")

    # 1. Define Resource
    # resource = Resource(attributes={
    #     "service.name": "rag_backend",
    #     "project_name": project_name 
    # })

    # 2. Setup Provider
    # tracer_provider = TracerProvider(resource=resource)
    tracer_provider = register(project_name=project_name, auto_instrument=True)
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    OtelTracerSingleton().otel_tracers[project_name] = tracer_provider
    print(f'OTEL: otel_tracers = {OtelTracerSingleton().otel_tracers}')
    # 3. Setup OTLP Exporter with HEADERS
    # otlp_exporter = OTLPSpanExporter(
    #     endpoint=endpoint,
    #     headers={"project_name": project_name} 
    # )
    
    # 4. Use BatchSpanProcessor for production
    # tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # trace.set_tracer_provider(tracer_provider)
    # # 5. Set as Global Provider
    # try:
    #     trace.set_tracer_provider(tracer_provider)
    # except Exception as e:
    #     print(f"⚠️ Failed to set tracer provider: {e}")
    
    # 6. Instrument Libraries
    # try:
    #     LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    #     OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    #     print("✅ Instrumentation Complete: LangChain & OpenAI")
    # except Exception as e:
    #     print(f"⚠️ Instrumentation Error: {e}")

@router.post("/createAssistant/")
async def createAssistant(
    data: CreateAssitantRequest,
    session: Session = Depends(get_session),
    ):

    print("Creating new assistant with name:", data.name)
    # 1️⃣ Check for duplicate name
    existing = session.exec(select(KnowledgeAssistant).where(KnowledgeAssistant.name == data.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Knowledge Assistant already exists")

    print("No existing Knowledge Assistant found, proceeding to create.")

    # 2️⃣ Create datastore record
    print("Create Chatbot Data", data)
    new_assistant = KnowledgeAssistant(name=data.name, description=data.description, datastore_id=data.datastore_id)
    session.add(new_assistant)
    session.commit()
    session.refresh(new_assistant)
    print(f'OTEL new_assistant.id = {new_assistant.id}, type = {type(new_assistant.id)}')
    OtelTracerSingleton().otel_id_to_project_name[str(new_assistant.id)] = new_assistant.name
    print(f'OTEL: otel_id_to_project_name = {OtelTracerSingleton().otel_id_to_project_name}')
    configure_opentelemetry_for_phoenix(project_name=new_assistant.name)

    return new_assistant

@router.get("/getAssistants" , response_model=List[KnowledgeAssistantResponse])
async def get_assistants(session: Session = Depends(get_session)):
    assistants = session.exec(select(KnowledgeAssistant)).all()
    return_assistants: List[KnowledgeAssistantResponse] = []
    for assistant in assistants:
        # docs = session.exec(select(DocumentRecord.id).where(DocumentRecord.datastore_id == datastore.id)).all()
        # datastore["documentCount"] = len(docs)
        print("Model Dump", assistant.model_dump())
        return_assistants.append( KnowledgeAssistantResponse(
            **assistant.model_dump(),
        ))

    print(f"Found datastores.", return_assistants)
    return return_assistants


@router.post("/deleteAssistant/{assistant_id}" , response_model=KnowledgeAssistantResponse)
async def delete_assistant(
    assistant_id: int, 
    session: Session = Depends(get_session)):

    assistant = session.exec(select(KnowledgeAssistant).where(KnowledgeAssistant.id == assistant_id)).first()
    session.delete(assistant)
    session.commit()
    return assistant



@router.post("/query/{chatbot_id}", response_model=dict)
async def retrieve(
    chatbot_id: str,
    data: ChatInterfaceDetails,
    use_knowledge_base: bool = Query(True),
    llm_model_provider: str = Query(
        RAG_CONFIG["default_llm_provider"], description="LLM model provider"
    ),
    llm_model_name: str = Query(
        RAG_CONFIG["default_llm_model"], description="LLM model name"
    ),
    # llm_endpoint: str = Query(
    #     RAG_CONFIG["default_llm_endpoint"], description="LLM endpoint"
    # ),
    temperature: float = Query(
        RAG_CONFIG["default_temperature"], description="LLM temperature"
    ),
    # top_p: float = Query(
    #     RAG_CONFIG["default_top_p"],
    #     ge=0.0,
    #     le=1.0, 
    #     description="LLM temperature"
    # ),
    max_token: int = Query(
        RAG_CONFIG["default_max_tokens"],
        ge=0,
        le=8192,
        description="Token size (between 256 and 2048)",
    ),
    use_reranker: bool = False,
    reranker_type: str = Query(
        RAG_CONFIG["default_reranker_type"], description="Reranker type to use"
    ),
    # reranker_model_endpoint: str = Query(
    #     CONFIG["default_reranker_model_endpoint"], description="Reranker model endpointoption to use"
    # ),
    # reranker_top_k: int = Query(
    #     RAG_CONFIG["default_reranker_top_k"],
    #     ge=0,
    #     le=25, 
    #     description="Reranker Top L"
    # ),
    # use_query_rewriting: bool = False,
    query_rewriting_type: str = Query(
        RAG_CONFIG["default_query_rewriting_type"],
        description="Query Rewriter Type"
    ),

    use_guardrail: bool = False,

    guardrail_type: str = Query(
        RAG_CONFIG["default_guardrail_type"],
        description="Query Rewriter Type"
    ),

    use_citation: bool = False,
    datastore_id: str = "",
    query: str = "",
    is_vision_search: bool = False,
    

    # use_VLM_inference: bool = False,

    # vlm_model_name: str = Query(
    #     RAG_CONFIG["default_vlm_model"], description="Embedding model name"
    # ),
    # vlm_endpoint: str = Query(
    #     RAG_CONFIG["default_vlm_endpoint"], description="Embedding endpoint"
    # ),

    # document_id: List[int] = Query(..., description="File IDs to search within"),
    session: Session = Depends(get_session)
):
    # Call your existing service logic.
    print("In rag router /query", data, is_vision_search)
    
    datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()

    # Map selected filenames to full file paths
    final_selected_documents = []
    
    # Only perform file path resolution for ChromaDB
    # For other vector stores (like PGVector, Milvus), we might use file IDs or plain text matching
    if datastore and datastore.vector_store_provider == "ChromaDB":
        if data.selected_documents:
            for doc_name in data.selected_documents:
                # If it already looks like a path, keep it
                if "/" in doc_name or "\\" in doc_name:
                    final_selected_documents.append(doc_name)
                    continue
                    
                # Lookup the file path in the database
                doc_record = session.exec(
                    select(DocumentRecord).where(
                        (DocumentRecord.datastore_id == datastore_id) & 
                        (DocumentRecord.filename == doc_name)
                    )
                ).first()
                
                if doc_record and doc_record.filePath:
                    print(f"Mapped document '{doc_name}' to path: {doc_record.filePath}")
                    final_selected_documents.append(doc_record.filePath)
                else:
                    print(f"Warning: Could not find file path for document '{doc_name}' in datastore {datastore_id}")
                    final_selected_documents.append(doc_name)
    else:
        # For non-ChromaDB providers, pass the list as-is (or handle differently if needed)
        final_selected_documents = data.selected_documents if data.selected_documents else []
    results_object = await retrieve_documents(
                query,
                search_image=data.search_image,
                message_history=data.messages,
                selected_documents= final_selected_documents,
                use_knowledge_base=use_knowledge_base,
                query_optimizer= query_rewriting_type,
                embedding_model_name= datastore.embedding_model,
                embedding_model_provider= datastore.embedding_provider,
                llm_model_name= llm_model_name,
                llm_model_provider= llm_model_provider,
                temperature = temperature,
                vector_db = datastore.vector_store_provider,
                token_size= max_token,
                sources= use_citation,
                guardrailOption= guardrail_type,
                rerankerOption= reranker_type,
                datastore_id= datastore_id,
                is_vision_search= is_vision_search,
                project_id=chatbot_id,
    )
    
    # # Process the final answer.
    # final_answer = ""
    # if isinstance(results_object, dict):
    #     final_answer = results_object.get("result") or results_object.get("answer", "No answer found in results.")
    # elif isinstance(results_object, str):
    #     final_answer = results_object
    # else:
    #     final_answer = "Could not process the response from the service."

    # Get the traceId to send back to the frontend for the feedback feature.
    # span_context = current_span.get_span_context()
    trace_id = ""
    # if span_context.is_valid:
    #     trace_id = format(span_context.trace_id, '032x')
    #     print(f"✅ Successfully captured Phoenix trace_id: {trace_id}")
    # else:
    #     trace_id = str(uuid.uuid4())
    #     print(f"⚠️ WARNING: Could not find a valid span context. Using generated UUID as trace_id: {trace_id}")

    # return {"answer": final_answer, "traceId": trace_id,"citations": results_object.get("document_pages_dict", [])}
    return results_object