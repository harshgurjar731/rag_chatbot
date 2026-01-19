from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from phoenix import Client
import os

router = APIRouter()

# Initialize Phoenix Client
# Using default endpoint http://127.0.0.1:6006 if not specified
client = Client()

class FeedbackRequest(BaseModel):
    trace_id: str
    feedback: str  # "thumbs_up" or "thumbs_down"

@router.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    try:
        if not request.trace_id:
            raise HTTPException(status_code=400, detail="Trace ID is required")

        # Map feedback to a score
        # 1.0 for Thumbs Up, -1.0 for Thumbs Down
        score = 1.0 if request.feedback == "thumbs_up" else -1.0
        
        # Log feedback using the Phoenix Client
        # Note: If trace_id is not found in Phoenix yet (async), this might warn or fail depending on settings.
        client.log_feedback(
            trace_id=request.trace_id,
            score=score,
            label="user_feedback",
        )
        
        return {"message": "Feedback submitted successfully", "score": score}
    except Exception as e:
        print(f"Error submitting feedback: {e}")
        # Return 500 but also details
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")
