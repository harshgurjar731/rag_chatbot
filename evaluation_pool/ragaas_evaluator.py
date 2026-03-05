"""
RAGAS Evaluator Module
Performs RAG evaluation using RAGAS metrics.
"""
import os
import json
import traceback
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict


from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
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
    def _strip_markdown(self, result):
        if result and result.generations:
            for generation in result.generations:
                # Handle both ChatResult (flat list) and LLMResult (nested list) structures
                if isinstance(generation, list):
                    for gen in generation:
                        self._clean_generation(gen)
                else:
                    self._clean_generation(generation)
        return result

    def _clean_generation(self, generation):
        # Strip markdown code blocks if present
        if not hasattr(generation, "text"):
            return
            
        text = generation.text.strip()
        if text.startswith("```json"):
            text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            generation.text = text.strip()
            if hasattr(generation, "message"):
                generation.message.content = generation.text
        elif text.startswith("```"):
            text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            generation.text = text.strip()
            if hasattr(generation, "message"):
                generation.message.content = generation.text

    def _generate(self, *args, **kwargs):
        if "n" in kwargs and kwargs["n"] > 1:
            # print(f"[DEBUG] Intercepting n={kwargs['n']} and forcing n=1 for Azure compatibility.")
            kwargs["n"] = 1
        result = super()._generate(*args, **kwargs)
        return self._strip_markdown(result)

    async def _agenerate(self, *args, **kwargs):
        if "n" in kwargs and kwargs["n"] > 1:
            # print(f"[DEBUG] Intercepting async n={kwargs['n']} and forcing n=1 for Azure compatibility.")
            kwargs["n"] = 1
        result = await super()._agenerate(*args, **kwargs)
        return self._strip_markdown(result)

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
        
        
        # Default values from CONFIG
        llm_model = CONFIG.get("evaluation_llm_model", "llama-3.3-70b-versatile")
        llm_provider = CONFIG.get("evaluation_llm_provider", "groq")
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
        
        if llm_provider == "azure-openai" or llm_provider == "azureopenai":
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
                max_retries=5,
                request_timeout=60.0,
            )
             llm = LangchainLLMWrapper(llm)
             
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
             llm = LangchainLLMWrapper(llm)
             
        else:
             # Default generic OpenAI or fallback
             raise ValueError(f"Unsupported LLM provider '{llm_provider}' for RAGAS evaluation. Supported: 'azure-openai', 'groq'")
        # embeddings = SentenceTransformer("BAAI/bge-small-en-v1.5")
        embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5"))

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
        from rag_response_generator import ensure_rag_responses_for_evaluation
        
        print(f"[INFO] Loading RAG Responses for chatbot {chatbot_id} on datastore {datastore_id}")
        
        # Use shared RAG response generator
        results, rag_stats = ensure_rag_responses_for_evaluation(
            datastore_id=datastore_id,
            chatbot_id=chatbot_id,
            session=session,
            llm_provider=llm_provider,
            llm_model=llm_model,
            settings_id=latest_settings_id
        )
        
        print(f"[INFO] Loaded {len(results)} RAG responses for evaluation")


        # -------------------- Combine DB Results into Ragas Rows --------------------
        ragas_rows = []
        skipped_reasons = defaultdict(int)
        
        for rag_resp, qna in results:
            question_text = qna.question.strip()
            answer_text = rag_resp.generated_answer.replace("\n", " ").strip() if rag_resp.generated_answer else ""
            ground_truth_text = qna.answer.replace("\n", " ").strip() if qna.answer else ""
            
            # Handle citations/contexts
            reference = rag_resp.citations
            context_raw = rag_resp.context_text
            contexts = []
            
            print(f"[DEBUG] Processing Question ID {qna.question_id}")
            print(f"[DEBUG]   context_raw: {repr(context_raw)}")
            print(f"[DEBUG]   reference (citations): {repr(reference)}")
            
            # Try to extract contexts from context_text first
            if context_raw and context_raw not in ["[]", "", None]:
                try:
                    parsed = json.loads(context_raw)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        contexts = [str(ctx).strip() for ctx in parsed if ctx and str(ctx).strip()]
                        print(f"[DEBUG]   Parsed {len(contexts)} contexts from context_text")
                    elif parsed:  # Non-empty non-list
                        ctx_str = str(parsed).strip()
                        if ctx_str:
                            contexts = [ctx_str]
                            print(f"[DEBUG]   Using single context from context_text")
                except json.JSONDecodeError:
                    ctx_str = context_raw.strip()
                    if ctx_str:
                        contexts = [ctx_str]
                        print(f"[DEBUG]   Using raw context_text as single context")
            
            # Fallback to citations if context_text didn't yield results
            if not contexts and reference and reference not in ["[]", "", None]:
                try:
                    parsed = json.loads(reference)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        # Citations are usually [{"source": "...", "page_number": "..."}]
                        # Extract source info as context fallback
                        contexts = [
                            f"Source: {item.get('source', 'Unknown')}, Page: {item.get('page_number', 'N/A')}"
                            for item in parsed
                            if isinstance(item, dict)
                        ]
                        if contexts:
                            print(f"[DEBUG]   Extracted {len(contexts)} citation-based contexts")
                    elif parsed:
                        ctx_str = str(parsed).replace("\n", " ").strip()
                        if ctx_str:
                            contexts = [ctx_str]
                            print(f"[DEBUG]   Using single context from citations")
                except json.JSONDecodeError:
                    ctx_str = reference.replace("\n", " ").strip()
                    if ctx_str:
                        contexts = [ctx_str]
                        print(f"[DEBUG]   Using raw citations as single context")
            
            print(f"[DEBUG]   Final contexts: {len(contexts)} items")
            print(f"[DEBUG]   question_text: {'OK' if question_text else 'EMPTY'}")
            print(f"[DEBUG]   answer_text: {'OK' if answer_text else 'EMPTY'}")
            print(f"[DEBUG]   ground_truth_text: {'OK' if ground_truth_text else 'EMPTY'}")
            
            # Track why rows are skipped
            skip_reason = None
            if not question_text:
                skip_reason = "missing_question"
            elif not answer_text:
                skip_reason = "missing_answer"
            elif not ground_truth_text:
                skip_reason = "missing_ground_truth"
            elif not contexts:
                skip_reason = "missing_contexts"
            
            if skip_reason:
                skipped_reasons[skip_reason] += 1
                print(f"[DEBUG]   ❌ SKIPPING row - reason: {skip_reason}")
                continue
            
            print(f"[DEBUG]   ✅ ADDING row to ragas_rows")
            ragas_rows.append(
                {
                    "question": question_text,
                    "answer": answer_text,
                    "contexts": contexts,
                    "ground_truth": ground_truth_text,
                }
            )

        if not ragas_rows:
            skip_summary = ", ".join([f"{reason}: {count}" for reason, count in skipped_reasons.items()])
            error_msg = f"No valid rows found for RAGAS evaluation after filtering. Skipped {sum(skipped_reasons.values())} rows: {skip_summary}"
            raise ValueError(error_msg)

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
                # Assign wrapped LLM directly to metric so ragas uses it internally
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
