"""
RAG Configuration Module

This module defines the configuration settings for the RAG pipeline, including
LLM parameters, vector database settings, API keys, and guardrail thresholds.
It loads environment variables using `dotenv`.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv(override=True)

RAG_CONFIG = {
    # LLM Related
    "default_embedding_model": os.getenv("DEFAULT_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    "default_llm_provider": os.getenv("DEFAULT_LLM_PROVIDER", "groq"),
    "default_llm_model": os.getenv("DEFAULT_LLM_MODEL", "llama-3.3-70b-versatile"),
    "default_temperature": float(os.getenv("DEFAULT_TEMPERATURE", 0.0)),
    "default_top_p": float(os.getenv("DEFAULT_TOP_P", 0.0)),
    "default_max_tokens": int(os.getenv("DEFAULT_MAX_TOKENS", 256)),
    "default_reranker_type": os.getenv("DEFAULT_RERANKER_TYPE", "None"),
    "default_query_rewriting_type": os.getenv("DEFAULT_QUERY_REWRITING_TYPE", "None"),
    "default_guardrail_type": os.getenv("DEFAULT_GUARDRAIL_TYPE", "None"),

    #Azure Open AI configs
    "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_API_BASE", ""),
    "AZURE_OPENAI_API_KEY": os.getenv("AZURE_API_KEY", ""),
    "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_API_VERSION", "2025-01-01-preview"),

    #GROQ OPEN AI configs
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
    "GROQ_API_BASE": os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1"),

    "default_conversation_history_count": int(os.getenv("DEFAULT_CONVERSATION_HISTORY_COUNT", "10")),
    "default_ragfusion_rrf_k": int(os.getenv("DEFAULT_RAGFUSION_RRF_K", "60")),
    "default_multiquery_retrieval_top_k": int(os.getenv("DEFAULT_MULTIQUERY_RETRIEVAL_TOP_K", "5")),
    "default_query_retrieval_top_k": int(os.getenv("DEFAULT_QUERY_REWRITE_RETRIEVAL_TOP_K", "20")),
    "default_rerank_top_k": int(os.getenv("DEFAULT_RERANK_TOP_K", "5")),

    # Vector DB
    "default_vector_db": os.getenv("DEFAULT_VECTOR_DB", "faiss"),


    # Query Options
    "default_query_optimizer": os.getenv("DEFAULT_QUERY_OPTIMIZER", "Multi Query"),
    "default_reranker_option": os.getenv("DEFAULT_RERANKER_OPTION", "none"),
    "default_guardrail_option": os.getenv("DEFAULT_GUARDRAIL_OPTION", "none"),

    # Chatbot & Files
    "default_chat_history_limit": int(os.getenv("DEFAULT_CHAT_HISTORY_LIMIT", 1000)),
    "default_file_upload_types": os.getenv(
        "DEFAULT_FILE_UPLOAD_TYPES", ".pdf,.docx,.txt,.jpg,.jpeg,.png,.webp"
    ).split(","),

    # Chunking
    "default_chunk_method": os.getenv("DEFAULT_CHUNK_METHOD", "recursive"),
    "default_chunk_size": int(os.getenv("DEFAULT_CHUNK_SIZE", 512)),
    "default_chunk_overlap": int(os.getenv("DEFAULT_CHUNK_OVERLAP", 50)),

    # Data Folders
    "datastore_data_folder": os.getenv("DATASTORE_DATA_FOLDER", "Data"),
    "chunks_folder": os.getenv("CHUNKS_FOLDER", "Data"),

    # Translation
    "default_translation_source": os.getenv("DEFAULT_TRANSLATION_SOURCE", "auto"),
    "default_translation_format": os.getenv("DEFAULT_TRANSLATION_FORMAT", "text"),

    # API Keys
    "mistral_api_key": os.getenv("MISTRAL_API_KEY", ""),
    "groq_api_key": os.getenv("GROQ_API_KEY", ""),
    "groq_api_base": os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1"),

       # Azure OpenAI
    "azure_api_key": os.getenv("AZURE_API_KEY", ""),
    "azure_api_base": os.getenv("AZURE_API_BASE", ""),
    "azure_api_version": os.getenv("AZURE_API_VERSION", "2025-01-01-preview"),

    # Guardrail
    "default_guardrail_level": os.getenv("DEFAULT_GUARDRAIL_OPTION", "none"),

    # Guardrail thresholds
    "toxicity_threshold_basic": float(os.getenv("TOXICITY_THRESHOLD_BASIC", 0.9)),
    "toxicity_threshold_strict": float(os.getenv("TOXICITY_THRESHOLD_STRICT", 0.5)),
    "toxicity_threshold_custom": float(os.getenv("TOXICITY_THRESHOLD_CUSTOM", 0.7)),

    # Guardrail PII
    "pii_entities_strict": os.getenv("PII_ENTITIES_STRICT", "EMAIL_ADDRESS,PHONE_NUMBER,US_SSN").split(","),
    "pii_entities_custom": os.getenv("PII_ENTITIES_CUSTOM", "EMAIL_ADDRESS,CREDIT_CARD").split(","),
    "onfailaction_strict": os.getenv("ONFAILACTION_STRICT", "FIX"),
    "onfailaction_custom": os.getenv("ONFAILACTION_CUSTOM", "FIX"),
    
    # -----------------------------
    # RAG Fusion
    # -----------------------------
    "default_ragfusion_top_k": int(os.getenv("DEFAULT_RAGFUSION_TOP_K", 5)),
    "default_ragfusion_rrf_k": int(os.getenv("DEFAULT_RAGFUSION_RRF_K", 60)),

        # Re-ranker
    "default_reranker_top_k": int(os.getenv("DEFAULT_RERANKER_TOP_K", 5)),
    "cross_encoder_model": os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
    "bi_encoder_model": os.getenv("BI_ENCODER_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
    "llm_reranker_model": os.getenv("LLM_RERANKER_MODEL", "llama-3.3-70b-versatile"),
    "llm_reranker_max_tokens": int(os.getenv("LLM_RERANKER_MAX_TOKENS", 512)),


    # -----------------------------
    # Model Platform Configurations
    # -----------------------------
    "groq_supported_models": os.getenv(
        "GROQ_SUPPORTED_MODELS",
        "llama-3.3-70b-versatile,deepseek-r1-distill-llama-70b,gemma2-9b-it,llama-3.1-8b-instant,openai/gpt-oss-20b"
    ).split(","),

    "azure_supported_models": os.getenv(
        "AZURE_SUPPORTED_MODELS",
        "gpt-4o-mini"
    ).split(","),



}