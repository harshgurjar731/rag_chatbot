# routes/feedback.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from Services.feedback_service import record_feedback

router = APIRouter()

class FeedbackPayload(BaseModel):
    trace_id: str
    feedback: str

@router.post("/feedback")
def handle_feedback(payload: FeedbackPayload):
    try:
        record_feedback(payload.trace_id, payload.feedback)
        return {"status": "success", "message": "Feedback recorded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record feedback: {e}")