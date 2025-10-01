# routes/config_routes.py
from fastapi import APIRouter
from frontend_config import (
    get_config,
    get_optimizer,
    get_embedding_models,
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
    return get_config()


# Individual endpoints
@router.get("/config/api-base-url")
def fetch_api_base_url():
    return get_api_base_url()

@router.get("/config/optimizer")
def fetch_optimizer():
    return get_optimizer()

@router.get("/config/embedding-models")
def fetch_embedding_models():
    return get_embedding_models()

@router.get("/config/llm-models")
def fetch_llm_models():
    return get_llm_models()

@router.get("/config/vector-dbs")
def fetch_vector_dbs():
    return get_vector_dbs()

@router.get("/config/reranker-options")
def fetch_reranker_options():
    return get_reranker_options()

@router.get("/config/guardrail-options")
def fetch_guardrail_options():
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
