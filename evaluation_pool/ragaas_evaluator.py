"""
RAGAS Evaluator Module
Performs RAG evaluation using RAGAS metrics.
"""
import os
import json
import traceback
from pathlib import Path
from typing import List, Dict, Any


from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas import evaluate
from langchain_openai import ChatOpenAI
from datasets import Dataset
from config import CONFIG
from sentence_transformers import SentenceTransformer
from pathlib import Path
from typing import List, Dict, Any
import json
import pandas as pd
import numpy as np
from langchain_openai import AzureChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings

class AzureChatOpenAIWrapper(AzureChatOpenAI):
    """Wrapper to force n=1 for Azure OpenAI compatibility with Ragas."""
    def _generate(self, *args, **kwargs):
        if "n" in kwargs and kwargs["n"] > 1:
            print(f"[DEBUG] Intercepting n={kwargs['n']} and forcing n=1 for Azure compatibility.")
            kwargs["n"] = 1
        return super()._generate(*args, **kwargs)

    async def _agenerate(self, *args, **kwargs):
        if "n" in kwargs and kwargs["n"] > 1:
            print(f"[DEBUG] Intercepting async n={kwargs['n']} and forcing n=1 for Azure compatibility.")
            kwargs["n"] = 1
        return await super()._agenerate(*args, **kwargs)

    def generate(self, *args, **kwargs):
        if "n" in kwargs and kwargs["n"] > 1:
            kwargs["n"] = 1
        return super().generate(*args, **kwargs)

    async def agenerate(self, *args, **kwargs):
        if "n" in kwargs and kwargs["n"] > 1:
            kwargs["n"] = 1
        return await super().agenerate(*args, **kwargs)


