from typing import Protocol
from langchain_openai import ChatOpenAI
from langchain_openai import AzureChatOpenAI
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from rag_pipeline.Config.rag_config import RAG_CONFIG

class LLMModelsProtocol(Protocol):
    def get_llm(self, model_name: str, temperature: str, ):
        ...

def create_llm_model(provider: str, model_name: str, temperature: str, max_tokens: str):
    if (provider.lower() == "groq"):
        print("Creating Groq LLM")
        return GroqLLMModel().get_llm(
            model_name=model_name,
            temperature= temperature,
            max_tokens= max_tokens
        )
    elif (provider.lower == "azureopenai"):
        print("Creating Azure OpenAI LLM")
        return AzureOpenAILLMModel().get_llm(
            model_name=model_name,
            temperature= temperature,
            max_tokens= max_tokens
        )
    
class GroqLLMModel(LLMModelsProtocol):
    def get_llm(self, model_name: str, temperature: float, max_tokens):
        # Only works if you are using Groq’s OpenAI-compatible API endpoint
        groq_api_key = RAG_CONFIG["GROQ_API_KEY"]
        groq_api_base = RAG_CONFIG["GROQ_API_BASE"]

        if not groq_api_key:
            raise ValueError("Missing GROQ_API_KEY in config or environment")

        return ChatOpenAI(
            openai_api_base=groq_api_base,
            openai_api_key=groq_api_key,
            model=model_name,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )


class AzureOpenAILLMModel(LLMModelsProtocol):
    def get_llm(self, model_name: str, temperature: float, max_tokens):
        # Only works if you are using Groq’s OpenAI-compatible API endpoint
        
        azure_api_key = RAG_CONFIG["AZURE_OPENAI_API_KEY"]
        azure_endpoint = RAG_CONFIG["AZURE_OPENAI_ENDPOINT"]
        azure_api_version = RAG_CONFIG["AZURE_OPENAI_API_VERSION"]

        if not azure_api_key or not azure_endpoint:
            raise ValueError("Azure credentials not found in config or environment")

        return AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_deployment=model_name,  # or use self.model_name if dynamic
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )