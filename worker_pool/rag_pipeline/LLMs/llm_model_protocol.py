"""
This module defines the protocol and implementations for LLM (Large Language Model) interactions.

It includes a protocol `LLMModelsProtocol` that defines the interface for obtaining
LLM instances, and concrete implementations for different providers like Groq and Azure OpenAI.
"""

from typing import Protocol, Any
from langchain_openai import ChatOpenAI
from langchain_openai import AzureChatOpenAI
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from rag_pipeline.Config.rag_config import RAG_CONFIG


class LLMModelsProtocol(Protocol):
    """
    Protocol defining the interface for LLM model factories.
    """

    def get_llm(self, model_name: str, temperature: float, max_tokens: int) -> Any:
        """
        Get an instance of a Language Model.

        Args:
            model_name (str): The name of the model to use.
            temperature (float): The sampling temperature (0.0 to 1.0).
            max_tokens (int): The maximum number of tokens to generate.

        Returns:
            Any: An instance of a LangChain compatible LLM/ChatModel.
        """
        ...


def create_llm_model(provider: str, model_name: str, temperature: float, max_tokens: int) -> Any:
    """
    Factory function to create an LLM model instance based on the provider.

    Args:
        provider (str): The name of the LLM provider (e.g., "groq", "azureopenai").
        model_name (str): The name of the model to use.
        temperature (float): The sampling temperature.
        max_tokens (int): The maximum number of tokens to generate.

    Returns:
        Any: An instance of a LangChain compatible LLM/ChatModel.

    Raises:
        ValueError: If the provider is not supported.
    """
    if provider.lower() == "groq":
        print("Creating Groq LLM")
        return GroqLLMModel().get_llm(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    elif provider.lower() == "azureopenai":
        print("Creating Azure OpenAI LLM")
        return AzureOpenAILLMModel().get_llm(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        # Fallback or error could be handled here
        print(f"Warning: Unknown provider {provider}")
        return None


class GroqLLMModel(LLMModelsProtocol):
    """
    Implementation of LLMModelsProtocol for Groq's OpenAI-compatible API.
    """

    def get_llm(self, model_name: str, temperature: float, max_tokens: int) -> ChatOpenAI:
        """
        Get a ChatOpenAI instance configured for Groq.

        Args:
            model_name (str): The name of the Groq model.
            temperature (float): The sampling temperature.
            max_tokens (int): The maximum number of tokens to generate.

        Returns:
            ChatOpenAI: A configured ChatOpenAI instance.

        Raises:
            ValueError: If GROQ_API_KEY is missing from configuration.
        """
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
    """
    Implementation of LLMModelsProtocol for Azure OpenAI.
    """

    def get_llm(self, model_name: str, temperature: float, max_tokens: int) -> AzureChatOpenAI:
        """
        Get an AzureChatOpenAI instance.

        Args:
            model_name (str): The deployment name of the Azure OpenAI model.
            temperature (float): The sampling temperature.
            max_tokens (int): The maximum number of tokens to generate.

        Returns:
            AzureChatOpenAI: A configured AzureChatOpenAI instance.

        Raises:
            ValueError: If Azure credentials are missing from configuration.
        """
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