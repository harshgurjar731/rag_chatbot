"""
Evaluation Router
Handles evaluation API endpoints - dispatches jobs to evaluation_pool via Redis.
"""
import os
import uuid
import json
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel
import redis

from database import get_session
from models.datastore import DataStore, ChatbotSettings
from models.FileRecord import QuestionAnswerV2
from models.EvaluationResult import EvaluationResult

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Queue names
EVALUATION_INBOX = "evaluation:inbox"
EVALUATION_STATUS_PREFIX = "evaluation:status:"

router = APIRouter()


# --- Pydantic Models ---

class QnaRequest(BaseModel):
    file_id: int
    question: str
    answer: str


class EvaluationRequest(BaseModel):
    datastore_id: int
    datastore_name: str
    framework: str = "ragaas"  # Supported: "ragaas", "ragas", "phoenix"
    metrics: List[str] = ["faithfulness", "answer_relevancy"]  # RAGAS: faithfulness, answer_relevancy, context_precision, context_recall | Phoenix: hallucination, qna, rag_relevancy, toxicity
    chatbot_id: str = None


class EvaluationResponse(BaseModel):
    evaluation_id: str
    status: str
    message: str


# --- Q&A Endpoints ---

@router.get("/datastore/{datastore_id}", response_model=List[QuestionAnswerV2])
def get_all_questions(datastore_id: int, session: Session = Depends(get_session)):
    """
    Get all Q&A pairs for a datastore.
    """
    qas = session.exec(
        select(QuestionAnswerV2).where(QuestionAnswerV2.datastore_id == datastore_id)
    ).all()

    if not qas:
        return []

    return qas


@router.post("/datastore/{datastore_id}/qna", status_code=status.HTTP_201_CREATED)
def add_qna_pair(
    datastore_id: int,
    request: QnaRequest,
    session: Session = Depends(get_session),
):
    """Add a new Q&A pair to a datastore."""
    # Check datastore exists
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    qa_entry = QuestionAnswerV2(
        question=request.question,
        answer=request.answer,
        datastore_id=datastore_id,
        # file_id=request.file_id  <-- V2 doesn't have file_id? Or I need to map it?
        # V2 has document_id. If request has file_id, I assume it corresponds to DocumentRecord ID = document_id.
        document_id=request.file_id,
        file_name="User Added" # Adding default for manually added Q&A
    )
    session.add(qa_entry)
    session.commit()
    session.refresh(qa_entry)

    return {
        "message": "Q&A pair added successfully",
        "question_id": qa_entry.question_id,
        "datastore_id": datastore_id
    }


@router.get("/datastore/qna/id")
def get_question_id(
    question: str,
    file_id: int,
    session: Session = Depends(get_session)
):
    """Get question_id from question text and document_id (file_id)."""
    qa = session.exec(
        select(QuestionAnswerV2)
        .where(QuestionAnswerV2.question == question)
        .where(QuestionAnswerV2.document_id == file_id)
    ).first()

    if not qa:
        raise HTTPException(status_code=404, detail="Question not found")

    return {"question_id": qa.question_id}


@router.delete("/datastore/qna/{question_id}", status_code=status.HTTP_200_OK)
def delete_question_by_id(question_id: int, session: Session = Depends(get_session)):
    """Delete a single Q&A entry by question_id."""
    qa_to_delete = session.get(QuestionAnswerV2, question_id)
    if not qa_to_delete:
        raise HTTPException(status_code=404, detail="Question not found")

    session.delete(qa_to_delete)
    session.commit()

    return {"message": f"Question with ID {question_id} deleted successfully"}


# --- Evaluation Endpoints ---

@router.post("/start-evaluation", response_model=EvaluationResponse)
def start_evaluation(
    req: EvaluationRequest,
    session: Session = Depends(get_session),
):
    """
    Start an evaluation asynchronously.
    Pushes a job to the evaluation_pool via Redis queue.
    """
    # Validate datastore
    datastore = session.get(DataStore, req.datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    evaluation_id = f"eval-{uuid.uuid4().hex[:8]}"
    framework = req.framework.lower()

    print(
        f"[INFO] Starting evaluation {evaluation_id} "
        f"for framework '{framework}' "
        f"on datastore '{req.datastore_name}' (ID: {req.datastore_id}) "
        f"with metrics {req.metrics}"
    )

    # Create job payload
    job_data = {
        "job_type": "run_evaluation",
        "evaluation_id": evaluation_id,
        "datastore_id": req.datastore_id,
        "datastore_name": req.datastore_name,
        "framework": framework,
        "metrics": req.metrics,
        "chatbot_id": req.chatbot_id,
    }

    # Push to Redis queue
    try:
        r.rpush(EVALUATION_INBOX, json.dumps(job_data))
        
        # Initialize status
        status_key = f"{EVALUATION_STATUS_PREFIX}{evaluation_id}"
        initial_status = {
            "evaluation_id": evaluation_id,
            "status": "pending",
            "progress": 0,
            "framework": framework,
            "metrics": req.metrics,
        }
        r.set(status_key, json.dumps(initial_status), ex=86400)
        
    except redis.ConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to queue evaluation: {str(e)}"
        )

    return EvaluationResponse(
        evaluation_id=evaluation_id,
        status="started",
        message=f"Evaluation for '{framework}' started. Poll /evaluation/evaluation-status/{evaluation_id} for updates."
    )


