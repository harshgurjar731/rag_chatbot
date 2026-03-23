"""
Q&A Generator Module
Uses synthetic-data-kit for generating Q&A pairs from documents.
"""
import os
import json
import subprocess
import traceback
from pathlib import Path
from typing import Dict, Any, List
from sqlmodel import SQLModel, create_engine, Session, select
from database_models import DocumentRecord, QuestionAnswerV2
import yaml
import synthetic_data_kit

# Auto-detect if running in Docker
IS_DOCKER = os.path.exists('/.dockerenv') or os.path.exists('/proc/self/cgroup') and 'docker' in open('/proc/self/cgroup').read()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIRECTORY = os.getenv("DATA_DIRECTORY", "/app/data_directory" if IS_DOCKER else os.path.join(PROJECT_ROOT, "data_directory"))
if not os.path.isabs(DATA_DIRECTORY):
    DATA_DIRECTORY = os.path.abspath(os.path.join(PROJECT_ROOT, DATA_DIRECTORY))

# DB Connection
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "db" if IS_DOCKER else "localhost")
DB_NAME = os.getenv("DB_NAME", "chatbot_db")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

engine = create_engine(DATABASE_URL)


def load_sdk_config() -> Dict[str, Any]:
    """
    Load configuration from synthetic-data-kit config.yaml file.
    """
    try:
        config_path = os.path.join(os.path.dirname(synthetic_data_kit.__file__), "config.yaml")
        if not os.path.exists(config_path):
            print(f"[WARN] Config file not found at {config_path}")
            return {}
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        print(f"[INFO] Loaded config from {config_path}")
        return config
    except Exception as e:
        print(f"[ERROR] Failed to load SDK config: {e}")
        return {}


def update_sdk_config_with_api_key(provider: str, api_key: str):
    """
    Update only the API key in the config file for the specified provider.
    All other settings are read from the existing config.
    """
    try:
        config_path = os.path.join(os.path.dirname(synthetic_data_kit.__file__), "config.yaml")
        if not os.path.exists(config_path):
            print(f"[WARN] Config file not found at {config_path}")
            return

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}

        # Update only the API key for the specified provider
        if provider == 'api-endpoint' and 'api-endpoint' in config:
            config['api-endpoint']['api_key'] = api_key
            print(f"[INFO] Updated API key for api-endpoint provider")
        elif provider == 'azure-openai' and 'azure-openai' in config:
            config['azure-openai']['api_key'] = api_key
            print(f"[INFO] Updated API key for Azure OpenAI provider")
        else:
            print(f"[WARN] Provider {provider} not found in config")
            return

        with open(config_path, 'w') as f:
            yaml.dump(config, f)
            
    except Exception as e:
        print(f"[ERROR] Failed to update SDK config: {e}")


