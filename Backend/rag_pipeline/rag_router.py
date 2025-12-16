from fastapi import APIRouter, HTTPException, Depends, Query
from pathlib import Path
from sqlmodel import Session, select
from database import get_session
import os
import shutil
import time
from typing import List
from models.datastore import KnowledgeAssistant, DataStore
from rag_pipeline.rag_models import CreateAssitantRequest, KnowledgeAssistantResponse, ChatInterfaceDetails

from rag_pipeline.Config.rag_config import RAG_CONFIG
from rag_pipeline.Services.retrieve_service import retrieve_documents

router = APIRouter()

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
    results_object = await retrieve_documents(
        query,
        search_image=data.search_image,
        message_history=data.messages,
        selected_documents= data.selected_documents,
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