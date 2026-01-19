from typing import List, Union
import pandas as pd
from sqlmodel import Session, select
from models.datastore import RAGResponse
from models.FileRecord import QuestionAnswer
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
    MistralAIModel,
)
from pydantic import BaseModel, Field
from typing import Optional
from config import CONFIG  # ✅ centralized config


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


# ... (skipping to evaluate_records loop)




# -----------------------------
# Initialize model
# -----------------------------
model = MistralAIModel(
    model="mistral-small-latest",
    api_key=CONFIG["mistral_api_key"],
    temperature=0.2,
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
# Core evaluation functions
# -----------------------------
from sqlmodel import Session, select
from models.datastore import RAGResponse
from models.FileRecord import QuestionAnswer

# ... (existing imports preserved by not overwriting them, but I must provide valid replacement block)
# I will overwrite the top imports section carefully or append.
# Since replace_file_content works on blocks, I'll targeting the `evaluate_records` area and adds the helper before it.
# Wait, I need imports at top. I'll do two edits or one large one.
# I'll do imports first.

# -----------------------------
# Helper: Fetch directly from DB
# -----------------------------
def fetch_evaluation_data_from_db(session: Session, chatbot_id: str) -> pd.DataFrame:
    """
    Fetch RAGResponse records for a specific chatbot and convert to DataFrame for evaluation.
    """
    statement = select(RAGResponse, QuestionAnswer).where(
        RAGResponse.chatbot_id == str(chatbot_id),
        RAGResponse.question_id == QuestionAnswer.question_id
    )
    results = session.exec(statement).all()
    
    data = []
    for rag_resp, qna in results:
        data.append({
            "reference": rag_resp.citations,
            "input": qna.question,
            "text": qna.question,
            "output": rag_resp.generated_answer,
            "context": rag_resp.citations
        })
    
    if not data:
        return pd.DataFrame(columns=["reference", "input", "text", "output", "context"])
        
    return pd.DataFrame(data)

# -----------------------------
# Core evaluation functions
# -----------------------------
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

    # --- Fetch Data (DB or Request) ---
    if session and chatbot_id:
        print(f"[INFO] Fetching evaluation data from DB for ChatbotID: {chatbot_id}")
        df = fetch_evaluation_data_from_db(session, chatbot_id)
        if df.empty:
             # Fallback or error?
             print("[WARN] No RAG Responses found in DB for this chatbot. Evaluation might be empty.")
             request_obj = EvaluationRequest(data=[]) # Empty
    else:
        # Fallback to existing logic
        if not request:
             raise ValueError("Either (session, chatbot_id) or request data must be provided.")
             
        # --- Normalize input ---
    # Determine explanation flag
    provide_explanation = True
    if not session or not chatbot_id:
        # --- Normalize input (only if request provided) ---
        if isinstance(request, dict):
            request_obj = EvaluationRequest(**request)
        elif isinstance(request, list):
            request_obj = EvaluationRequest(data=request)
        else:
            request_obj = request
            
        if request_obj:
            provide_explanation = request_obj.provide_explanation


    # --- Run evaluation based on selected metric ---
    if metric.lower() == "hallucination":
        classifications = llm_classify(
            dataframe=df,
            template=HALLUCINATION_PROMPT_TEMPLATE,
            model=model,
            rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
            provide_explanation=provide_explanation,
        )
        df["hallucination_eval"] = classifications["label"]

    elif metric.lower() == "qna":
        classifications = llm_classify(
            dataframe=df,
            template=QA_PROMPT_TEMPLATE,
            model=model,
            rails=list(QA_PROMPT_RAILS_MAP.values()),
            provide_explanation=provide_explanation,
        )
        df["qna_eval"] = classifications["label"]

    elif metric.lower() == "rag_relevancy":
        classifications = llm_classify(
            dataframe=df,
            template=RAG_RELEVANCY_PROMPT_TEMPLATE,
            model=model,
            rails=list(RAG_RELEVANCY_PROMPT_RAILS_MAP.values()),
            provide_explanation=provide_explanation,
        )
        df["rag_relevancy_eval"] = classifications["label"]

    elif metric.lower() == "toxicity":
        classifications = llm_classify(
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