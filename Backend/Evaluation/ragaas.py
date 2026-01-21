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


def perform_ragaas_evaluation(
    datastore_id: int,
    datastore_name: str,
    metrics: List[str],
    session,
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
        from models.datastore import DataStore, RAGResponse, ChatbotSettings 
        from models.FileRecord import QuestionAnswer # Added QuestionAnswer
        from sqlmodel import select 
        
        # Default values
        llm_model = "gpt-4o-mini" # Default for evaluation if no settings
        llm_provider = "azure-openai"
        temperature = 0.0

        if chatbot_id:
            settings = session.exec(select(ChatbotSettings).where(ChatbotSettings.chatbot_id == str(chatbot_id))).first()
            if settings:
                print(f"[INFO] Using ChatbotSettings for Ragas Judge: PROV={settings.llm_provider}, MODEL={settings.llm_model}")
                llm_model = settings.llm_model or llm_model
                llm_provider = settings.llm_provider or llm_provider
                temperature = settings.temperature if settings.temperature is not None else temperature
            else:
                 print(f"[WARN] No settings found for chatbot {chatbot_id}, using defaults for Ragas.")

        # -------------------- Initialize LLM based on Settings --------------------
        token_size = 2048 
        
        if llm_provider == "azure-openai":
             # Load Azure Config
             azure_api_key = CONFIG.get("azure_api_key") or "239wAP9aB98yqPnlsfsIJEyUhYLq7dW254TkygU4q7w7swGzqMhbJQQJ99BLACYeBjFXJ3w3AAABACOGJ103"
             azure_endpoint = CONFIG.get("azure_api_base") or "https://knowledgesynthesis.openai.azure.com/"
             azure_api_version = CONFIG.get("azure_api_version") or "2025-01-01-preview"
             
             llm = AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version,
                azure_deployment=llm_model, # Use the model from settings as deployment name usually
                temperature=temperature,
                max_completion_tokens=token_size,
            )
        
        elif llm_provider == "groq":
             GROQ_API_KEY = CONFIG.get("groq_api_key")
             GROQ_API_BASE = CONFIG.get("groq_api_base")
             
             llm = ChatOpenAI(
                openai_api_base=GROQ_API_BASE,
                openai_api_key=GROQ_API_KEY,
                model=llm_model,
                temperature=temperature,
                max_tokens=token_size,
             )
             
        else:
             # Default generic OpenAI or fallback
             print(f"[WARN] Provider '{llm_provider}' not explicitly handled in Ragas setup, defaulting to generic ChatOpenAI path or Azure fallback.")
             # Fallback to Azure if provider unknown, or try generic
             # For now, let's assume default behavior or error. 
             # Let's fallback to the hardcoded Azure keys if everything fails, to be safe.
             azure_api_key = "239wAP9aB98yqPnlsfsIJEyUhYLq7dW254TkygU4q7w7swGzqMhbJQQJ99BLACYeBjFXJ3w3AAABACOGJ103"
             azure_endpoint = "https://knowledgesynthesis.openai.azure.com/"
             llm = AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version="2025-01-01-preview",
                azure_deployment="gpt-4o-mini", 
                temperature=temperature,
            )




        # embeddings = SentenceTransformer("BAAI/bge-small-en-v1.5")
        embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

        # -------------------- Load Datastore Info --------------------
        # Imports now handled in LLM setup block or at module level
        datastore = session.get(DataStore, datastore_id)
        if not datastore:
            raise ValueError(f"Datastore with ID {datastore_id} not found.")

        # -------------------- Load Data from DB (RAGResponse + QuestionAnswer) --------------------
        print(f"[INFO] Fetching RAGAS evaluation data from DB using ChatbotID: {chatbot_id}")
        
        # Join RAGResponse with QuestionAnswer on question_id
        # Filter by chatbot_id if provided
        stmt = select(RAGResponse, QuestionAnswer).where(
            RAGResponse.question_id == QuestionAnswer.question_id,
            QuestionAnswer.datastore_id == datastore_id
        )
        if chatbot_id:
            stmt = stmt.where(RAGResponse.chatbot_id == str(chatbot_id))
            
        results = session.exec(stmt).all()

        if not results:
             raise ValueError(f"No RAG Responses found in DB for Datastore {datastore_id} and ChatbotID {chatbot_id}")

        # -------------------- Combine DB Results into Ragas Rows --------------------
        ragas_rows = []
        for rag_resp, qna in results:
            question_text = qna.question.strip()
            answer_text = rag_resp.generated_answer.replace("\n", " ").strip() if rag_resp.generated_answer else ""
            ground_truth_text = qna.answer.replace("\n", " ").strip() if qna.answer else ""
            
            # Handle citations/contexts
            reference = rag_resp.citations
            contexts = []
            
            if reference:
                try:
                    # Try interpreting as JSON list first
                    parsed = json.loads(reference)
                    if isinstance(parsed, list):
                        contexts = [str(ctx).strip() for ctx in parsed if ctx]
                    else:
                         contexts = [str(parsed).replace("\n", " ").strip()]
                except json.JSONDecodeError:
                    # Treat as simple string
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
                res = evaluate(ds, metrics=[metric_obj], llm=llm, embeddings=embeddings)
                df = res.to_pandas()

                # 🧹 Clean up invalid numbers for JSON serialization safely
                df.replace([np.inf, -np.inf], np.nan, inplace=True)
                df = df.apply(lambda col: col.map(lambda x: None if (isinstance(x, float) and np.isnan(x)) else x))

                # Convert safely to JSON-serializable dictionary
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