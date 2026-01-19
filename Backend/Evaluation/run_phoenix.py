from phoenix.evals import llm_classify, HALLUCINATION_PROMPT_TEMPLATE, HALLUCINATION_PROMPT_RAILS_MAP, MistralAIModel
from Evaluation.phoenix import *
from typing import List, Dict
from sqlmodel import Session, select
from models.FileRecord import QuestionAnswer
from rag_pipeline.Services.retrieve_service import retrieve_documents # ✅ Updated Import
from Evaluation.add_qna_into_db import insert_qna_for_datastore
import json
from pathlib import Path
import asyncio
import traceback # Added for debugging
from datetime import datetime
import os

# Force HuggingFace Offline Mode to prevent connection timeouts
os.environ["HF_HUB_OFFLINE"] = "1"

# List of fallback LLMs
# List of fallback LLMs with explicit provider
from models.datastore import ChatbotSettings
from config import CONFIG # Ensure CONFIG is available if needed, or RAG_CONFIG
from rag_pipeline.Config.rag_config import RAG_CONFIG

# Define fallback LLMs structure based on config
FALLBACK_LLMS = [
    ("gpt-4o-mini", "azure-openai") 
]

async def generate_qna_with_retrieval(datastore_id: int, session: Session, chatbot_id: str = None, output_file: str = None) -> list[dict]:
    # print(f"[DEBUG-TOP] Called generate_qna_with_retrieval. Datastore: {datastore_id}, ChatbotID: {chatbot_id}, OutputFile: {output_file}", flush=True)
    # ... (rest of the function start is same) ...
    insert_qna_for_datastore(session, datastore_id)

    print(f"[INFO] Fetching all QA pairs for datastore {datastore_id}")

    qas = session.exec(
        select(QuestionAnswer).where(QuestionAnswer.datastore_id == datastore_id)
    ).all()

    if not qas:
        return []
    
    # --- Fetch Chatbot Settings ---
    settings = None
    if chatbot_id:
        settings = session.exec(select(ChatbotSettings).where(ChatbotSettings.chatbot_id == chatbot_id)).first()
        if settings:
            print(f"[INFO] Using saved settings for chatbot {chatbot_id}: PROV={settings.llm_provider}, MODEL={settings.llm_model}, TEMP={settings.temperature}")
        else:
            print(f"[WARN] No settings found for chatbot {chatbot_id}, using defaults.")

    json_output = []
    existing_data = []

    # --- Load existing JSON file if it exists (Legacy Support / Ragas file-based interop) ---
    existing_queries = set()
    if output_file:
        output_path = Path(output_file)
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                    if isinstance(existing_data, dict):
                        existing_data = [existing_data]
                    elif not isinstance(existing_data, list):
                        existing_data = []
                    # print(f"[INFO] Loaded {len(existing_data)} records from {output_file}")
                except json.JSONDecodeError:
                    existing_data = []

    # Create a lookup set of existing queries (from file) to avoid duplicate entries in file export
    # NOTE: We still might regenerate if DB cache is stale, but this helps avoid appending duplicates to JSON on every run
    existing_queries = {item["query"] for item in existing_data if isinstance(item, dict) and "query" in item}

    from models.datastore import RAGResponse # Lazy import

    for row in qas:
        question = row.question
        # row.question_id is required for linking
        if not row.question_id:
            print(f"[WARN] Skipping question '{question}' (No ID)")
            continue

        cached_response = None
        needs_regeneration = True
        
        # 1. Check Cache
        # 1. Check Cache
        if chatbot_id:
            print(f"[DEBUG] Checking cache for QID: {row.question_id}, ChatbotID: {chatbot_id}", flush=True)
            cached_response = session.exec(
                select(RAGResponse).where(
                    RAGResponse.question_id == row.question_id,
                    RAGResponse.chatbot_id == chatbot_id
                )
            ).first()
            
            if cached_response and settings:
                cached_temp = cached_response.temperature if cached_response.temperature is not None else 0.0
                current_temp = settings.temperature if settings.temperature is not None else 0.0
                temp_match = abs(cached_temp - current_temp) < 0.01
                
                cached_model = cached_response.llm_model or ""
                current_model = settings.llm_model or ""
                
                cached_provider = cached_response.llm_provider or ""
                current_provider = settings.llm_provider or ""
                
                settings_match = (cached_model == current_model and 
                                  cached_provider == current_provider and 
                                  temp_match)
                
                if settings_match:
                    needs_regeneration = False
                    print(f"[CACHE HIT] Reusing answer for QID: {row.question_id}", flush=True)
                else:
                    print(f"[CACHE MISS] Settings Mismatch for QID: {row.question_id}. "
                          f"Cached:({cached_model}, {cached_provider}, {cached_temp}) "
                          f"vs Current:({current_model}, {current_provider}, {current_temp})", flush=True)
            elif cached_response and not settings:
                 needs_regeneration = True 
                 print(f"[CACHE MISS] No settings provided, regenerating for QID: {row.question_id}", flush=True)
            else:
                 print(f"[CACHE MISS] No cache found for QID: {row.question_id}, ChatbotID: {chatbot_id}", flush=True)
 

        # 2. Use Cache or Regenerate
        if not needs_regeneration and cached_response:
            retrieved_answer = cached_response.generated_answer
            citations = cached_response.citations # JSON string ideally
            llm_used = cached_response.llm_model
            # Reconstruct reference_text from citations if possible or just use what we have
            reference_text = citations # Simplified
            
        else:
            # print(f"[GENERATING] Processing Q: {question[:30]}...")
            llm_used = None
            retriever_output = None
    
            # Determine models to use (Settings > Fallback)
            models_to_try = []
            if settings and settings.llm_model and settings.llm_provider:
                 models_to_try.append((settings.llm_model, settings.llm_provider))
            
            models_to_try.extend(FALLBACK_LLMS)
    
            # Try retriever with fallback models
            for llm_model, provider in models_to_try:
                try:
                    retriever_output = await retrieve_documents(
                        query=question,
                        search_image=None,
                        message_history=[],
                        selected_documents=[], 
                        llm_model_name=llm_model,
                        llm_model_provider=provider,
                        datastore_id=datastore_id,
                        use_knowledge_base=True,
                        sources=True,
                        vector_db=settings.vector_db if settings and settings.vector_db and settings.vector_db.lower() in ["chroma", "qdrant"] else "Chroma"
                    )
                    llm_used = llm_model
                    break
                except Exception as e:
                    print(f"LLM '{llm_model}' failed: {str(e)}")
                    traceback.print_exc()
                    continue
    
            if retriever_output is None:
                reference_text = []
                retrieved_answer = "Error: Could not generate answer."
                citations_str = "[]"
            else:
                reference_text = retriever_output.get("retrieved_contexts", retriever_output.get("citations", "[]"))
                retrieved_answer = retriever_output.get("answer", "")
                citations_str = "\n\n".join(reference_text) if isinstance(reference_text, list) else str(reference_text)

            # 3. Save to Cache
            if chatbot_id:
                if cached_response:
                    # Update existing
                    cached_response.generated_answer = retrieved_answer
                    cached_response.citations = citations_str
                    cached_response.llm_model = settings.llm_model if settings else (llm_used or "Unknown")
                    cached_response.llm_provider = settings.llm_provider if settings else "Unknown"
                    cached_response.temperature = settings.temperature if settings else 0.0
                    cached_response.updated_at = datetime.utcnow()
                    session.add(cached_response)
                else:
                    # Create new
                    new_cache = RAGResponse(
                        question_id=row.question_id,
                        chatbot_id=chatbot_id,
                        generated_answer=retrieved_answer,
                        citations=citations_str,
                        llm_model=settings.llm_model if settings else (llm_used or "Unknown"),
                        llm_provider=settings.llm_provider if settings else "Unknown",
                        temperature=settings.temperature if settings else 0.0
                    )
                    session.add(new_cache)
                try:
                    session.commit()
                except Exception as db_err:
                     print(f"[WARN] Failed to cache RAG response: {db_err}")
            
            reference_text = citations_str # Alignment for JSON output

        # Prepare JSON Structure (Standardized for tools)
        # Avoid adding if it's already in 'existing_queries' AND we just reused cache (duplicate in file)
        # But if we regenerated, we might want to update the file entry.
        # For simplicity, we just append to json_output and let the file write handle overwrites or duplicates?
        # The prompt asked to "read values from there". 
        # Ideally, we should ignore 'existing_data' loading if we are fully DB driven now.
        # But for backward compat with Ragas/Phoenix file readers, we still produce the file.
        
        json_output.append({
            "reference": reference_text,
            "query": question,
            "response": retrieved_answer,
            "llm_used": llm_used,
            "retrieval_context": [reference_text] if isinstance(reference_text, str) else reference_text # Format helper
        })

    # --- Merge new and old results ---
    combined_data = existing_data + json_output

    # --- Print Generated Q&A Table ---
    if json_output:
        try:
            from tabulate import tabulate
            
            table_data = []
            headers = ["Question", "Generated Answer", "Context (Excerpt)"]
            
            for item in json_output:
                # Truncate context for display
                context_preview = item.get("reference", "")[:200] + "..." if len(item.get("reference", "")) > 200 else item.get("reference", "")
                answer_preview = item.get("response", "")[:200] + "..." if len(item.get("response", "")) > 200 else item.get("response", "")
                
                table_data.append([
                    item.get("query", ""),
                    answer_preview,
                    context_preview
                ])
                
            print("\n" + "="*50)
            print("🆕 NEWLY GENERATED Q&A PAIRS")
            print("="*50)
            print(tabulate(table_data, headers=headers, tablefmt="grid", maxcolwidths=[30, 40, 50]))
            print("="*50 + "\n")
            
        except ImportError:
            print("[WARN] 'tabulate' library not found. install it with 'pip install tabulate' for pretty printing.")
            # Fallback print
            for item in json_output:
                 print(f"Q: {item.get('query')}\nA: {item.get('response')}\n---\n")

    # --- Save to JSON if file specified ---
    if output_file:
        output_path = Path(output_file)
        # ✅ Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, indent=4, ensure_ascii=False)
        print(f"[INFO] QA JSON updated at {output_file}")

    return combined_data