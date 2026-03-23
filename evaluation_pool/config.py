
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Auto-detect if running in Docker
IS_DOCKER = os.path.exists('/.dockerenv') or os.path.exists('/proc/self/cgroup') and 'docker' in open('/proc/self/cgroup').read()

CONFIG = {
    # Azure OpenAI
    "azure_api_key": os.getenv("AZURE_API_KEY", "").strip(),
    "azure_api_base": os.getenv("AZURE_API_BASE", "").strip(),
    "azure_api_version": os.getenv("AZURE_API_VERSION", "2024-02-15-preview").strip(),
    
    # Generic OpenAI / Groq
    "openai_api_key": os.getenv("OPENAI_API_KEY", "").strip(),
    "groq_api_key": os.getenv("GROQ_API_KEY", "").strip(),
    "groq_api_base": os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1").strip(),
    
    # Database
    "db_user": os.getenv("DB_USER", "user").strip(),
    "db_password": os.getenv("DB_PASSWORD", "password").strip(),
    "db_host": os.getenv("DB_HOST", "db" if IS_DOCKER else "localhost").strip(),
    "db_name": os.getenv("DB_NAME", "chatbot_db").strip(),
    
    # Redis
    "redis_host": os.getenv("REDIS_HOST", "redis" if IS_DOCKER else "localhost").strip(),
    "redis_port": os.getenv("REDIS_PORT", "6379").strip(),
    
    # Paths
    "data_directory": os.getenv("DATA_DIRECTORY", "/app/data_directory" if IS_DOCKER else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_directory")).strip(),
    
    # Evaluation Configuration
    "evaluation_llm_provider": os.getenv("EVALUATION_LLM_PROVIDER", "groq").strip(),
    "evaluation_llm_model": os.getenv("EVALUATION_LLM_MODEL", "llama-3.3-70b-versatile").strip(),
}

# Resolve relative data_directory path if not in Docker
if not IS_DOCKER and not os.path.isabs(CONFIG["data_directory"]):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG["data_directory"] = os.path.abspath(os.path.join(base_dir, CONFIG["data_directory"]))
