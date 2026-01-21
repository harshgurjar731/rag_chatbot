import json
import subprocess
from pathlib import Path
from shutil import move,copy
import os
import time

def filename(path: str):
    name, _ = os.path.splitext(os.path.basename(path))
    return name


# -------------------
# UTILS
# -------------------
def run_command(cmd: list[str]):
    """Run a shell command and stream output."""
    print(f"[RUN] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def process_file(file_path: str, output_dir: str="",datastore_name:str=""):
    parsed_file = f"data/parsed/{filename(file_path)}.lance" 
    generated_file = f"data/generated/{filename(file_path)}_qa_pairs.json"
    curated_file = f"data/curated/{filename(file_path)}_qa_pairs_cleaned.json"
    json_path = f"{output_dir}/{filename(file_path)}_qa_pairs_cleaned.json"

    
    # run_command(["mkdir", "-p", "Test_data/input"])
    run_command(["synthetic-data-kit", "ingest", file_path])
    run_command(["synthetic-data-kit", "create", parsed_file, "--type", "qa"])
    run_command(["synthetic-data-kit", "curate", generated_file])
    run_command([
        "synthetic-data-kit", "save-as", curated_file,
        "--format", "alpaca", "--storage", "hf"
    ])
    time.sleep(3) 
    Path(output_dir).mkdir(parents=True, exist_ok=True)  # Ensure directory exists

# Move curated file to output_dir
    copy(curated_file, json_path)

    if Path(curated_file).exists():
        with open(curated_file, "r", encoding="utf-8") as f:
            qna_list = json.load(f)
        # insert_qna(chunk_id, qna_list)
        return {"status": "success", "inserted": len(qna_list["qa_pairs"])}
    else:
        raise FileNotFoundError("Curated file not found after pipeline run.")