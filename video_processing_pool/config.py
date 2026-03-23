import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv(override=True)

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

# Database
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "chatbot_db")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# ChromaDB
CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST", "chromadb")
CHROMA_SERVER_PORT = os.getenv("CHROMA_SERVER_PORT", "8000")

# Video Processing Pool
VIDEO_POOL_SIZE = int(os.getenv("VIDEO_POOL_SIZE", "1"))
VIDEO_POOL_PORT = int(os.getenv("VIDEO_POOL_PORT", "8004"))

# Mistral API
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# Data directories
DATA_DIRECTORY = os.getenv("DATA_DIRECTORY", "/app/data_directory")
if not os.path.isabs(DATA_DIRECTORY):
    # Resolve relative to project root (rag_chatbot)
    # This config is in rag_chatbot/video_processing_pool/config.py
    # So project root is the parent directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIRECTORY = os.path.abspath(os.path.join(base_dir, DATA_DIRECTORY))

OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(DATA_DIRECTORY, "video_output"))
TEMP_DIR = os.getenv("TEMP_DIR", os.path.join(DATA_DIRECTORY, "video_temp"))
GRAPH_DIR = os.getenv("GRAPH_DIR", os.path.join(DATA_DIRECTORY, "video_graphs"))
