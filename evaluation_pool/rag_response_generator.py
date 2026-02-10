"""
Shared RAG Response Generator Module
Centralizes RAG response generation for both RAGAS and Phoenix evaluators.
"""
import json
from typing import Dict, Any, List, Tuple
from sqlmodel import Session, select


def ensure_rag_responses_for_evaluation(
    datastore_id: int,
    chatbot_id: str,
    session: Session,
    llm_provider: str = None,
    llm_model: str = None,
    settings_id: int = None
) -> Tuple[List[Tuple[Any, Any]], Dict[str, Any]]:
    """
    Ensure RAG responses exist for all Q&A pairs in the datastore.
    Generates missing responses via the RAG client.
    
    Args:
        datastore_id: ID of the datastore
        chatbot_id: ID of the chatbot
        session: Database session
        llm_provider: LLM provider to use (optional, will use settings if not provided)
        llm_model: LLM model to use (optional, will use settings if not provided)
        settings_id: Settings ID to use (optional, will fetch latest if not provided)
        
    Returns:
        Tuple of (results_list, stats_dict)
        - results_list: List of (RAGResponse, QuestionAnswerV2) tuples
        - stats_dict: Dictionary with generation statistics
    """
    from database_models import QuestionAnswerV2, RAGResponse, ChatbotSettings
    from rag_client import RAGClient
    from config import CONFIG
    
    print(f"[INFO] Ensuring RAG Responses for chatbot {chatbot_id} on datastore {datastore_id}")
    
    # Get latest settings if not provided
    if settings_id is None:
        settings = session.exec(
            select(ChatbotSettings)
            .where(ChatbotSettings.chatbot_id == str(chatbot_id))
            .order_by(ChatbotSettings.id.desc())
        ).first()
        
        if settings:
            settings_id = settings.id
            if llm_provider is None:
                llm_provider = settings.llm_provider or CONFIG.get("evaluation_llm_provider", "groq")
            if llm_model is None:
                llm_model = settings.llm_model or CONFIG.get("evaluation_llm_model", "llama-3.3-70b-versatile")
            print(f"[INFO] Using ChatbotSettings (v{settings.id}): PROV={llm_provider}, MODEL={llm_model}")
        else:
            print(f"[WARN] No settings found for chatbot {chatbot_id}, using defaults")
            llm_provider = llm_provider or CONFIG.get("evaluation_llm_provider", "groq")
            llm_model = llm_model or CONFIG.get("evaluation_llm_model", "llama-3.3-70b-versatile")
    
    # Load all Q&A pairs for this datastore
    qnas = session.exec(
        select(QuestionAnswerV2).where(QuestionAnswerV2.datastore_id == datastore_id)
    ).all()
    
    if not qnas:
        raise ValueError(f"No Q&A pairs found for Datastore {datastore_id}. Generate Q&A first.")
    
    print(f"[INFO] Found {len(qnas)} Q&A pairs for datastore {datastore_id}")
    
    # Initialize RAG client
    rag_client = RAGClient(timeout=120)  # 2 min timeout for RAG
    
    # Track statistics
    stats = {
        "total_qnas": len(qnas),
        "existing_responses": 0,
        "generated_responses": 0,
        "failed_responses": 0
    }
    
    final_results = []
    
    for qna in qnas:
        # Check if RAGResponse already exists for THIS settings version
        rag_resp = session.exec(
            select(RAGResponse).where(
                RAGResponse.question_id == qna.question_id,
                RAGResponse.chatbot_id == str(chatbot_id),
                RAGResponse.settings_id == settings_id
            )
        ).first()
        
        if rag_resp:
            print(f"[INFO] RAG Response exists for Question ID {qna.question_id}")
            stats["existing_responses"] += 1
            final_results.append((rag_resp, qna))
            continue
        
        # Generate new response
        print(f"[INFO] Generating RAG Response for Question ID {qna.question_id}: {qna.question[:50]}...")
        try:
            resp_data = rag_client.get_rag_response(
                chatbot_id=str(chatbot_id),
                question=qna.question,
                datastore_id=datastore_id,
                llm_model_provider=llm_provider,
                llm_model_name=llm_model
            )
            
            if "error" in resp_data:
                print(f"[ERROR] Failed to generate RAG response: {resp_data['error']}")
                stats["failed_responses"] += 1
                continue
            
            # Save to DB
            rag_resp = RAGResponse(
                question_id=qna.question_id,
                chatbot_id=str(chatbot_id),
                user_query=qna.question,
                generated_answer=resp_data.get("generated_answer", ""),
                citations=resp_data.get("citations", "[]"),
                context_text=resp_data.get("context_text", "[]"),
                settings_id=settings_id
            )
            session.add(rag_resp)
            session.commit()
            session.refresh(rag_resp)
            
            print(f"[INFO] ✅ Successfully generated and saved RAG response for Question ID {qna.question_id}")
            stats["generated_responses"] += 1
            final_results.append((rag_resp, qna))
            
        except Exception as e:
            print(f"[ERROR] Exception during RAG generation for Question ID {qna.question_id}: {e}")
            import traceback
            traceback.print_exc()
            stats["failed_responses"] += 1
            continue
    
    if not final_results:
        raise ValueError(
            f"No RAG Responses available for Datastore {datastore_id}. "
            f"Generated: {stats['generated_responses']}, Failed: {stats['failed_responses']}"
        )
    
    print(f"[INFO] RAG Response Generation Complete:")
    print(f"  Total Q&As: {stats['total_qnas']}")
    print(f"  Existing: {stats['existing_responses']}")
    print(f"  Generated: {stats['generated_responses']}")
    print(f"  Failed: {stats['failed_responses']}")
    print(f"  Available for evaluation: {len(final_results)}")
    
    return final_results, stats