@router.get("/evaluation-status/{evaluation_id}")
def evaluation_status(evaluation_id: str):
    """Check progress and results of a running evaluation."""
    status_key = f"{EVALUATION_STATUS_PREFIX}{evaluation_id}"
    
    try:
        status_data = r.get(status_key)
        if not status_data:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        
        return json.loads(status_data)
        
    except redis.ConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to get evaluation status: {str(e)}"
        )


@router.get("/generate-qa/{datastore_id}")
def trigger_qa_generation(
    datastore_id: int,
    session: Session = Depends(get_session),
):
    """
    Trigger Q&A generation for a datastore.
    Pushes a job to the evaluation_pool via Redis queue.
    """
    # Validate datastore
    datastore = session.get(DataStore, datastore_id)
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    evaluation_id = f"qa-{uuid.uuid4().hex[:8]}"

    # Create job payload
    job_data = {
        "job_type": "generate_qa",
        "evaluation_id": evaluation_id,
        "datastore_id": datastore_id,
        "datastore_name": datastore.name,
    }

    # Push to Redis queue
    try:
        r.rpush(EVALUATION_INBOX, json.dumps(job_data))
        
        # Initialize status
        status_key = f"{EVALUATION_STATUS_PREFIX}{evaluation_id}"
        initial_status = {
            "evaluation_id": evaluation_id,
            "status": "pending",
            "progress": 0,
            "job_type": "generate_qa",
        }
        r.set(status_key, json.dumps(initial_status), ex=86400)
        
    except redis.ConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to queue QA generation: {str(e)}"
        )

    return {
        "evaluation_id": evaluation_id,
        "status": "started",
        "message": f"Q&A generation started. Poll /evaluation/evaluation-status/{evaluation_id} for updates."
    }


# --- Evaluation Results Endpoints ---

@router.get("/results/{evaluation_id}")
def get_evaluation_results(
    evaluation_id: str,
    session: Session = Depends(get_session),
):
    """
    Retrieve evaluation results by evaluation_id.
    Used by the History modal to load past results.
    """
    try:
        result = session.exec(
            select(EvaluationResult)
            .where(EvaluationResult.evaluation_id == evaluation_id)
        ).first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        
        return {
            "evaluation_id": result.evaluation_id,
            "datastore_id": result.datastore_id,
            "chatbot_id": result.chatbot_id,
            "framework": result.framework,
            "metrics": json.loads(result.metrics),
            "results": json.loads(result.results),
            "meta_info": json.loads(result.meta_info) if result.meta_info else {},
            "created_at": result.created_at.isoformat(),
            "execution_time_seconds": result.execution_time_seconds,
            "qa_count": result.qa_count,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve evaluation results: {str(e)}"
        )


@router.get("/history/{datastore_id}")
def get_evaluation_history(
    datastore_id: int,
    chatbot_id: str = None,
    session: Session = Depends(get_session),
):
    """
    Return the last 5 evaluation results per framework for a given datastore + chatbot.
    Response shape: { "ragas": [...], "phoenix": [...] }
    """
    try:
        query = (
            select(EvaluationResult)
            .where(EvaluationResult.datastore_id == datastore_id)
            .where(EvaluationResult.is_valid == True)
        )
        if chatbot_id:
            query = query.where(EvaluationResult.chatbot_id == chatbot_id)

        all_results = session.exec(
            query.order_by(EvaluationResult.created_at.desc())
        ).all()

        # Group by framework, keep last 5 per group
        grouped: Dict[str, list] = {}
        for result in all_results:
            fw = result.framework
            if fw not in grouped:
                grouped[fw] = []
            if len(grouped[fw]) < 5:
                grouped[fw].append({
                    "evaluation_id": result.evaluation_id,
                    "framework": fw,
                    "metrics": json.loads(result.metrics),
                    "created_at": result.created_at.isoformat(),
                    "qa_count": result.qa_count,
                    "execution_time_seconds": result.execution_time_seconds,
                })

        return grouped

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch evaluation history: {str(e)}"
        )


