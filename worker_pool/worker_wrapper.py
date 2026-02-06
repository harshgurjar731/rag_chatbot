"""
Worker Process Wrapper.

This script runs as a standalone worker process managed by the worker pool.
It listens for messages on Redis, processes them using the RAG pipeline, and
streams responses back.
"""

import os
import redis
import asyncio
import json
import uuid
import sys
from sqlmodel import create_engine, Session, select
from opentelemetry import trace
# from phoenix.otel import register

# Ensure we can import from Backend
# transform path to include root rag_chatbot folder if running from there
sys.path.append(os.getcwd())

# Imports from Backend
from models.datastore import DataStore
from models.FileRecord import DocumentRecord
from rag_pipeline.Services.retrieve_service import retrieve_documents
from rag_pipeline.Config.rag_config import RAG_CONFIG
from rag_pipeline.rag_models import Message

# Configuration
BOT_NAME = os.getenv("BOT_NAME", "default")
BOT_ID = os.getenv("BOT_ID", "-1")
DATASTORE_ID = os.getenv("DATASTORE_ID", "-1")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

print(f'BOT_NAME = {BOT_NAME}')
print(f'BOT_ID = {BOT_ID}')
print(f'DATASTORE_ID = {DATASTORE_ID}')
print(f'REDIS_HOST = {REDIS_HOST}')

# Redis Connection
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# Database Setup
# Using absolute path to ensure we find the DB
# Database Setup
from database import engine

# OpenTelemetry
# tracer_provider = register(
#     project_name=BOT_NAME,
#     auto_instrument=True,
#     batch=False
# )

