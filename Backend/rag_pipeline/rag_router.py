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
import json
from rag_pipeline.rag_models import CreateAssitantRequest, KnowledgeAssistantResponse, ChatInterfaceDetails, FeedbackRequest

from rag_pipeline.Config.rag_config import RAG_CONFIG
# from rag_pipeline.Services.retrieve_service import retrieve_documents

from opentelemetry import trace
import requests
import datetime
from rag_pipeline.bot_manager import BotManager
from rag_pipeline.bot_communication import BotCommunicator
from rag_pipeline.bot_utils import validate_bot_name, sanitize_bot_name

router = APIRouter()
bot_manager = BotManager()
bot_comm = BotCommunicator(redis_host=os.getenv("REDIS_HOST", "redis"))


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
    try:
        new_assistant = KnowledgeAssistant(name=data.name, description=data.description, datastore_id=data.datastore_id)
        session.add(new_assistant)
        session.commit()
        session.refresh(new_assistant)

        new_id = new_assistant.id
        success, message = bot_manager.create_bot(new_id, data.name , data.datastore_id)
        
        if not success:
            raise Exception(f"Bot manager failed: {message}")
    
        return new_assistant
    except Exception as e:
        session.rollback()
        print(f"Error creating assistant: {e}")
        # If bot was partially created, we might want to attempt cleanup here, but for now just rollback DB
        raise HTTPException(status_code=500, detail=f"Failed to create assistant: {str(e)}")

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
    assistant_id: str, 
    session: Session = Depends(get_session)):

    try:
        assistant = session.exec(select(KnowledgeAssistant).where(KnowledgeAssistant.id == assistant_id)).first()
        if not assistant:
             raise HTTPException(status_code=404, detail="Assistant not found")
             
        session.delete(assistant)
        session.commit()

        bot_id = assistant.id
        try:
            success, message = bot_manager.delete_bot(bot_id)
            if not success:
                print(f"Warning: Bot manager delete failed: {message}")
            bot_comm.cleanup_bot_data(bot_id)
        except Exception as e:
             print(f"Warning: Failed to cleanup bot resources: {e}")
        
        return assistant
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        print(f"Error deleting assistant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete assistant: {str(e)}")



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

    full_response = ""
    
    try:
        # Stream response from bot
        # for chunk in bot_comm.send_message_streaming(
        #     bot_name=chatbot_id,
        #     message_text=query,
        #     timeout=60,
        #     use_knowledge_base=use_knowledge_base,
        #     llm_model_provider=llm_model_provider,
        #     llm_model_name=llm_model_name,
        #     temperature=temperature,
        #     max_token=max_token,
        #     use_reranker=use_reranker,
        #     reranker_type=reranker_type,
        #     query_rewriting_type=query_rewriting_type,
        #     use_guardrail=use_guardrail,
        #     guardrail_type=guardrail_type,
        #     use_citation=use_citation,
        #     datastore_id=datastore_id,
        #     query=query,
        #     is_vision_search=is_vision_search,
        #     messages=[m.dict() for m in data.messages] if data.messages else [],
        #     selected_documents=data.selected_documents if data.selected_documents else []
            
        # ):
        #     print("2")  
        #     full_response += chunk
        #     print(f"full_response: {full_response}")
        
        full_response = bot_comm.send_message(
            bot_name=chatbot_id,
            message_text=query,
            timeout=0,
            use_knowledge_base=use_knowledge_base,
            llm_model_provider=llm_model_provider,
            llm_model_name=llm_model_name,
            temperature=temperature,
            max_token=max_token,
            use_reranker=use_reranker,
            reranker_type=reranker_type,
            query_rewriting_type=query_rewriting_type,
            use_guardrail=use_guardrail,
            guardrail_type=guardrail_type,
            use_citation=use_citation,
            datastore_id=datastore_id,
            query=query,
            is_vision_search=is_vision_search,
            messages=[m.dict() for m in data.messages] if data.messages else [],
            selected_documents=data.selected_documents if data.selected_documents else []
        )
        if full_response and not full_response.startswith("Error:"):
            
            # Try to parse as JSON first
            try:
                json_response = json.loads(full_response)
                if isinstance(json_response, dict):
                     return json_response
            except json.JSONDecodeError:
                pass
            
            # Fallback for plain text
            return {"answer": full_response}
        else:
            
            raise HTTPException(status_code=400, detail=full_response or "⚠️ No reply received. The bot may be offline.")
    except Exception as e:
        error_msg = f"⚠️ Error processing query: {str(e)}"
        print(f"Query Error: {e}")
        raise HTTPException(status_code=500, detail=error_msg)

    # Call your existing service logic.
    print("In rag router /query", data, is_vision_search)
    
    # datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()

    # # Map selected filenames to full file paths
    # final_selected_documents = []
    
    # # Only perform file path resolution for ChromaDB
    # # For other vector stores (like PGVector, Milvus), we might use file IDs or plain text matching
    # if datastore and datastore.vector_store_provider == "ChromaDB":
    #     if data.selected_documents:
    #         for doc_name in data.selected_documents:
    #             # If it already looks like a path, keep it
    #             if "/" in doc_name or "\\" in doc_name:
    #                 final_selected_documents.append(doc_name)
    #                 continue
                    
    #             # Lookup the file path in the database
    #             doc_record = session.exec(
    #                 select(DocumentRecord).where(
    #                     (DocumentRecord.datastore_id == datastore_id) & 
    #                     (DocumentRecord.filename == doc_name)
    #                 )
    #             ).first()
                
    #             if doc_record and doc_record.filePath:
    #                 print(f"Mapped document '{doc_name}' to path: {doc_record.filePath}")
    #                 final_selected_documents.append(doc_record.filePath)
    #             else:
    #                 print(f"Warning: Could not find file path for document '{doc_name}' in datastore {datastore_id}")
    #                 final_selected_documents.append(doc_name)
    # else:
    #     # For non-ChromaDB providers, pass the list as-is (or handle differently if needed)
    #     final_selected_documents = data.selected_documents if data.selected_documents else []

     # # Manually start a span since FastAPI instrumentation might be missing or incomplete
    # tracer = trace.get_tracer(__name__)
    # with tracer.start_as_current_span("rag_query_handler") as span:
    #     # results_object = await retrieve_documents(
    #     #     query,
    #     #     search_image=data.search_image,
    #     #     message_history=data.messages,
    #     #     selected_documents= final_selected_documents,
    #     #     use_knowledge_base=use_knowledge_base,
    #     #     query_optimizer= query_rewriting_type,
    #     #     embedding_model_name= datastore.embedding_model,
    #     #     embedding_model_provider= datastore.embedding_provider,
    #     #     llm_model_name= llm_model_name,
    #     #     llm_model_provider= llm_model_provider,
    #     #     temperature = temperature,
    #     #     vector_db = datastore.vector_store_provider,
    #     #     token_size= max_token,
    #     #     sources= use_citation,
    #     #     guardrailOption= guardrail_type,
    #     #     rerankerOption= reranker_type,
    #     #     datastore_id= datastore_id,
    #     #     is_vision_search= is_vision_search,
    #     # )
        
    #     # Set attributes for Phoenix to display Input/Output
    #     span.set_attribute("input.value", query)
    #     # if isinstance(results_object, dict):
    #     #     # Try to grab just the answer if possible, or dump the whole thing
    #     #     answer_content = results_object.get("answer", str(results_object))
    #     #     span.set_attribute("output.value", answer_content)
    #     # else:
    #     #     span.set_attribute("output.value", str(results_object))

    #     # Get the traceId to send back to the frontend for the feedback feature.
    #     # current_span = trace.get_current_span() # Should be 'span'
    #     span_context = span.get_span_context()
    #     trace_id = ""
    #     span_id = ""
    #     if span_context.is_valid:
    #         trace_id = format(span_context.trace_id, '032x')
    #         span_id = format(span_context.span_id, '016x')
    #         print(f"✅ Successfully captured Phoenix trace_id: {trace_id}, span_id: {span_id}")
    #     else:
    #         # trace_id = str(uuid.uuid4())
    #         print(f"⚠️ WARNING: Could not find a valid span context. Using generated UUID as trace_id: {trace_id}")

    #     # return {"answer": final_answer, "traceId": trace_id,"citations": results_object.get("document_pages_dict", [])}
    #     # if isinstance(results_object, dict):
    #     #     results_object["traceId"] = trace_id
    #     #     results_object["spanId"] = span_id # Sending spanId
    #     # elif isinstance(results_object, str):
    #     #     # If it's just a string, we might need to change implementation of retrieve_documents or wrap it
    #     #     pass

    #     # return results_object


