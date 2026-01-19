from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from database import get_session
from models.datastore import ChatbotSettings
from rag_pipeline.Config.rag_config import RAG_CONFIG
from datetime import datetime

router = APIRouter()

@router.get("/settings/{chatbot_id}")
async def get_settings(chatbot_id: str, session: Session = Depends(get_session)):
    settings = session.exec(select(ChatbotSettings).where(ChatbotSettings.chatbot_id == chatbot_id)).first()
    
    if not settings:
        # Return defaults from Config as a flat dict
        return {
            "llm_model": RAG_CONFIG["default_llm_model"],
            "llm_provider": RAG_CONFIG["default_llm_provider"],
            "temperature": RAG_CONFIG["default_temperature"],
            "max_tokens": RAG_CONFIG["default_max_tokens"],
            "reranker_type": RAG_CONFIG["default_reranker_type"],
            "query_optimizer": RAG_CONFIG["default_query_rewriting_type"], # Correct mapping
            "guardrail_type": RAG_CONFIG["default_guardrail_type"],
            "embedding_model": RAG_CONFIG["default_embedding_model"],
            "vector_db": RAG_CONFIG["default_vector_db"]
        }
    return settings

@router.post("/settings/{chatbot_id}")
async def save_settings(chatbot_id: str, update_data: dict, session: Session = Depends(get_session)):
    settings = session.exec(select(ChatbotSettings).where(ChatbotSettings.chatbot_id == chatbot_id)).first()
    
    if not settings:
        settings = ChatbotSettings(chatbot_id=chatbot_id)
        session.add(settings)
    
    # Update fields
    # Map frontend keys to backend keys if necessary, or assume they align 
    # (Based on standard naming, they mostly align, ensuring key mapping)
    
    # Helper to safe set
    def safe_set(key, val):
        if val is not None:
             setattr(settings, key, val)

    safe_set("llm_model", update_data.get("llmModel") or update_data.get("llm_model"))
    safe_set("llm_provider", update_data.get("llmProvider") or update_data.get("llm_provider"))
    safe_set("temperature", update_data.get("temperature"))
    safe_set("max_tokens", update_data.get("tokenSize") or update_data.get("max_tokens"))
    safe_set("reranker_type", update_data.get("rerankerOption") or update_data.get("reranker_type"))
    safe_set("query_optimizer", update_data.get("optimizer") or update_data.get("query_optimizer"))
    safe_set("guardrail_type", update_data.get("guardrailOption") or update_data.get("guardrail_type"))
    safe_set("vector_db", update_data.get("vectorDb") or update_data.get("vector_db"))
    
    settings.updated_at = datetime.utcnow()
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    
    # --- Print Updated Settings ---
    print("\n" + "="*50)
    print(f"🔄 Chatbot {chatbot_id} Settings Updated")
    print("="*50)
    print(settings.model_dump_json(indent=4))
    print("="*50 + "\n")
    
    return settings