def run_command(cmd: list, cwd: str = None, env: Dict[str, str] = None) -> bool:
    """Run a shell command and stream output."""
    print(f"[CMD] {' '.join(cmd)}")
    try:
        # Merge provided env with system env
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
            
        result = subprocess.run(cmd, check=True, cwd=cwd, env=full_env, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {e.stderr}")
        return False


def get_filename_without_ext(path: str) -> str:
    """Get filename without extension."""
    return os.path.splitext(os.path.basename(path))[0]


def process_document_for_qa(file_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Process a document through synthetic-data-kit pipeline.
    """
    filename = get_filename_without_ext(file_path)

    # Use ABSOLUTE paths to avoid CWD-relative path issues
    output_dir_abs = os.path.abspath(output_dir)
    parsed_dir   = os.path.join(output_dir_abs, "parsed")
    generated_dir = os.path.join(output_dir_abs, "generated")
    curated_dir  = os.path.join(output_dir_abs, "curated")

    Path(parsed_dir).mkdir(parents=True, exist_ok=True)
    Path(generated_dir).mkdir(parents=True, exist_ok=True)
    Path(curated_dir).mkdir(parents=True, exist_ok=True)

    # Absolute paths for the intermediate files
    parsed_file   = os.path.join(parsed_dir,   f"{filename}.lance")
    generated_file = os.path.join(generated_dir, f"{filename}_qa_pairs.json")
    curated_file  = os.path.join(curated_dir,  f"{filename}_qa_pairs_cleaned.json")

    # Normalize source file path (critical for Windows paths with spaces / mixed separators)
    file_path = os.path.normpath(file_path)

    # Pre-flight: verify source file exists before starting
    if not os.path.exists(file_path):
        print(f"[ERROR] Source file does not exist: {file_path}")
        return {"status": "failed", "error": f"Source file not found: {file_path}"}

    # Load configuration from config.yaml
    config = load_sdk_config()

    # Get the provider from config
    provider = config.get('llm', {}).get('provider')
    if not provider:
        print("[ERROR] No provider specified in config.yaml")
        return {"status": "failed", "error": "No provider specified in config"}
    
    print(f"[INFO] Using provider from config: {provider}")
    
    # Update API key from environment variable (only sensitive data comes from env)
    env_vars = {}
    
    if provider == 'azure-openai':
        api_key = os.getenv("AZURE_API_KEY")
        if not api_key:
            print("[ERROR] AZURE_API_KEY environment variable not set")
            return {"status": "failed", "error": "Azure API key not found"}
        
        # Update only the API key, keep all other config from file
        update_sdk_config_with_api_key('azure-openai', api_key)
        
        # Get Azure config from file for logging
        azure_config = config.get('azure-openai', {})
        endpoint = azure_config.get('azure_endpoint', 'N/A')
        deployment = azure_config.get('deployment_name', 'N/A')
        print(f"[INFO] Azure OpenAI configured: {endpoint} (deployment: {deployment})")
        
    elif provider == 'api-endpoint':
        # Try to find which API key is available
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("[ERROR] No API key found for api-endpoint provider")
            return {"status": "failed", "error": "API endpoint key not found"}
        
        # Update only the API key, keep api_base from config
        update_sdk_config_with_api_key('api-endpoint', api_key)
        
        # Get api-endpoint config from file
        api_config = config.get('api-endpoint', {})
        api_base = api_config.get('api_base', 'N/A')
        print(f"[INFO] API endpoint configured: {api_base}")
        
        # Set env vars for subprocess
        env_vars = {
            "API_ENDPOINT_KEY": api_key,
            "API_ENDPOINT_URL": api_base
        }
    else:
        print(f"[ERROR] Unsupported provider: {provider}")
        return {"status": "failed", "error": f"Unsupported provider: {provider}"}


    import sys

    # Build steps with ABSOLUTE paths so output locations are predictable regardless of CWD.
    # --output-dir tells each SDK command exactly where to write its files.
    # Original Docker steps (kept for reference):
    # steps = [
    #     (["synthetic-data-kit", "ingest", file_path], "Ingesting document"),
    #     (["synthetic-data-kit", "create", parsed_file_rel, "--type", "qa"], "Generating Q&A"),
    #     (["synthetic-data-kit", "curate", generated_file_rel], "Curating Q&A"),
    # ]
    steps = [
        # ingest: --output-dir sets the directory; SDK names the file after the input basename
        ([sys.executable, "-m", "synthetic_data_kit", "ingest", file_path, "--output-dir", parsed_dir], "Ingesting document"),
        # create: --output-dir sets the directory; SDK names the file {base_name}_qa_pairs.json
        ([sys.executable, "-m", "synthetic_data_kit", "create", parsed_file, "--type", "qa", "--output-dir", generated_dir], "Generating Q&A"),
        # curate: uses --output (full path) not --output-dir; SDK names the file {base_name}_cleaned.json
        ([sys.executable, "-m", "synthetic_data_kit", "curate", generated_file, "--output", curated_file], "Curating Q&A"),
    ]

    for cmd, description in steps:
        print(f"[STEP] {description}...")
        if not run_command(cmd, env=env_vars):
            return {"status": "failed", "error": f"Failed at: {description}"}

        # After ingest, verify the lance file was actually produced before continuing
        if description == "Ingesting document" and not os.path.exists(parsed_file):
            print(f"[ERROR] Ingest step completed but lance file not found at: {parsed_file}")
            return {"status": "failed", "error": "Ingest produced no output (lance file missing)"}

    # Check final output
    if os.path.exists(curated_file):
        try:
            with open(curated_file, "r", encoding="utf-8") as f:
                qa_data = json.load(f)

            return {
                "status": "success",
                "qa_pairs": qa_data.get("qa_pairs", []),
                "count": len(qa_data.get("qa_pairs", []))
            }
        except Exception as e:
            return {"status": "failed", "error": f"Failed to parse output: {e}"}

    return {"status": "failed", "error": "Output file not found"}

def generate_qa_for_datastore(datastore_id: int, datastore_name: str) -> Dict[str, Any]:
    """
    Generate Q&A pairs for all files in a datastore.
    """
    print(f"[INFO] Generating Q&A for datastore {datastore_id} ({datastore_name})")
    
    total_qa_count = 0
    processed_files = 0
    errors = []
    
    try:
        with Session(engine) as session:
            # 1. Fetch documents
            docs = session.exec(
                select(DocumentRecord).where(DocumentRecord.datastore_id == datastore_id)
            ).all()
            
            print(f"[INFO] Found {len(docs)} documents for datastore {datastore_id}")
            
            for doc in docs:
                if not doc.filePath:
                    print(f"[WARN] Document {doc.id} ({doc.filename}) has no filePath. Skipping.")
                    continue
                
                # Check for existing Q&A
                existing_qa_count = session.exec(
                    select(QuestionAnswerV2).where(QuestionAnswerV2.document_id == doc.id)
                ).all()
                
                if len(existing_qa_count) > 0:
                     print(f"[INFO] Document {doc.id} ({doc.filename}) already has {len(existing_qa_count)} Q&A pairs. Skipping generation.")
                     continue
                
                # Resolve file path — handle Docker paths, local paths, and the local ingestion layout
                raw_path = doc.filePath
                file_path = None

                # 1. Docker-style path mapping: /app/data_directory/... or \app\data_directory\...
                # We check this FIRST because on Windows, \app\... might accidentally exist
                # (pointing to root of drive) but we ALWAYS want to map it if it has this prefix.
                if raw_path:
                    norm = raw_path.replace('\\', '/')
                    if norm.startswith('/app/data_directory'):
                        rel_path = norm[len('/app/data_directory'):].lstrip('/')
                        candidate = os.path.normpath(os.path.join(DATA_DIRECTORY, rel_path))
                        if os.path.exists(candidate):
                            file_path = candidate
                            print(f"[INFO] Mapped Docker path {raw_path} -> {file_path}")

                # 2. Try the path exactly as stored in DB (works for newly-uploaded local files)
                if file_path is None and raw_path and os.path.exists(raw_path):
                    file_path = raw_path

                # 3. Fallback: reconstruct from local ingestion_root layout
                #    ingestion_root = DATA_DIRECTORY/../  (i.e. parent of data_directory)
                #    files saved to: ingestion_root/data_directory/{datastore_name}/{filename}
                if file_path is None:
                    ingestion_root = os.path.dirname(DATA_DIRECTORY)
                    candidate = os.path.normpath(os.path.join(ingestion_root, "data_directory", datastore_name, doc.filename))
                    if os.path.exists(candidate):
                        file_path = candidate
                        print(f"[INFO] Located file via ingestion layout: {file_path}")

                if file_path is None:
                    print(f"[WARN] File not found for document {doc.id} ({doc.filename}). Tried: {raw_path}")
                    errors.append(f"{doc.filename}: file not found on disk")
                    continue

                file_path = os.path.normpath(file_path)
                
                # Permanently update the database record with the resolved local path
                # if it differs from the current stored path (e.g. Docker paths)
                if doc.filePath != file_path:
                    print(f"[INFO] Updating database record for {doc.filename} with local path: {file_path}")
                    doc.filePath = file_path
                    session.add(doc)
                    # We commit at the end of the loop, but adding to session here is enough
                
                print(f"[INFO] Processing file: {file_path}")
                
                # 2. Process File
                # Utilize a temp output dir
                output_dir = os.path.join(DATA_DIRECTORY, datastore_name, "qa_output")
                
                result = process_document_for_qa(file_path, output_dir)
                
                if result.get("status") == "success":
                    qa_pairs = result.get("qa_pairs", [])
                    print(f"[INFO] Generated {len(qa_pairs)} pairs for {doc.filename}")
                    
                    # 3. Save to DB
                    for qa in qa_pairs:
                        qa_entry = QuestionAnswerV2(
                            question=qa.get("question", ""),
                            answer=qa.get("answer", ""),
                            datastore_id=datastore_id,
                            document_id=doc.id, # Using DocumentRecord ID
                            file_name=doc.filename
                        )
                        session.add(qa_entry)
                    
                    total_qa_count += len(qa_pairs)
                    processed_files += 1
                else:
                    print(f"[ERROR] Failed to process {doc.filename}: {result.get('error')}")
                    errors.append(f"{doc.filename}: {result.get('error')}")
            
            session.commit()
            
    except Exception as e:
        print(f"[ERROR] DB Operation failed: {e}")
        traceback.print_exc()
        return {
            "status": "failed",
            "error": str(e)
        }
        
    return {
        "status": "success",
        "datastore_id": datastore_id,
        "datastore_name": datastore_name,
        "count": total_qa_count,
        "processed_files": processed_files,
        "errors": errors
    }
