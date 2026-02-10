"""
Evaluation Worker - Main Entry Point
Listens on Redis queue for evaluation jobs and processes them.
"""
import os
import json
import time
import redis
import traceback
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Queue names
EVALUATION_INBOX = "evaluation:inbox"
EVALUATION_STATUS_PREFIX = "evaluation:status:"

# DB Connection
from sqlmodel import create_engine, Session

DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "chatbot_db")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

engine = create_engine(DATABASE_URL)

print(f"[INFO] Evaluation Worker starting...")
print(f"[INFO] Redis: {REDIS_HOST}:{REDIS_PORT}")


def update_evaluation_status(evaluation_id: str, status: str, progress: int, results: dict = None, error: str = None, metrics: list = None, framework: str = None):
    """Update evaluation status in Redis, preserving existing metadata if needed."""
    status_key = f"{EVALUATION_STATUS_PREFIX}{evaluation_id}"
    
    # Try to fetch existing status to preserve metrics/framework
    existing_data = {}
    try:
        raw = r.get(status_key)
        if raw:
            existing_data = json.loads(raw)
    except:
        pass

    status_data = {
        "evaluation_id": evaluation_id,
        "status": status,
        "progress": progress,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "framework": framework or existing_data.get("framework"),
        "metrics": metrics or existing_data.get("metrics"),
    }
    
    if results:
        status_data["results"] = results
    if error:
        status_data["error"] = error
    
    r.set(status_key, json.dumps(status_data), ex=86400)  # 24 hour expiry
    print(f"[STATUS] {evaluation_id}: {status} ({progress}%)")


def process_generate_qa(job_data: dict):
    """Process Q&A generation job using synthetic-data-kit."""
    from qa_generator import generate_qa_for_datastore
    
    evaluation_id = job_data.get("evaluation_id")
    datastore_id = job_data.get("datastore_id")
    datastore_name = job_data.get("datastore_name")
    
    try:
        update_evaluation_status(evaluation_id, "generating_qa", 10)
        
        result = generate_qa_for_datastore(
            datastore_id=datastore_id,
            datastore_name=datastore_name
        )
        
        # Check if this was a direct generation job or part of evaluation
        if job_data.get("job_type") == "generate_qa":
            update_evaluation_status(evaluation_id, "completed", 100, results={"qa_count": result.get("count", 0)})
        else:
            update_evaluation_status(evaluation_id, "qa_generated", 50, results={"qa_count": result.get("count", 0)})
            
        return result
        
    except Exception as e:
        error_msg = f"QA generation failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        update_evaluation_status(evaluation_id, "failed", 0, error=error_msg)
        return None


def process_run_evaluation(job_data: dict):
    """Process evaluation job using RAGAS or Phoenix."""
    from ragaas_evaluator import perform_ragaas_evaluation
    from phoenix_evaluator import perform_phoenix_evaluation
    from rag_response_generator import ensure_rag_responses_for_evaluation
    
    evaluation_id = job_data.get("evaluation_id")
    datastore_id = job_data.get("datastore_id")
    datastore_name = job_data.get("datastore_name")
    chatbot_id = job_data.get("chatbot_id")
    framework = job_data.get("framework", "ragaas").lower()
    metrics = job_data.get("metrics", ["faithfulness", "answer_relevancy"])
    
    try:
        update_evaluation_status(evaluation_id, "initializing", 5)
        
        # First generate Q&A if needed
        update_evaluation_status(evaluation_id, "generating_qa", 15, metrics=metrics, framework=framework)
        qa_result = process_generate_qa(job_data)
        
        # CRITICAL: Ensure RAG responses exist BEFORE running any evaluation framework
        # This prevents Phoenix from failing due to missing responses
        update_evaluation_status(evaluation_id, "preparing_rag_responses", 40, metrics=metrics, framework=framework)
        print(f"[INFO] Ensuring RAG responses are available for evaluation...")
        
        with Session(engine) as session:
            try:
                rag_results, rag_stats = ensure_rag_responses_for_evaluation(
                    datastore_id=datastore_id,
                    chatbot_id=chatbot_id,
                    session=session
                )
                print(f"[INFO] RAG responses ready: {len(rag_results)} available")
            except Exception as e:
                error_msg = f"Failed to prepare RAG responses: {str(e)}"
                print(f"[ERROR] {error_msg}")
                raise ValueError(error_msg)
        
        update_evaluation_status(evaluation_id, "running_evaluation", 60, metrics=metrics, framework=framework)
        
        if framework == "ragaas" or framework == "ragas":
            with Session(engine) as session:
                results = perform_ragaas_evaluation(
                    datastore_id=datastore_id,
                    datastore_name=datastore_name,
                    metrics=metrics,
                    session=session,
                    chatbot_id=chatbot_id
                )
        elif framework == "phoenix":
            with Session(engine) as session:
                results = perform_phoenix_evaluation(
                    datastore_id=datastore_id,
                    datastore_name=datastore_name,
                    metrics=metrics,
                    session=session,
                    chatbot_id=chatbot_id
                )
        else:
            results = {"error": f"Unsupported framework: {framework}"}
        
        update_evaluation_status(evaluation_id, "completed", 100, results=results, metrics=metrics, framework=framework)
        return results
        
    except Exception as e:
        error_msg = f"Evaluation failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        update_evaluation_status(evaluation_id, "failed", 0, error=error_msg)
        return None


def process_job(job_data: dict):
    """Route job to appropriate handler."""
    job_type = job_data.get("job_type")
    evaluation_id = job_data.get("evaluation_id", "unknown")
    
    print(f"[JOB] Processing {job_type} for evaluation {evaluation_id}")
    
    if job_type == "generate_qa":
        return process_generate_qa(job_data)
    elif job_type == "run_evaluation":
        return process_run_evaluation(job_data)
    else:
        print(f"[WARN] Unknown job type: {job_type}")
        return None


def main_loop():
    """Main worker loop - listen for jobs on Redis queue."""
    print(f"[INFO] Listening on queue: {EVALUATION_INBOX}")
    
    while True:
        try:
            # Block waiting for job (timeout 1 second for graceful shutdown)
            result = r.blpop(EVALUATION_INBOX, timeout=1)
            
            if result is None:
                continue
            
            _, job_json = result
            job_data = json.loads(job_json)
            
            print(f"[INFO] Received job: {job_data.get('job_type')}")
            process_job(job_data)
            
        except redis.ConnectionError as e:
            print(f"[ERROR] Redis connection error: {e}")
            time.sleep(5)  # Wait before reconnecting
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid job JSON: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            traceback.print_exc()
            time.sleep(1)


if __name__ == "__main__":
    print("[INFO] Starting Evaluation Worker...")
    main_loop()
