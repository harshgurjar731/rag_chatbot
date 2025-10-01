from typing import List, Union
import pandas as pd
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
    input: str
    output: str
    context: str
    # Make this optional to handle metrics that don't use hallucination_eval
    hallucination_eval: Optional[str] = "Unknown"
    qna_eval: Optional[str] = "Unknown"
    rag_relevancy_eval: Optional[str] = "Unknown"
    toxicity_eval: Optional[str] = "Unknown"
    explanation: Optional[str] = None


class EvaluationResponse(BaseModel):
    results: List[EvaluationResult]
    total_records: int
    model_used: str


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
def evaluate_records(
    request: Union[EvaluationRequest, dict, list],
    metric: str
) -> EvaluationResponse:
    """
    Evaluate records for a given metric (hallucination, qna, rag_relevancy, toxicity).
    Returns structured Pydantic response.
    """

    # --- Normalize input ---
    if isinstance(request, dict):
        request_obj = EvaluationRequest(**request)
    elif isinstance(request, list):
        request_obj = EvaluationRequest(data=request)
    else:
        request_obj = request

    df = json_to_dataframe(request_obj.data)

    # --- Run evaluation based on selected metric ---
    if metric.lower() == "hallucination":
        classifications = llm_classify(
            dataframe=df,
            template=HALLUCINATION_PROMPT_TEMPLATE,
            model=model,
            rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
            provide_explanation=request_obj.provide_explanation,
        )
        df["hallucination_eval"] = classifications["label"]

    elif metric.lower() == "qna":
        classifications = llm_classify(
            dataframe=df,
            template=QA_PROMPT_TEMPLATE,
            model=model,
            rails=list(QA_PROMPT_RAILS_MAP.values()),
            provide_explanation=request_obj.provide_explanation,
        )
        df["qna_eval"] = classifications["label"]

    elif metric.lower() == "rag_relevancy":
        classifications = llm_classify(
            dataframe=df,
            template=RAG_RELEVANCY_PROMPT_TEMPLATE,
            model=model,
            rails=list(RAG_RELEVANCY_PROMPT_RAILS_MAP.values()),
            provide_explanation=request_obj.provide_explanation,
        )
        df["rag_relevancy_eval"] = classifications["label"]

    elif metric.lower() == "toxicity":
        classifications = llm_classify(
            dataframe=df,
            template=TOXICITY_PROMPT_TEMPLATE,
            model=model,
            rails=list(TOXICITY_PROMPT_RAILS_MAP.values()),
            provide_explanation=request_obj.provide_explanation,
        )
        df["toxicity_eval"] = classifications["label"]

    else:
        raise ValueError(f"Unsupported metric: {metric}")

    # --- Attach explanations if provided ---
    if isinstance(classifications, pd.DataFrame) and "explanation" in classifications.columns:
        df["explanation"] = classifications["explanation"]
    elif request_obj.provide_explanation and isinstance(classifications, dict):
        df["explanation"] = classifications.get("explanation", "")

    # --- Build structured results ---
    results = []
    for _, row in df.iterrows():
        results.append(
            EvaluationResult(
                reference=row.get("reference"),
                input=row.get("input"),
                output=row.get("output"),
                context=row.get("context"),
                hallucination_eval=row.get("hallucination_eval") if metric == "hallucination" else None,
                qna_eval=row.get("qna_eval") if metric == "qna" else None,
                rag_relevancy_eval=row.get("rag_relevancy_eval") if metric == "rag_relevancy" else None,
                toxicity_eval=row.get("toxicity_eval") if metric == "toxicity" else None,
                explanation=row.get("explanation") if request_obj.provide_explanation else None,
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
