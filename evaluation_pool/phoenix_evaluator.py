"""
Phoenix Evaluator Module
Performs RAG evaluation using Phoenix Evals framework with multiple metrics.
"""
from typing import List, Union, Optional
import pandas as pd
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from phoenix.evals import (
    HALLUCINATION_PROMPT_RAILS_MAP,
    HALLUCINATION_PROMPT_TEMPLATE,
    QA_PROMPT_RAILS_MAP,
    QA_PROMPT_TEMPLATE,
    RAG_RELEVANCY_PROMPT_RAILS_MAP,
    RAG_RELEVANCY_PROMPT_TEMPLATE,
    TOXICITY_PROMPT_RAILS_MAP,
    TOXICITY_PROMPT_TEMPLATE,
    llm_classify,
    OpenAIModel,
)
from config import CONFIG


# -----------------------------
# Pydantic models
# -----------------------------
class EvaluationRecord(BaseModel):
    reference: str
    query: str
    response: str


class EvaluationRequest(BaseModel):
    data: List[EvaluationRecord]
    provide_explanation: Optional[bool] = True


class EvaluationResult(BaseModel):
    reference: str
    query: str
    response: str
    context: str
    label: Optional[str] = "Unknown"
    explanation: Optional[str] = None


class EvaluationResponse(BaseModel):
    results: List[EvaluationResult]
    total_records: int
    model_used: str


# -----------------------------
# Initialize model (Groq by default, Azure supported)
# -----------------------------
def get_phoenix_model(provider: str = "groq", model_name: str = "llama-3.3-70b-versatile"):
    """
    Get Phoenix-compatible LLM model for evaluation.
    
    Args:
        provider: "groq" or "azure-openai"
        model_name: Model name to use
        
    Returns:
        OpenAIModel instance configured for the provider
    """
    if provider == "azure-openai":
        azure_api_key = CONFIG.get("azure_api_key")
        azure_endpoint = CONFIG.get("azure_api_base")
        azure_api_version = CONFIG.get("azure_api_version", "2024-02-15-preview")
        
        if not azure_api_key or not azure_endpoint:
            raise ValueError("Azure OpenAI credentials not configured. Please set AZURE_API_KEY and AZURE_API_BASE in .env")
        
        return OpenAIModel(
            model=model_name,
            api_key=azure_api_key,
            azure_endpoint=azure_endpoint,
            api_version=azure_api_version,
            temperature=0.0,
        )
    else:  # Default to Groq
        groq_api_key = CONFIG.get("groq_api_key")
        groq_api_base = CONFIG.get("groq_api_base")
        
        if not groq_api_key:
            raise ValueError("Groq API key not configured. Please set GROQ_API_KEY in .env")
        
        return OpenAIModel(
            model=model_name,
            api_key=groq_api_key,
            base_url=groq_api_base,
            temperature=0.0,
        )


# Default model instance (from CONFIG)
model = get_phoenix_model(
    provider=CONFIG.get("evaluation_llm_provider", "groq"),
    model_name=CONFIG.get("evaluation_llm_model", "llama-3.3-70b-versatile")
)



# -----------------------------
# Helper: JSON -> DataFrame
# -----------------------------
def json_to_dataframe(data: Union[List[dict], List[EvaluationRecord]]) -> pd.DataFrame:
    """
    Convert JSON / list of EvaluationRecord dicts into a Pandas DataFrame
    with columns: reference, input, output, context
    """
    df = pd.DataFrame(
        [
            {
                "reference": rec["reference"] if isinstance(rec, dict) else rec.reference,
                "input": rec["query"] if isinstance(rec, dict) else rec.query,
                "text": rec["query"] if isinstance(rec, dict) else rec.query,
                "output": rec["response"] if isinstance(rec, dict) else rec.response,
                "context": rec["reference"] if isinstance(rec, dict) else rec.reference,
            }
            for rec in data
        ]
    )
    return df


