
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from Backend.config import CONFIG
    from Backend.Evaluation.phoenix import evaluate_records, EvaluationRequest, EvaluationRecord
    from phoenix.evals import MistralAIModel
except ImportError:
    # Try local import if running from Backend directly
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))
    from config import CONFIG
    from Evaluation.phoenix import evaluate_records, EvaluationRequest, EvaluationRecord
    from phoenix.evals import MistralAIModel

def check_api_key():
    key = CONFIG.get("mistral_api_key")
    if not key:
        print("[ERROR] MISTRAL_API_KEY is missing in CONFIG.")
        return False
    print(f"[INFO] MISTRAL_API_KEY found: {key[:4]}...{key[-4:]}")
    return True

def test_evaluation():
    print("[INFO] Starting Phoenix Evaluation Test...")
    
    # Dummy data
    records = [
        EvaluationRecord(
            reference="The capital of France is Paris.",
            query="What is the capital of France?",
            response="Paris is the capital of France."
        )
    ]
    
    req = EvaluationRequest(data=records, provide_explanation=True)
    
    try:
        # Test 'hallucination' metric
        print("[INFO] Testing 'hallucination' metric...")
        result = evaluate_records(req, metric="hallucination")
        print(f"[SUCCESS] Hallucination Result: {result.results[0].hallucination_eval}")
        
    except Exception as e:
        print(f"[ERROR] Hallucination evaluation failed: {e}")
        import traceback
        traceback.print_exc()

    try:
         # Test 'qna' metric
        print("[INFO] Testing 'qna' metric...")
        result = evaluate_records(req, metric="qna")
        print(f"[SUCCESS] QnA Result: {result.results[0].qna_eval}")
        
    except Exception as e:
        print(f"[ERROR] QnA evaluation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if check_api_key():
        test_evaluation()