async def process_message(message_data):
    """
    Process a single message and stream responses back via Redis PubSub.

    Retrieves necessary configurations from the message data, rebuilds context/history,
    invokes the retrieval service, and publishes results (or chunks) to Redis.
    
    Args:
        message_data (dict): The message payload containing query, history, and config.
    """
    # Extract fields
    msg_id = message_data.get('id')
    text = message_data.get('text', '') # This is the query? Or message_data.get('query')?
    # rag_router passes "text": message_text. 
    # message_text = query. 
    # But message_data also has 'query'.
    query = message_data.get('query') or text
    
    response_channel = f"msg:{msg_id}:stream"

    print(f"[*] Processing message {msg_id} for {BOT_NAME}: {query[:20]}...")
    
    # Extract other params
    chatbot_id = message_data.get('chatbot_id')
    use_knowledge_base = message_data.get('use_knowledge_base') if message_data.get('use_knowledge_base') is not None else True
    llm_model_provider = message_data.get('llm_model_provider') or RAG_CONFIG["default_llm_provider"]
    llm_model_name = message_data.get('llm_model_name') or RAG_CONFIG["default_llm_model"]
    temperature = float(message_data.get('temperature') or RAG_CONFIG["default_temperature"])
    max_token = int(message_data.get('max_token') or RAG_CONFIG["default_max_tokens"])
    use_reranker = message_data.get('use_reranker') if message_data.get('use_reranker') is not None else False
    reranker_type = message_data.get('reranker_type') or RAG_CONFIG["default_reranker_type"]
    query_rewriting_type = message_data.get('query_rewriting_type') or RAG_CONFIG["default_query_rewriting_type"]
    use_guardrail = message_data.get('use_guardrail') if message_data.get('use_guardrail') is not None else False
    guardrail_type = message_data.get('guardrail_type') or RAG_CONFIG["default_guardrail_type"]
    use_citation = message_data.get('use_citation') if message_data.get('use_citation') is not None else False
    datastore_id = message_data.get('datastore_id') or DATASTORE_ID
    is_vision_search = message_data.get('is_vision_search') if message_data.get('is_vision_search') is not None else False
    
    # Reconstruct message history
    raw_history = message_data.get('messages', []) # If passed directly? 
    # rag_router doesn't pass 'messages' list in payload in bot_communication.py?
    # bot_communication.py payload:
    # "text": message_text, "query": query, ...
    # It DOES NOT include 'messages' history in payload!
    # Wait, check bot_communication.py again.
    
    # If history is missing, we might have a problem for conversation context.
    # Assuming 'query' is just the last message.
    # We might need to fix bot_communication.py to include history if needed.
    # For now, create a basic history with just the current query if missing?
    # Or just empty list.
    
    # Actually, verify_fix.py sends "messages": [{"role": "user", ...}] to API.
    # API calls rag_router /query.
    # rag_router calls bot_comm.send_message_streaming.
    # send_message_streaming args: ... no 'message_history' arg!
    # rag_router calls it with `message_text=query`.
    
    # Issue identified: Protocol mismatch. 
    # rag_router passes data.messages to retrieve_documents, but bot_communication.py 
    # signature does NOT accept message history.
    # I should check bot_communication.py signature again.
    
    try:
        # DB Session for resolver
        with Session(engine) as session:
            
            # Fetch DataStore
            datastore = None
            if datastore_id:
                datastore = session.exec(select(DataStore).where(DataStore.id == int(datastore_id))).first()
            
            # Resolve selected documents
            selected_docs_payload = message_data.get('selected_documents', [])
            final_selected_documents = [] 
            
            if datastore and datastore.vector_store_provider == "ChromaDB":
                if selected_docs_payload:
                    for doc_name in selected_docs_payload:
                        # If it already looks like a path, keep it
                        if "/" in doc_name or "\\" in doc_name:
                            final_selected_documents.append(doc_name)
                            continue
                            
                        # Lookup the file path in the database
                        doc_record = session.exec(
                            select(DocumentRecord).where(
                                (DocumentRecord.datastore_id == int(datastore_id)) & 
                                (DocumentRecord.filename == doc_name)
                            )
                        ).first()
                        
                        if doc_record and doc_record.filePath:
                            # print(f"Mapped document '{doc_name}' to path: {doc_record.filePath}")
                            final_selected_documents.append(doc_record.filePath)
                        else:
                            # print(f"Warning: Could not find file path for document '{doc_name}'")
                            final_selected_documents.append(doc_name)
            else:
                final_selected_documents = selected_docs_payload

            # Tracer
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("rag_query_handler") as span:
                span.set_attribute("input.value", query)

                # Call retrieve_documents
                # construct message history
                raw_history = message_data.get('messages', [])
                message_history = []
                if raw_history:
                    try:
                        # Convert dicts back to Message objects
                        message_history = [Message(**msg) for msg in raw_history]
                    except Exception as e:
                        print(f"Error parsing history: {e}")
                        message_history = [Message(role="user", content=query)]
                else:
                    message_history = [Message(role="user", content=query)]
                
                # Get search image
                search_image = message_data.get('search_image', "")
                
                # Note: retrieve_service.py expects List[Message] objects
                
                results_object = await retrieve_documents(
                    query=query,
                    search_image=search_image, 
                    message_history=message_history, 
                    selected_documents=final_selected_documents,
                    use_knowledge_base=use_knowledge_base,
                    query_optimizer=query_rewriting_type,
                    embedding_model_name=datastore.embedding_model if datastore else None,
                    embedding_model_provider=datastore.embedding_provider if datastore else None,
                    llm_model_name=llm_model_name,
                    llm_model_provider=llm_model_provider,
                    temperature=temperature,
                    vector_db=datastore.vector_store_provider if datastore else None,
                    token_size=max_token,
                    sources=use_citation,
                    guardrailOption=guardrail_type,
                    rerankerOption=reranker_type,
                    datastore_id=datastore_id,
                    is_vision_search=is_vision_search,
                )
                
                # Extract answer
                answer = ""
                trace_id = ""
                span_id = ""
                
                span_context = span.get_span_context()
                if span_context.is_valid:
                    trace_id = format(span_context.trace_id, '032x')
                    span_id = format(span_context.span_id, '016x')
                
                if isinstance(results_object, dict):
                    answer = results_object.get("answer", str(results_object))
                    results_object["traceId"] = trace_id
                    results_object["spanId"] = span_id
                    # Publish the whole object as JSON? or just answer?
                    # rag_router expects streaming text? 
                    # send_message_streaming yields chunks.
                    # If I send JSON string, rag_router will emit it as chunk?
                    # rag_router collects chunks: full_response += chunk
                    # Then returns {"answer": full_response}
                    # So ideally I should output TEXT answer.
                    # But if I output text, how does it get traceId?
                    
                    # rag_router:
                    # for chunk in bot_comm...
                    # full_response += chunk
                    # ...
                    # return {"answer": full_response}
                    
                    # This implies rag_router expects pure text. 
                    # But it also tries to set traceId?
                    # "Get the traceId to send back... if isinstance(results_object, dict)..."
                    # The commented out code in rag_router suggests it WANTS traceId.
                    # But the CURRENT implementation in rag_router just returns {"answer": full_response}.
                    
                    # Publish the whole object as JSON
                    print("a")
                    r.publish(response_channel, json.dumps(results_object))
                    
                else:
                    answer = str(results_object)
                    print("b")
                    r.publish(response_channel, json.dumps({"answer": answer}))
                
                span.set_attribute("output.value", answer)
                print("c")
                
    except Exception as e:
        print(f"[!] Error processing message: {e}")
        r.publish(response_channel, f"Error: {str(e)}")
        
    finally:
        # End stream
        r.publish(response_channel, "__END__")


async def heartbeat_loop():
    """
    Maintain Redis heartbeat to show bot is alive.
    Runs indefinitely, updating a TTL key in Redis every 5 seconds.
    """
    while True:
        try:
            # Heartbeat now includes PID so the pool manager can track it too if needed
            r.setex(f"bot:{BOT_ID}:heartbeat", 10, f"alive:{os.getpid()}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[!] Heartbeat error: {e}")
            await asyncio.sleep(5)

async def message_loop():
    """
    Poll Redis list for new messages.
    Blocking pop (blpop) is used to wait for messages efficiently.
    """
    inbox_key = f"bot:{BOT_ID}:inbox"
    print(f"[*] {BOT_ID} listening on {inbox_key}")
    
    while True:
        try:
            result = r.blpop(inbox_key, timeout=1)
            
            if result:
                _, message_json = result
                message_data = json.loads(message_json)
                await process_message(message_data)
            else:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"[!] Message loop error: {e}")
            await asyncio.sleep(1)

async def main():
    """
    Main entry point for the worker process.
    Starts the heartbeat loop and the message polling loop.
    """
    print(f"[*] Bot process started: {BOT_NAME} (PID: {os.getpid()})")
    asyncio.create_task(heartbeat_loop())
    await message_loop()

if __name__ == "__main__":
    asyncio.run(main())