# -----------------------------
# Helper: Fetch directly from DB
# -----------------------------
def fetch_evaluation_data_from_db(session: Session, chatbot_id: str) -> pd.DataFrame:
    """
    Fetch RAGResponse records for a specific chatbot and convert to DataFrame for evaluation.
    """
    from database_models import RAGResponse, QuestionAnswerV2
    
    statement = select(RAGResponse, QuestionAnswerV2).where(
        RAGResponse.chatbot_id == str(chatbot_id),
        RAGResponse.question_id == QuestionAnswerV2.question_id
    )
    results = session.exec(statement).all()
    
    data = []
    for rag_resp, qna in results:
        # Use context_text (raw text) if available, otherwise fallback to citations (metadata)
        # Phoenix expects the retrieved text content for hallucination/relevancy checks.
        context_data = rag_resp.context_text
        if not context_data or context_data == "[]":
            context_data = rag_resp.citations

        data.append({
            "reference": context_data,
            "input": qna.question,
            "text": qna.question,
            "output": rag_resp.generated_answer,
            "context": context_data
        })
    
    if not data:
        return pd.DataFrame(columns=["reference", "input", "text", "output", "context"])
        
    return pd.DataFrame(data)


# -----------------------------
# Core evaluation functions
# -----------------------------
import time
import random

