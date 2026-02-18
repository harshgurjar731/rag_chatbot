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
    from database_models import EvaluationResult, ChatbotSettings
    from sqlmodel import select
    import time
    
    evaluation_id = job_data.get("evaluation_id")
    datastore_id = job_data.get("datastore_id")
    datastore_name = job_data.get("datastore_name")
    chatbot_id = job_data.get("chatbot_id")
    framework = job_data.get("framework", "ragaas").lower()
    metrics = job_data.get("metrics", ["faithfulness", "answer_relevancy"])
    force_rerun = job_data.get("force_rerun", False)
    
    try:
        update_evaluation_status(evaluation_id, "initializing", 5)
        
        # Check for cached results unless force_rerun is True
        if not force_rerun:
            with Session(engine) as session:
                # Get the latest chatbot settings if chatbot_id provided
                settings_id = None
                if chatbot_id:
                    settings = session.exec(
                        select(ChatbotSettings)
                        .where(ChatbotSettings.chatbot_id == chatbot_id)
                        .order_by(ChatbotSettings.id.desc())
                    ).first()
                    if settings:
                        settings_id = settings.id
                
                # Query for cached evaluation
                query = (
                    select(EvaluationResult)
                    .where(EvaluationResult.datastore_id == datastore_id)
                    .where(EvaluationResult.framework == framework)
                    .where(EvaluationResult.is_valid == True)
                )
                
                if chatbot_id:
                    query = query.where(EvaluationResult.chatbot_id == chatbot_id)
                    if settings_id:
                        query = query.where(EvaluationResult.settings_id == settings_id)
                
                # Check if metrics match (convert both to sorted lists for comparison)
                cached_results = session.exec(query.order_by(EvaluationResult.created_at.desc())).all()
                
                for cached_result in cached_results:
                    cached_metrics = sorted(json.loads(cached_result.metrics))
                    requested_metrics = sorted(metrics)
                    
                    if cached_metrics == requested_metrics:
                        print(f"[INFO] Using cached evaluation results: {cached_result.evaluation_id}")
                        results = json.loads(cached_result.results)
                        update_evaluation_status(
                            evaluation_id, 
                            "completed", 
                            100, 
                            results=results, 
                            metrics=metrics, 
                            framework=framework
                        )
                        return results
        
        # No cache found or force_rerun is True - proceed with evaluation
        start_time = time.time()
        
        # First generate Q&A if needed
        update_evaluation_status(evaluation_id, "generating_qa", 15, metrics=metrics, framework=framework)
        qa_result = process_generate_qa(job_data)
        
        # CRITICAL: Ensure RAG responses exist BEFORE running any evaluation framework
        # This prevents Phoenix from failing due to missing responses
        update_evaluation_status(evaluation_id, "preparing_rag_responses", 40, metrics=metrics, framework=framework)
        print(f"[INFO] Ensuring RAG responses are available for evaluation...")
        
        settings_id = None
        with Session(engine) as session:
            try:
                # Get settings_id for saving with results
                if chatbot_id:
                    settings = session.exec(
                        select(ChatbotSettings)
                        .where(ChatbotSettings.chatbot_id == chatbot_id)
                        .order_by(ChatbotSettings.id.desc())
                    ).first()
                    if settings:
                        settings_id = settings.id
                
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
        
        execution_time = time.time() - start_time
        
        # Save results to database
        update_evaluation_status(evaluation_id, "saving_results", 95, metrics=metrics, framework=framework)
        
        with Session(engine) as session:
            try:
                evaluation_result = EvaluationResult(
                    evaluation_id=evaluation_id,
                    datastore_id=datastore_id,
                    chatbot_id=chatbot_id,
                    settings_id=settings_id,
                    framework=framework,
                    metrics=json.dumps(metrics),
                    results=json.dumps(results),
                    metadata=json.dumps({
                        "datastore_name": datastore_name,
                        "qa_result": qa_result
                    }),
                    execution_time_seconds=execution_time,
                    qa_count=qa_result.get("count", 0) if qa_result else 0,
                    is_valid=True
                )
                
                session.add(evaluation_result)
                session.commit()
                print(f"[INFO] Saved evaluation results to database: {evaluation_id}")
                
            except Exception as e:
                print(f"[WARN] Failed to save evaluation results to database: {str(e)}")
                traceback.print_exc()
                # Don't fail the entire evaluation if saving fails
        
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
