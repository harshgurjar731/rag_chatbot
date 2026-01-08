# rag_app/backend/routes/datastore.py
import os
import time
import uuid
from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from pydantic import BaseModel

from database import get_session
from models.datastore import DataStore
from models.FileRecord import QuestionAnswer
from config import CONFIG  # ✅ centralized config
# from Evaluation.add_qna_into_db import insert_qna_for_datastore, insert_qna
# from Evaluation.run_phoenix import generate_qna_with_retrieval
# from Evaluation.phoenix import evaluate_records
# from Evaluation.ragaas import perform_ragaas_evaluation  # If you have ragaas module

# If you have other framework modules (like ragas)
# from Evaluation.run_ragaas import run_ragaas_evaluation  # placeholder for future
# NOTE: ensure this import matches your actual ragaas evaluation file

router = APIRouter()

@router.get("/datastore/{datastore_id}", response_model=List[QuestionAnswer])
def get_all_questions(datastore_id: int, session: Session = Depends(get_session)):
    """
    Ensure QA is generated for all files if missing, then return all QA pairs for the datastore.
    """
    insert_qna_for_datastore(session, datastore_id)

    qas = session.exec(
        select(QuestionAnswer).where(QuestionAnswer.datastore_id == datastore_id)
    ).all()

    if not qas:
        raise HTTPException(status_code=404, detail="No QuestionAnswer found for this datastore")

    return qas

# Pydantic schema for request
class QnaRequest(BaseModel):
    file_id: int
    question: str
    answer: str

