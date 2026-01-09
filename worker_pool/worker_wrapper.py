import os
import redis
import asyncio
import json
import uuid
from google import genai
from phoenix.otel import register

# Configuration
BOT_NAME = os.getenv("BOT_NAME", "default")
BOT_ID = os.getenv("BOT_ID", "-1")
DATASTORE_ID = os.getenv("DATASTORE_ID", "-1")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

# Redis Connection
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)


# OpenTelemetry
tracer_provider = register(
    project_name=BOT_NAME,
    auto_instrument=True,
    batch=False
)

async def process_message(message_data):
    """
    Process a single message and stream responses back via Redis PubSub.
    """
   chatbot_id = message_data.get('chatbot_id')
   use_knowledge_base = message_data.get('use_knowledge_base')
   llm_model_provider = message_data.get('llm_model_provider')
   llm_model_name = message_data.get('llm_model_name')
   temperature = message_data.get('temperature')
   max_token = message_data.get('max_token')
   use_reranker = message_data.get('use_reranker')
   reranker_type = message_data.get('reranker_type')
   query_rewriting_type = message_data.get('query_rewriting_type')
   use_guardrail = message_data.get('use_guardrail')
   guardrail_type = message_data.get('guardrail_type')
   use_citation = message_data.get('use_citation')
   datastore_id = message_data.get('datastore_id')
   query = message_data.get('query')
   is_vision_search = message_data.get('is_vision_search')
   session = message_data.get('session')
   select=message_data.get('select')
   DataStore=message_data.get('DataStore')
   retrieve_documents=message_data.get('retrieve_documents')


    msg_id = message_data.get('id')
    text = message_data.get('text')
    response_channel = f"msg:{msg_id}:stream"

    print(f"[*] Processing message {msg_id} for {BOT_NAME}: {text[:20]}...")

    # try:
    #     # Stream chunks
    #     response = client.models.generate_content_stream(
    #         model='gemini-2.0-flash-exp',
    #         contents=text
    #     )
        
    #     for chunk in response:
    #         if chunk.text:
    #             r.publish(response_channel, chunk.text)
        
    #     # Signal End
    #     r.publish(response_channel, "__END__")

    # except Exception as e:
    #     print(f"[!] Error generating content: {e}")
    #     r.publish(response_channel, f"Error: {str(e)}")
    #     r.publish(response_channel, "__END__")

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

    # Manually start a span since FastAPI instrumentation might be missing or incomplete
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("rag_query_handler") as span:
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
        )
        
        # Set attributes for Phoenix to display Input/Output
        span.set_attribute("input.value", query)
        if isinstance(results_object, dict):
            # Try to grab just the answer if possible, or dump the whole thing
            answer_content = results_object.get("answer", str(results_object))
            span.set_attribute("output.value", answer_content)
        else:
            span.set_attribute("output.value", str(results_object))

        # Get the traceId to send back to the frontend for the feedback feature.
        # current_span = trace.get_current_span() # Should be 'span'
        span_context = span.get_span_context()
        trace_id = ""
        span_id = ""
        if span_context.is_valid:
            trace_id = format(span_context.trace_id, '032x')
            span_id = format(span_context.span_id, '016x')
            print(f"✅ Successfully captured Phoenix trace_id: {trace_id}, span_id: {span_id}")
        else:
            # trace_id = str(uuid.uuid4())
            print(f"⚠️ WARNING: Could not find a valid span context. Using generated UUID as trace_id: {trace_id}")

        # return {"answer": final_answer, "traceId": trace_id,"citations": results_object.get("document_pages_dict", [])}
        if isinstance(results_object, dict):
            results_object["traceId"] = trace_id
            results_object["spanId"] = span_id # Sending spanId
        elif isinstance(results_object, str):
            # If it's just a string, we might need to change implementation of retrieve_documents or wrap it
            pass

        return results_object





async def heartbeat_loop():
    """Maintain Redis heartbeat to show bot is alive."""
    while True:
        try:
            # Heartbeat now includes PID so the pool manager can track it too if needed
            r.setex(f"bot:{BOT_NAME}:heartbeat", 10, f"alive:{os.getpid()}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[!] Heartbeat error: {e}")
            await asyncio.sleep(5)

async def message_loop():
    """Poll Redis list for new messages."""
    inbox_key = f"bot:{BOT_NAME}:inbox"
    print(f"[*] {BOT_NAME} listening on {inbox_key}")
    
    while True:
        try:
            # BLPOP blocks until a message is available
            # Returns (key, value) tuple
            result = r.blpop(inbox_key, timeout=1)
            
            if result:
                _, message_json = result
                message_data = json.loads(message_json)
                # Process in background task to not block heartbeat? 
                # For now, process sequentially to keep it simple, or use asyncio.create_task
                await process_message(message_data)
            else:
                await asyncio.sleep(0.1) # Yield control
                
        except Exception as e:
            print(f"[!] Message loop error: {e}")
            await asyncio.sleep(1)

async def main():
    print(f"[*] Bot process started: {BOT_NAME} (PID: {os.getpid()})")
    
    # Start heartbeat
    asyncio.create_task(heartbeat_loop())
    
    # Start message loop
    await message_loop()

if __name__ == "__main__":
    asyncio.run(main())
