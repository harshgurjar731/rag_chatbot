import redis
import json
import os
import time

def run_test():
    # 1. Connect to Redis
    # We are running inside the container network, so host is 'redis'
    try:
        r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
        r.ping()
        print("[*] Connected to Redis successfully.")
    except Exception as e:
        print(f"[!] Failed to connect to Redis: {e}")
        return

    # 2. Create a sample file
    input_dir = "/app/data_directory"
    # Ensure directory exists (it should via volume mount)
    os.makedirs(input_dir, exist_ok=True)
    
    input_file = os.path.join(input_dir, "test_synthetic.txt")
    output_dir = os.path.join(input_dir, "synthetic_output")
    
    sample_text = """
    RAG (Retrieval-Augmented Generation) is a technique for enhancing the accuracy and reliability of generative AI models with facts fetched from external sources.
    It bridges the gap between private data and public training data for Large Language Models (LLMs).
    By retrieving relevant information and injecting it into the context window, RAG reduces hallucinations and ensures the model has access to up-to-date information.
    """
    
    with open(input_file, "w", encoding="utf-8") as f:
        f.write(sample_text)
        
    print(f"[*] Created sample input file at: {input_file}")

    # 3. Create Job Payload
    job = {
        "job_type": "generate_qa",
        "input_file": input_file,
        "output_dir": output_dir,
        "num_pairs": 3
    }
    
    # 4. Push to Redis
    queue_key = "synthetic_data:inbox"
    r.rpush(queue_key, json.dumps(job))
    print(f"[*] Pushed job to queue '{queue_key}':")
    print(json.dumps(job, indent=2))
    
    print("\n[*] Test trigger complete. Check the service logs to see processing:")
    print("    docker compose logs -f synthetic_data_service")

if __name__ == "__main__":
    run_test()
