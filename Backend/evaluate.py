# In a new file, `evaluate.py`
import phoenix as px
from phoenix.session.evaluation import get_qa_with_reference
from phoenix.evals import HallucinationEvaluator, OpenAIModel
import pandas as pd

def run_evaluation_script():
    # Ensure Phoenix is running
    print("Connecting to Phoenix session...")
    
    # You might need to wait for a session to be active or load from a specific run ID
    # For a simple local setup, a small delay might work
    # time.sleep(10) 
    
    try:
        session = px.active_session()
        print(f"Active session found: {session.run_id}")
    except RuntimeError as e:
        print(f"Error: {e}. Ensure Phoenix is running and instrumenting your app.")
        return

    # Get the traces into a dataframe
    qa_df = get_qa_with_reference(session)
    
    if qa_df.empty:
        print("No QA traces found to evaluate.")
        return
        
    print(f"Found {len(qa_df)} QA traces.")

    # Run evaluations
    model = OpenAIModel("gpt-4-turbo-preview")
    hallucination_evaluator = HallucinationEvaluator(model=model)
    hallucination_eval = hallucination_evaluator.run(qa_df)

    # Log the results back
    session.log_evaluations(hallucination_eval)
    print("Hallucination evaluation complete and logged to Phoenix.")

if __name__ == "__main__":
    run_evaluation_script()