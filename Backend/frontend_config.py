# config.py
from pydantic import BaseModel
from typing import List,Dict
from config import CONFIG  # ✅ centralized config
from models.User import DepartmentEnum
# ---------------------------
# Pydantic Models
# ---------------------------

class Language(BaseModel):
    code: str
    name: str

class ModelConfig(BaseModel):
    base_url:str
    optimizer: List[Dict[str, str]] 
    embedding_models: List[str]
    llm_providers: List[str]
    llm_models: List[str]
    vector_dbs: List[str]
    reranker_options: List[str]
    guardrail_options: List[Dict[str, str]]
    default_temperature: float
    token_size_options: Dict[str, int]
    show_sources_default: bool
    languages: List[Language]
    eval_framworks:Dict[str, List[str]]
    user_departments: List[DepartmentEnum]


# ---------------------------
# Individual Getters
# ---------------------------

def get_api_base_url() -> str:
    """
    Returns the API base URL from environment variables.
    Falls back to 172.200.163.232 if not set.
    """
    return CONFIG["backend_base_url"]

def get_optimizer() -> List[Dict[str, str]]:
    """
    Returns available optimizer options with machine-friendly values and user-friendly labels.
    """
    return [
        {"value": "none", "label": "None"},
        {"value": "multiquery", "label": "Multi Query"},
        {"value": "stepback", "label": "Step Back"},
        {"value": "ragfusion", "label": "RAG Fusion"},
    ]

def get_embedding_models() -> List[str]:
    return [
        "all-MiniLM-L6-v2",
        "bge-base-en",
        "bge-large-en",
        "e5-large-v2",
    ]

def get_llm_providers() -> List[str]:
    return [
        "groq",
        "azureopenai"
    ]

def get_llm_models() -> List[str]:
    return [
        "llama-3.3-70b-versatile",
        "deepseek-r1-distill-llama-70b",
        "gemma2-9b-it",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-20b",
        "gpt-4o-mini",
    ]

def get_evaluation_frameworks() -> Dict[str, List[str]]:
    return {
        "Phoenix": [
            "Hallucination",      # maps to hallucination_eval
            "Answer Relevance",   # maps to qna_eval
            "RAG Relevancy",      # maps to rag_relevancy_eval
            "Toxicity",           # maps to toxicity_eval
        ],
        "Ragaas": [
            "Faithfulness",
        "Answer Relevancy",
        "Context Precision",
        "Context Recall",          # maps to toxicity_eval
        ],
    }


def get_vector_dbs() -> List[str]:
    return ["FAISS", "Pinecone", "Chroma", "Weaviate"]

def get_reranker_options() -> List[str]:
    return ["None", "Cohere", "Cross-encoder", "OpenAI Reranker"]



def get_guardrail_options() -> List[Dict[str, str]]:
    return [
        {"value": "none", "label": "None - No filtering"},
        {"value": "basic", "label": "Basic - Mild safety filtering"},
        {"value": "strict", "label": "Strict - High safety filtering"},
        {"value": "custom", "label": "Custom - Use project-defined rules"},
    ]

def get_default_temperature() -> float:
    return 0.0

def get_token_size_options() -> Dict[str, int]:
    """
    Returns token size configuration including default, min, max, and step values.
    """
    return {
        "default": 512,
        "min": 256,
        "max": 2048,
        "step": 128,
    }

def get_show_sources_default() -> bool:
    return True

def get_languages() -> List[Dict[str, str]]:
    return [
        { "code": "en", "name": "English" },
        { "code": "hi", "name": "Hindi" },
        { "code": "es", "name": "Spanish" },
        { "code": "fr", "name": "French" },
        { "code": "de", "name": "German" },
        { "code": "zh-CN", "name": "Chinese (Simplified)" },
        { "code": "zh-TW", "name": "Chinese (Traditional)" },
        { "code": "ar", "name": "Arabic" },
        { "code": "ja", "name": "Japanese" },
        { "code": "ko", "name": "Korean" },
        { "code": "ru", "name": "Russian" },
        { "code": "pt", "name": "Portuguese" },
        { "code": "it", "name": "Italian" },
        { "code": "nl", "name": "Dutch" },
        { "code": "tr", "name": "Turkish" },
        { "code": "sv", "name": "Swedish" },
        { "code": "pl", "name": "Polish" },
        { "code": "uk", "name": "Ukrainian" },
        { "code": "bn", "name": "Bengali" },
        { "code": "ta", "name": "Tamil" },
        { "code": "te", "name": "Telugu" },
        { "code": "gu", "name": "Gujarati" },
        { "code": "mr", "name": "Marathi" },
    ]

# ---------------------------
# Combined Config Getter
# ---------------------------
def get_config() -> ModelConfig:
    """
    Returns the full config object for frontend.
    """
    return ModelConfig(
        base_url=get_api_base_url(),
        optimizer=get_optimizer(),
        embedding_models=get_embedding_models(),
        llm_providers=get_llm_providers(),
        llm_models=get_llm_models(),
        vector_dbs=get_vector_dbs(),
        reranker_options=get_reranker_options(),
        guardrail_options=get_guardrail_options(),
        default_temperature=get_default_temperature(),
        token_size_options=get_token_size_options(),
        show_sources_default=get_show_sources_default(),
        languages=get_languages(),
        eval_framworks=get_evaluation_frameworks(),
        user_departments=[dept.value for dept in DepartmentEnum]
    )