@router.post("/datastore/{datastore_id}/qna", status_code=status.HTTP_201_CREATED)
def add_qna_pair(
    datastore_id: int,
    request: QnaRequest,
    session: Session = Depends(get_session),
):
    # Check datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    # Prepare QnA JSON in the format insert_qna expects
    qna_json = {
        "qa_pairs": [
            {"question": request.question, "answer": request.answer}
        ]
    }

    try:
        inserted_count = insert_qna(
            session=session,
            datastore_id=datastore_id,
            qna_json=qna_json,
            file_id=request.file_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if inserted_count == 0:
        raise HTTPException(status_code=400, detail="No valid Q&A pairs inserted")

    return {
        "message": "Q&A pair added successfully",
        "inserted_count": inserted_count,
        "file_id": request.file_id,
        "datastore_id": datastore_id
    }


@router.delete("/datastore/qna/{question_id}", status_code=status.HTTP_200_OK)
def delete_question_by_id(question_id: int, session: Session = Depends(get_session)):
    """
    Delete a single QuestionAnswer entry by question_id.
    """
    qa_to_delete = session.get(QuestionAnswer, question_id)
    if not qa_to_delete:
        raise HTTPException(status_code=404, detail="Question not found")

    session.delete(qa_to_delete)
    session.commit()

    return {"message": f"Question with ID {question_id} deleted successfully"}

@router.get("/datastore/qna/id")
def get_question_id(file_id: int, question: str, session: Session = Depends(get_session)):
    """
    Get the question_id of a QA pair based on file_id and question text.
    """
    statement = select(QuestionAnswer).where(
        QuestionAnswer.file_id == file_id,
        QuestionAnswer.question == question
    )
    qa_record = session.exec(statement).first()

    if not qa_record:
        raise HTTPException(status_code=404, detail="Question not found for this file")

    return {"question_id": qa_record.question_id}


# --- In-memory evaluation tracker ---
evaluations: Dict[str, Dict] = {}

# --- Pydantic Models ---
class QnaRequest(BaseModel):
    file_id: int
    question: str
    answer: str


class EvaluationRequest(BaseModel):
    datastore_id: int
    datastore_name: str
    framework: str
    metrics: List[str]


class EvaluationResponse(BaseModel):
    result: dict
    status: str
    message: str
    evaluation_id: str


# --- Metric mapping ---
METRIC_MAP = {
    "Hallucination": "hallucination",
    "Faithfulness": "hallucination",
    "Answer Relevance": "qna",
    "RAG Relevancy": "rag_relevancy",
    "Toxicity": "toxicity",
}


# --- Utility: Run Phoenix Evaluation ---
def run_phoenix_evaluation(evaluation_id: str, req: EvaluationRequest, session: Session):
    """Dedicated runner for Phoenix framework."""
    try:
        evaluations[evaluation_id]["status"] = "initializing"
        evaluations[evaluation_id]["progress"] = 5

        insert_qna_for_datastore(session, req.datastore_id)
        time.sleep(1)

        evaluations[evaluation_id]["status"] = "fetching_data"
        evaluations[evaluation_id]["progress"] = 25

        # Generate QAs
        json_qas = generate_qna_with_retrieval(
            datastore_id=req.datastore_id,
            session=session,
            output_file=str(
                CONFIG["project_root"]
                / "Data"
                / req.datastore_name
                / f"{req.datastore_name}_evaluation_qa.json"
            ),
        )

        evaluations[evaluation_id]["status"] = "qa_generated"
        evaluations[evaluation_id]["progress"] = 50

        # Run metric evaluations
        metric_results = {}
        evaluations[evaluation_id]["status"] = "running_evaluation"
        evaluations[evaluation_id]["progress"] = 60

        for metric in req.metrics:
            internal_metric = METRIC_MAP.get(metric)
            if not internal_metric:
                print(f"[WARN] Unsupported metric: {metric}, skipping...")
                continue

            try:
                print(f"[INFO] Evaluating {metric} ({internal_metric})")
                result = evaluate_records(json_qas, metric=internal_metric)
                metric_results[metric] = result.dict()
            except Exception as metric_err:
                print(f"[ERROR] {metric} evaluation failed: {metric_err}")
                metric_results[metric] = {"error": str(metric_err)}

        evaluations[evaluation_id]["results"] = metric_results
        evaluations[evaluation_id]["progress"] = 100
        evaluations[evaluation_id]["status"] = "completed"

    except Exception as e:
        evaluations[evaluation_id]["status"] = "failed"
        evaluations[evaluation_id]["progress"] = 0
        print(f"[ERROR] Phoenix evaluation failed: {e}")


def run_ragaas_evaluation_wrapper(evaluation_id: str, req: EvaluationRequest, session: Session) -> EvaluationResponse:
    """
    Wrapper for executing RAGAS evaluation safely with progress tracking.
    """
    try:
        print(f"[INFO] Starting RAGAS evaluation for ID: {evaluation_id}")
        evaluations[evaluation_id]["status"] = "initializing"
        evaluations[evaluation_id]["progress"] = 5

        insert_qna_for_datastore(session, req.datastore_id)
        time.sleep(1)

        evaluations[evaluation_id]["status"] = "fetching_data"
        evaluations[evaluation_id]["progress"] = 25

        # Generate QAs
        json_qas = generate_qna_with_retrieval(
            datastore_id=req.datastore_id,
            session=session,
            output_file=str(
                CONFIG["project_root"]
                / "Data"
                / req.datastore_name
                / f"{req.datastore_name}_evaluation_qa.json"
            ),
        )

        evaluations[evaluation_id]["status"] = "qa_generated"
        evaluations[evaluation_id]["progress"] = 50
        time.sleep(3)
        # Run metric evaluations
        metric_results = {}
        evaluations[evaluation_id]["status"] = "running_evaluation"
        evaluations[evaluation_id]["progress"] = 60

        # Perform evaluation
        results = perform_ragaas_evaluation(
            datastore_id=req.datastore_id,
            metrics=req.metrics,
            session=session
        )

        evaluations[evaluation_id]["results"] = results
        evaluations[evaluation_id]["status"] = "completed"
        evaluations[evaluation_id]["progress"] = 100

        return EvaluationResponse(
            result={"data": results},
            status="success",
            message=f"RAGAS evaluation {evaluation_id} completed successfully.",
            evaluation_id=evaluation_id
        )

    except Exception as e:
        error_message = f"RAGAS evaluation failed: {str(e)}"
        print(f"[ERROR] {error_message}")
        evaluations[evaluation_id] = {
            "status": "failed",
            "progress": 0,
            "results": {"error": str(e)},
        }
        return EvaluationResponse(
            result={"error": str(e)},
            status="failed",
            message=error_message,
            evaluation_id=evaluation_id
        )


# --- Dynamic Framework Dispatcher ---
def dispatch_framework_evaluation(evaluation_id: str, req: EvaluationRequest, session: Session):
    """Select and run framework evaluation dynamically based on config."""
    framework = req.framework.lower()
    # supported_frameworks = CONFIG.get("frameworks", ["phoenix", "ragaas"])

    # if framework not in supported_frameworks:
    #     raise HTTPException(
    #         status_code=400,
    #         detail=f"Unsupported framework '{framework}'. Supported: {supported_frameworks}",
    #     )

    if framework == "phoenix":
        run_phoenix_evaluation(evaluation_id, req, session)
    elif framework == "ragaas":
        run_ragaas_evaluation_wrapper(evaluation_id, req, session)
    else:
        raise HTTPException(status_code=400, detail=f"No evaluation handler for '{framework}'.")


# --- API Routes ---

@router.post("/start-evaluation")
def start_evaluation(
    req: EvaluationRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Start an evaluation asynchronously and return an evaluation_id.
    Framework is read from request body and handled dynamically.
    """
    evaluation_id = f"eval-{uuid.uuid4().hex[:8]}"
    framework = req.framework.lower()

    print(
        f"[INFO] Starting evaluation {evaluation_id} "
        f"for framework '{framework}' "
        f"on datastore '{req.datastore_name}' (ID: {req.datastore_id}) "
        f"with metrics {req.metrics}"
    )

    # Initialize state
    evaluations[evaluation_id] = {
        "framework": framework,
        "metrics": req.metrics,
        "status": "pending",
        "progress": 0,
        "results": None,
    }

    # Run appropriate evaluation in background
    background_tasks.add_task(dispatch_framework_evaluation, evaluation_id, req, session)

    return {
        "evaluation_id": evaluation_id,
        "status": "started",
        "framework": framework,
        "message": f"Evaluation for '{framework}' started. Poll /evaluation-status/{evaluation_id} for updates.",
    }


@router.get("/evaluation-status/{evaluation_id}")
def evaluation_status(evaluation_id: str):
    """Check progress and results of a running evaluation."""
    evaluation = evaluations.get(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return {
        "evaluation_id": evaluation_id,
        "framework": evaluation["framework"],
        "status": evaluation["status"],
        "progress": evaluation["progress"],
        "metrics": evaluation["metrics"],
        "results": evaluation.get("results"),
    }