@router.post("/feedback")
async def log_feedback(
    feedback_data: FeedbackRequest,
    session: Session = Depends(get_session)
):
    print(f"Received feedback: {feedback_data}")
    
    # Use REST API to log annotation since phoenix client is not available in broken env
    phoenix_base_url = os.getenv('PHOENIX_COLLECTOR_ENDPOINT', '')
    phoenix_url = f"{phoenix_base_url}/v1/span_annotations" # or /v1/traces/{trace_id}/annotations?
    # Correct endpoint for Arize Phoenix (local) from research seems to be /v1/span_annotations
    
    # Map feedback to score
    score = 1.0 if feedback_data.feedback == "Positive" else 0.0
    
    # Phoenix /v1/span_annotations expects a list of annotations wrapped in "data"
    payload = {
        "data": [
            {
                "span_id": feedback_data.span_id,
                "name": "feedback", # Evaluation name changed from thumbs_up
                "annotator_kind": "HUMAN",
                "result": {
                    "label": feedback_data.feedback,
                    "score": score,
                    "explanation": "User feedback from chat interface"
                }
            }
        ]
    }

    try:
        response = requests.post(phoenix_url, json=payload, params={"sync": "false"})
        if response.status_code >= 200 and response.status_code < 300:
             print("✅ Feedback logged to Phoenix via REST")
             return {"status": "success"}
        else:
             print(f"⚠️ Failed to log feedback: {response.status_code} {response.text}")
             # Try fallback to trace_id based endpoint if span_id fails? 
             pass
             
    except Exception as e:
        print(f"Error logging feedback: {e}")
    
    return {"status": "submitted"}