def perform_ragaas_evaluation(
    datastore_id: int,
    datastore_name: str,
    metrics: List[str],
    session, # Passed from main.py
    chatbot_id: str = None  # Added chatbot_id
) -> Dict[str, Any]:
    """
    Perform RAGAS evaluation using:
      - Questions and ground truths from the database (QuestionAnswer)
      - Contexts (reference) and answers (response) from the database (RAGResponse)
    Returns results as a dictionary with per-metric outputs.
    """

    try:
        # -------------------- LLM + Embedding Setup --------------------
        # -------------------- Load Chatbot Settings --------------------
        # -------------------- Load Chatbot Settings --------------------
        from database_models import DataStore, RAGResponse, ChatbotSettings, QuestionAnswerV2 
        from sqlmodel import select
        from sqlmodel import select 
        
        # Default values
        llm_model = "llama-3.3-70b-versatile" # Default for evaluation if no settings
        llm_provider = "groq"
        temperature = 0.0

        latest_settings_id = None
        if chatbot_id:
            settings = session.exec(
                select(ChatbotSettings)
                .where(ChatbotSettings.chatbot_id == str(chatbot_id))
                .order_by(ChatbotSettings.id.desc())
            ).first()
            if settings:
                latest_settings_id = settings.id
                print(f"[INFO] Using ChatbotSettings (v{settings.id}) for Ragas Judge: PROV={settings.llm_provider}, MODEL={settings.llm_model}")
                llm_model = settings.llm_model or llm_model
                llm_provider = settings.llm_provider or llm_provider
                temperature = settings.temperature if settings.temperature is not None else temperature
            else:
                 print(f"[WARN] No settings found for chatbot {chatbot_id}, using defaults for Ragas.")

        # -------------------- Initialize LLM based on Settings --------------------
        token_size = 2048 
        
        if llm_provider == "azure-openai":
             # Load Azure Config
             azure_api_key = CONFIG.get("azure_api_key")
             azure_endpoint = CONFIG.get("azure_api_base")
             azure_api_version = CONFIG.get("azure_api_version", "2025-01-01-preview")
             
             if not azure_api_key or not azure_endpoint:
                 raise ValueError("Azure OpenAI credentials not configured. Please set AZURE_API_KEY and AZURE_API_BASE in .env")
             
             llm = AzureChatOpenAIWrapper(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version,
                azure_deployment=llm_model, # Use the model from settings as deployment name usually
                temperature=temperature,
                max_completion_tokens=token_size,
                n=1,
            )
        
        elif llm_provider == "groq":
             GROQ_API_KEY = CONFIG.get("groq_api_key")
             GROQ_API_BASE = CONFIG.get("groq_api_base")
             
             if not GROQ_API_KEY:
                 raise ValueError("Groq API key not configured. Please set GROQ_API_KEY in .env")
             
             llm = ChatOpenAI(
                openai_api_base=GROQ_API_BASE,
                openai_api_key=GROQ_API_KEY,
                model=llm_model,
                temperature=temperature,
                max_tokens=token_size,
                n=1,
             )
             
        else:
             # Default generic OpenAI or fallback
             raise ValueError(f"Unsupported LLM provider '{llm_provider}' for RAGAS evaluation. Supported: 'azure-openai', 'groq'")
        # embeddings = SentenceTransformer("BAAI/bge-small-en-v1.5")
        embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

        # -------------------- Load Datastore Info --------------------
        # Imports now handled in LLM setup block or at module level
        datastore = session.get(DataStore, datastore_id)
        if not datastore:
            raise ValueError(f"Datastore with ID {datastore_id} not found.")

        # -------------------- Load Data from DB (QuestionAnswer) --------------------
        qnas = session.exec(
            select(QuestionAnswerV2).where(QuestionAnswerV2.datastore_id == datastore_id)
        ).all()

        if not qnas:
            raise ValueError(f"No Q&A pairs found for Datastore {datastore_id}. Generate Q&A first.")

        # -------------------- Ensure RAG Responses exist --------------------
        from rag_client import RAGClient
        rag_client = RAGClient(timeout=120) # 2 min timeout for RAG
        
        print(f"[INFO] Checking for RAG Responses for chatbot {chatbot_id} on datastore {datastore_id}")
        
        final_results = []
        for qna in qnas:
            # Check if RAGResponse already exists for THIS settings version
            rag_resp = session.exec(
                select(RAGResponse).where(
                    RAGResponse.question_id == qna.question_id,
                    RAGResponse.chatbot_id == str(chatbot_id),
                    RAGResponse.settings_id == latest_settings_id
                )
            ).first()
            
            if not rag_resp:
                print(f"[INFO] RAG Response missing for Question ID {qna.question_id}. Generating...")
                try:
                    # Generate response via worker-pool
                    resp_data = rag_client.get_rag_response(
                        chatbot_id=str(chatbot_id),
                        question=qna.question,
                        datastore_id=datastore_id,
                        llm_model_provider=llm_provider,
                        llm_model_name=llm_model
                    )
                    
                    if "error" in resp_data:
                         print(f"[ERROR] Failed to generate RAG response: {resp_data['error']}")
                         continue
                         
                    # Save to DB
                    rag_resp = RAGResponse(
                        question_id=qna.question_id,
                        chatbot_id=str(chatbot_id),
                        user_query=qna.question,
                        generated_answer=resp_data.get("generated_answer", ""),
                        citations=resp_data.get("citations", "[]"),
                        context_text=resp_data.get("context_text", "[]"),
                        settings_id=latest_settings_id
                    )
                    session.add(rag_resp)
                    session.commit()
                    session.refresh(rag_resp)
                    print(f"[INFO] Successfully generated and saved RAG response for Question ID {qna.question_id}")
                    
                except Exception as e:
                    print(f"[ERROR] Exception during RAG generation for Question ID {qna.question_id}: {e}")
                    continue
            
            final_results.append((rag_resp, qna))

        if not final_results:
             raise ValueError(f"No RAG Responses found for Datastore {datastore_id} and generation failed.")

        results = final_results

        # -------------------- Combine DB Results into Ragas Rows --------------------
        ragas_rows = []
        for rag_resp, qna in results:
            question_text = qna.question.strip()
            answer_text = rag_resp.generated_answer.replace("\n", " ").strip() if rag_resp.generated_answer else ""
            ground_truth_text = qna.answer.replace("\n", " ").strip() if qna.answer else ""
            
            # Handle citations/contexts
            reference = rag_resp.citations
            context_raw = rag_resp.context_text
            contexts = []
            
            if context_raw and context_raw != "[]":
                try:
                    parsed = json.loads(context_raw)
                    if isinstance(parsed, list):
                        contexts = [str(ctx).strip() for ctx in parsed if ctx]
                    else:
                        contexts = [str(parsed).strip()]
                except json.JSONDecodeError:
                    contexts = [context_raw.strip()]
            elif reference:
                try:
                    # Fallback to citations if context_text is missing (old records)
                    parsed = json.loads(reference)
                    if isinstance(parsed, list):
                        contexts = [str(ctx).strip() for ctx in parsed if ctx]
                    else:
                        contexts = [str(parsed).replace("\n", " ").strip()]
                except json.JSONDecodeError:
                    contexts = [reference.replace("\n", " ").strip()]
            
            # Skip incomplete rows
            if not question_text or not answer_text or not contexts or not ground_truth_text:
                continue

            ragas_rows.append(
                {
                    "question": question_text,
                    "answer": answer_text,
                    "contexts": contexts,
                    "ground_truth": ground_truth_text,
                }
            )

        if not ragas_rows:
            raise ValueError("No valid rows found for RAGAS evaluation after filtering.")

        # -------------------- Prepare Dataset --------------------
        ds = Dataset.from_list(ragas_rows)

        # -------------------- Metric Mapping --------------------
        metric_map = {
            "faithfulness": faithfulness,
            "answer relevancy": answer_relevancy,
            "context precision": context_precision,
            "context recall": context_recall,
        }

        selected_metrics = [
            (name, metric_map[name.lower()])
            for name in metrics
            if name.lower() in metric_map
        ]

        if not selected_metrics:
            raise ValueError("No valid metrics found in request for RAGAS evaluation.")

        # -------------------- Run Evaluation --------------------
        print(f"[INFO] Running RAGAS evaluation for datastore {datastore_name} with metrics: {metrics}")
        metric_results = {}

        for metric_name, metric_obj in selected_metrics:
            try:
                # Explicitly assign the wrapper to each metric to ensure it uses the overridden generate methods
                metric_obj.llm = llm
                
                res = evaluate(ds, metrics=[metric_obj], llm=llm, embeddings=embeddings)
                df = res.to_pandas()

                # 🧹 Clean up invalid numbers for JSON serialization safely
                df.replace([np.inf, -np.inf], np.nan, inplace=True)
                df = df.apply(lambda col: col.map(lambda x: None if (isinstance(x, float) and np.isnan(x)) else x))

                # Convert safely to JSON-serializable dictionary
                # Use the EXACT metric name as requested (preserving original case for frontend match)
                metric_results[metric_name] = json.loads(df.to_json(orient="records"))
            except Exception as e:
                print(f"[WARN] Metric {metric_name} failed: {e}")
                metric_results[metric_name] = [{"error": str(e)}]


        return metric_results

    except FileNotFoundError as e:
        print(f"[ERROR] File not found: {e}")
        return {"error": str(e), "status": "failed"}

    except ValueError as e:
        print(f"[ERROR] Validation error: {e}")
        return {"error": str(e), "status": "failed"}

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decoding error: {e}")
        return {"error": "Invalid JSON file format.", "status": "failed"}

    except Exception as e:
        import traceback
        print(f"[ERROR] Unexpected error in perform_ragaas_evaluation: {e}")
        traceback.print_exc()
        return {"error": str(e), "status": "failed"}