# --- Helper: Retry Logic ---
def run_with_retry(func, *args, max_retries=10, **kwargs):
    """
    Run a function with exponential backoff for RateLimitErrors.
    """
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Check for rate limit error (by type name or message string)
            error_type = type(e).__name__
            error_msg = str(e).lower()
            
            is_rate_limit = (
                "RateLimitError" in error_type 
                or "rate limit" in error_msg 
                or "429" in error_msg
                or "throttling" in error_msg
            )
            
            if is_rate_limit:
                if attempt == max_retries - 1:
                    print(f"[ERROR] Max retries ({max_retries}) exhausted for rate limit.")
                    raise e
                
                # Exponential backoff: 2s, 4s, 8s, 16s... + jitter
                wait_time = (2 ** (attempt + 1)) + random.uniform(0, 1)
                print(f"[WARN] Rate limited ({error_type}). Retrying in {wait_time:.2f}s (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                # Not a rate limit error, re-raise immediately
                raise e
def evaluate_records(
    request: Union[EvaluationRequest, dict, list] = None,
    metric: str = "hallucination",
    session: Session = None,
    chatbot_id: str = None
) -> EvaluationResponse:
    """
    Evaluate records for a given metric (hallucination, qna, rag_relevancy, toxicity).
    Returns structured Pydantic response.
    Prioritizes DB fetch if session and chatbot_id are provided.
    """
    # --- Normalize Metric Name ---
    original_metric = metric
    metric = metric.lower().replace(" ", "_")
    
    # Map synonyms/aliases
    if metric in ["answer_relevance", "answer_relevancy", "qa", "q&a"]:
        metric = "qna"
    elif metric in ["faithfulness", "groundedness"]:
        metric = "hallucination"
    elif metric in ["context_relevance", "context_relevancy", "relevancy"]:
        metric = "rag_relevancy"

    # --- Fetch Data (DB or Request) ---
    if session and chatbot_id:
        print(f"[INFO] Fetching evaluation data from DB for ChatbotID: {chatbot_id}")
        df = fetch_evaluation_data_from_db(session, chatbot_id)
        if df.empty:
            error_msg = (
                f"No RAG Responses found in DB for chatbot {chatbot_id}. "
                "RAG responses should have been generated before evaluation. "
                "This indicates a workflow issue - ensure RAG response generation "
                "completes successfully before running Phoenix evaluation."
            )
            print(f"[ERROR] {error_msg}")
            raise ValueError(error_msg)
        print(f"[INFO] Loaded {len(df)} RAG responses for evaluation")
        provide_explanation = True
    else:
        # Fallback to existing logic
        if not request:
            raise ValueError("Either (session, chatbot_id) or request data must be provided.")
             
        # --- Normalize input (only if request provided) ---
        if isinstance(request, dict):
            request_obj = EvaluationRequest(**request)
        elif isinstance(request, list):
            request_obj = EvaluationRequest(data=request)
        else:
            request_obj = request
            
        provide_explanation = request_obj.provide_explanation
        df = json_to_dataframe(request_obj.data)

    # --- Run evaluation based on selected metric ---
    if metric.lower() == "hallucination":
        classifications = run_with_retry(
            llm_classify,
            dataframe=df,
            template=HALLUCINATION_PROMPT_TEMPLATE,
            model=model,
            rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
            provide_explanation=provide_explanation,
        )
        df["hallucination_eval"] = classifications["label"]

    elif metric.lower() == "qna":
        classifications = run_with_retry(
            llm_classify,
            dataframe=df,
            template=QA_PROMPT_TEMPLATE,
            model=model,
            rails=list(QA_PROMPT_RAILS_MAP.values()),
            provide_explanation=provide_explanation,
        )
        df["qna_eval"] = classifications["label"]

    elif metric.lower() == "rag_relevancy":
        classifications = run_with_retry(
            llm_classify,
            dataframe=df,
            template=RAG_RELEVANCY_PROMPT_TEMPLATE,
            model=model,
            rails=list(RAG_RELEVANCY_PROMPT_RAILS_MAP.values()),
            provide_explanation=provide_explanation,
        )
        df["rag_relevancy_eval"] = classifications["label"]

    elif metric.lower() == "toxicity":
        classifications = run_with_retry(
            llm_classify,
            dataframe=df,
            template=TOXICITY_PROMPT_TEMPLATE,
            model=model,
            rails=list(TOXICITY_PROMPT_RAILS_MAP.values()),
            provide_explanation=provide_explanation,
        )
        df["toxicity_eval"] = classifications["label"]

    else:
        raise ValueError(f"Unsupported metric: {metric}")

    # --- Attach explanations if provided ---
    if isinstance(classifications, pd.DataFrame) and "explanation" in classifications.columns:
        df["explanation"] = classifications["explanation"]
    elif provide_explanation and isinstance(classifications, dict):
        df["explanation"] = classifications.get("explanation", "")

    # --- Build structured results ---
    results = []
    for _, row in df.iterrows():
        # Map specific eval column to generic label
        label = "Unknown"
        if metric == "hallucination":
            label = row.get("hallucination_eval")
        elif metric == "qna":
            label = row.get("qna_eval")
        elif metric == "rag_relevancy":
            label = row.get("rag_relevancy_eval")
        elif metric == "toxicity":
            label = row.get("toxicity_eval")
            
        results.append(
            EvaluationResult(
                reference=row.get("reference"),
                query=row.get("input") or row.get("query"),
                response=row.get("output") or row.get("response"),
                context=row.get("context"),
                label=label,
                explanation=row.get("explanation") if provide_explanation else None,
            )
        )

    return EvaluationResponse(
        results=results,
        total_records=len(results),
        model_used=model.model,
    )


def evaluate_records_as_dataframe(request: EvaluationRequest) -> pd.DataFrame:
    """
    Evaluate hallucinations and return a raw Pandas DataFrame.
    """
    df = json_to_dataframe(request.data)

    rails = list(HALLUCINATION_PROMPT_RAILS_MAP.values())
    classifications = llm_classify(
        dataframe=df,
        template=HALLUCINATION_PROMPT_TEMPLATE,
        model=model,
        rails=rails,
        provide_explanation=request.provide_explanation,
    )

    # Merge results
    if isinstance(classifications, pd.DataFrame):
        df["hallucination_eval"] = classifications["label"]
        if request.provide_explanation and "explanation" in classifications.columns:
            df["explanation"] = classifications["explanation"]
    else:
        df["hallucination_eval"] = classifications.get("label", "UNKNOWN")
        if request.provide_explanation:
            df["explanation"] = classifications.get("explanation", "")

    return df


def perform_phoenix_evaluation(
    datastore_id: int,
    datastore_name: str,
    metrics: List[str],
    session: Session,
    chatbot_id: str = None
) -> dict:
    """
    Perform Phoenix evaluation for multiple metrics.
    This is the main entry point called by evaluation_worker.py.
    
    Args:
        datastore_id: ID of the datastore
        datastore_name: Name of the datastore
        metrics: List of metrics to evaluate (hallucination, qna, rag_relevancy, toxicity)
        session: Database session
        chatbot_id: Chatbot ID for fetching RAG responses
        
    Returns:
        Dictionary with results for each metric
    """
    try:
        print(f"[INFO] Running Phoenix evaluation for datastore {datastore_name} with metrics: {metrics}")
        
        metric_results = {}
        
        for metric in metrics:
            try:
                print(f"[INFO] Evaluating metric: {metric}")
                result = evaluate_records(
                    metric=metric.lower(),
                    session=session,
                    chatbot_id=chatbot_id
                )
                
                # Convert to dict for JSON serialization
                metric_results[metric] = {
                    "results": [r.dict() for r in result.results],
                    "total_records": result.total_records,
                    "model_used": result.model_used
                }
                
            except Exception as e:
                print(f"[WARN] Metric {metric} failed: {e}")
                metric_results[metric] = {"error": str(e)}
        
        return metric_results
        
    except Exception as e:
        print(f"[ERROR] Phoenix evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "status": "failed"}
