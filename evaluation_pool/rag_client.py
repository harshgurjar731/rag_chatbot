import os
import json
import time
import uuid
import redis

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

class RAGClient:
    """
    Client for interacting with the worker-pool to get RAG responses.
    """
    
    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def get_rag_response(self, chatbot_id: str, question: str, datastore_id: int, 
                         llm_model_provider: str = None, llm_model_name: str = None) -> dict:
        """
        Sends a question to the worker-pool and waits for the response.
        """
        msg_id = str(uuid.uuid4())
        inbox_key = f"bot:{chatbot_id}:inbox"
        response_channel = f"msg:{msg_id}:stream"
        
        # Prepare job data
        job_data = {
            "id": msg_id,
            "query": question,
            "chatbot_id": chatbot_id,
            "datastore_id": datastore_id,
            "use_knowledge_base": True,
            "use_citation": True,
            "llm_model_provider": llm_model_provider,
            "llm_model_name": llm_model_name
        }
        
        print(f"[RAGClient] Sending question to {inbox_key}: {question[:50]}...")
        
        # Subscribe to response channel
        pubsub = r.pubsub()
        pubsub.subscribe(response_channel)
        
        # Push to inbox
        r.rpush(inbox_key, json.dumps(job_data))
        
        # Collect response
        full_answer = ""
        citations = []
        context_text = "[]"
        start_time = time.time()
        
        try:
            while time.time() - start_time < self.timeout:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    data = message['data']
                    if data == "__END__":
                        break
                    
                    try:
                        chunk = json.loads(data)
                        if isinstance(chunk, dict):
                            # The worker_wrapper sends the whole results_object
                            if "answer" in chunk:
                                full_answer = chunk["answer"]
                            if "citations" in chunk:
                                citations = chunk["citations"]
                            if "context_text" in chunk:
                                context_text = chunk["context_text"]
                            if "context" in chunk and not citations:
                                citations = chunk["context"]
                        else:
                            full_answer += str(data)
                    except json.JSONDecodeError:
                        full_answer += str(data)
                
                time.sleep(0.1)
            else:
                print(f"[RAGClient] Timeout waiting for response {msg_id}")
                return {"error": "Timeout", "generated_answer": "", "citations": "", "context_text": "[]"}
                
        finally:
            pubsub.unsubscribe(response_channel)
            pubsub.close()

        return {
            "generated_answer": full_answer,
            "citations": json.dumps(citations) if isinstance(citations, list) else str(citations),
            "context_text": context_text
        }
