"""
Bot Communication Module

Provides communication functionality for chatbot workers via Redis.
Handles bot discovery (heartbeats) and messaging (Redis PubSub).
"""

import redis
import json
import uuid
import time
from typing import List, Optional, Tuple, Dict, Any, Iterator

class BotCommunicator:
    """
    Manages communication with chatbot workers using Redis.
    """
    
    def __init__(self, redis_host: str = "redis", redis_port: int = 6379, db_manager=None):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True
        )
        self.db_manager = db_manager

    def discover_active_bots(self) -> List[str]:
        """
        Discover all active bots by checking for heartbeat keys.
        """
        try:
            heartbeat_keys = self.redis_client.keys("bot:*:heartbeat")
            bot_names = [key.split(":")[1] for key in heartbeat_keys]
            return sorted(bot_names)
        except Exception as e:
            print(f"Error discovering bots: {e}")
            return []

    def is_bot_alive(self, bot_name: str) -> bool:
        try:
            return self.redis_client.exists(f"bot:{bot_name}:heartbeat") > 0
        except Exception as e:
            return False

    def send_message_streaming(
        self,
        bot_name: str,
        message_text: str,
        timeout: int = 60,
        use_knowledge_base: bool = True,
        llm_model_provider: str = "openai",
        llm_model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_token: int = 8192,
        use_reranker: bool = False,
        reranker_type: str = "default",
        query_rewriting_type: str = "default",
        use_guardrail: bool = False,
        guardrail_type: str = "default",
        use_citation: bool = False,
        datastore_id: str = "",
        query: str = "",
        is_vision_search: bool = False,
        messages: List[Dict[str, Any]] = [],
        selected_documents: List[str] = []
    ) -> Iterator[str]:
        """
        Send a message to a bot and get a streaming response via Redis PubSub.
        """
        msg_id = str(uuid.uuid4())
        response_channel = f"msg:{msg_id}:stream"
        inbox_key = f"bot:{bot_name}:inbox"
        
        # Subscribe first
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(response_channel)
        
        # Send message
        payload = {
            "id": msg_id,
            "text": message_text,
            "chatbot_id": bot_name,
            "use_knowledge_base": use_knowledge_base,
            "llm_model_provider": llm_model_provider,
            "llm_model_name": llm_model_name,
            "temperature": temperature,
            "max_token": max_token,
            "use_reranker": use_reranker,
            "reranker_type": reranker_type,
            "query_rewriting_type": query_rewriting_type,
            "use_guardrail": use_guardrail,
            "guardrail_type": guardrail_type,
            "use_citation": use_citation,
            "datastore_id": datastore_id,
            "query": query,
            "is_vision_search": is_vision_search,
            "messages": messages,
            "selected_documents": selected_documents
        }
       
        try:
            self.redis_client.rpush(inbox_key, json.dumps(payload))
            
            # Read stream
            start_time = time.time()
            for message in pubsub.listen():
                
                if timeout > 0 and (time.time() - start_time) > timeout:
                    print("e")
                    yield "Error: Timeout waiting for response"
                    break
                
                if message["type"] == "message":
                    
                    data = message["data"]
                    if data == "__END__":
                        
                        break
                    yield data
            
        except Exception as e:
            yield f"Error: {str(e)}"
        finally:
            print("j")
            pubsub.unsubscribe()
            self.redis_client.delete(response_channel) # Cleanup (optional, channels aren't stored keys)

    def cleanup_bot_data(self, bot_name: str) -> Tuple[bool, str]:
        try:
            self.redis_client.delete(f"bot:{bot_name}:heartbeat")
            self.redis_client.delete(f"bot:{bot_name}:inbox")
            return True, f"Cleaned up data for bot '{bot_name}'"
        except Exception as e:
            return False, f"Error cleaning up bot data: {e}"

    def send_message(
        self,
        bot_name: str,
        message_text: str,
        timeout: int = 60,
        use_knowledge_base: bool = True,
        llm_model_provider: str = "openai",
        llm_model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_token: int = 8192,
        use_reranker: bool = False,
        reranker_type: str = "default",
        query_rewriting_type: str = "default",
        use_guardrail: bool = False,
        guardrail_type: str = "default",
        use_citation: bool = False,
        datastore_id: str = "",
        query: str = "",
        is_vision_search: bool = False,
        messages: List[Dict[str, Any]] = [],
        selected_documents: List[str] = []
    ) -> str:
        """
        Send a message to a bot and get a complete response via Redis PubSub.
        """
        full_response = []
        try:
            for chunk in self.send_message_streaming(
                bot_name=bot_name,
                message_text=message_text,
                timeout=timeout,
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
                messages=messages,
                selected_documents=selected_documents
            ):
                full_response.append(chunk)
            return "".join(full_response)
        except Exception as e:
            return f"Error: {str(e)}"