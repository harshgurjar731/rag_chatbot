"""
API routes for exposing backend configuration to the frontend.

This module provides endpoints that the frontend uses to populate dropdowns,
default values, and other UI configuration elements.
"""
# routes/config_routes.py
from fastapi import APIRouter
from frontend_config import (
    get_config,
    get_optimizer,
    get_embedding_models,
    get_llm_providers,
    get_llm_models,
    get_vector_dbs,
    get_reranker_options,
    get_guardrail_options,
    get_default_temperature,
    get_token_size_options,
    get_show_sources_default,
    get_api_base_url,
    get_evaluation_frameworks,
)

router = APIRouter()


# Full config
@router.get("/config")
def fetch_config():
    """Returns the full frontend configuration object."""
    return get_config()


# Individual endpoints
@router.get("/config/api-base-url")
def fetch_api_base_url():
    """Returns the configured API base URL."""
    return get_api_base_url()

@router.get("/config/optimizer")
def fetch_optimizer():
    """Returns available query optimizer options."""
    return get_optimizer()

@router.get("/config/embedding-models")
def fetch_embedding_models():
    """Returns available embedding model options."""
    return get_embedding_models()

@router.get("/config/llm-providers")
def fetch_llm_providers():
    """Returns available LLM provider options."""
    return get_llm_providers()

@router.get("/config/llm-models")
def fetch_llm_models():
    """Returns available LLM model options."""
    return get_llm_models()

@router.get("/config/vector-dbs")
def fetch_vector_dbs():
    """Returns available vector database options."""
    return get_vector_dbs()

@router.get("/config/reranker-options")
def fetch_reranker_options():
    """Returns available reranker options."""
    return get_reranker_options()

@router.get("/config/guardrail-options")
def fetch_guardrail_options():
    """Returns available guardrail options."""
    return get_guardrail_options()

@router.get("/config/default-temperature")
def fetch_default_temperature():
    return {"default_temperature": get_default_temperature()}

@router.get("/config/get_token_size_options")
def fetch_get_token_size_options():
    return {"default_token_size": get_token_size_options()}

@router.get("/config/show-sources-default")
def fetch_show_sources_default():
    return {"show_sources_default": get_show_sources_default()}

# Route to fetch evaluation frameworks
@router.get("/config/get-evaluation-frameworks")
def fetch_evaluation_frameworks():
    return {"evaluation_frameworks": get_evaluation_frameworks()}
