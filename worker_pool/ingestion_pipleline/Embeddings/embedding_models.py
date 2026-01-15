"""
Embedding model factory.

This module provides a unified interface to instantiate different embedding models
(HuggingFace, OpenAI/Azure) based on configuration.
"""
from typing import Protocol
from typing import List
from langchain_core.documents import Document
from ingestion_pipleline.Config.Config import INGESTION_CONFIG

class EmbeddingModelsProtocol(Protocol):
    """Protocol for configuring embedding models."""
    def configureModel(self, model_name: str):
        ...

def create_embedding_model(provider: str, model_name: str):
    """
    Factory function to create an embedding model instance.

    Args:
        provider (str): 'HuggingFace' or 'OpenAI'.
        model_name (str): Name of the model to use.

    Returns:
        Embeddings: Configured LangChain embedding model.
    """
    if (provider == "HuggingFace"):
        print("Creating HuggingFace Embedding")
        return HuggingFaceModel().configureModel(
            model_name=model_name
        )
    elif (provider == "OpenAI"):
        print("Creating OpenAI Embedding")
        return OpenAIModel().configureModel(
           model_name=model_name 
        ) 
    
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_experimental.open_clip.open_clip import OpenCLIPEmbeddings
class HuggingFaceModel(EmbeddingModelsProtocol):
    """Configurator for HuggingFace embeddings (including OpenCLIP)."""
    def configureModel(self, model_name: str):
        if (model_name == "ViT-H-14"):
            print("In clip embedding:", model_name) #TODOANKIT - See how to handle CLIP Model embedding
            return OpenCLIPEmbeddings(model_name=model_name)
        return HuggingFaceEmbeddings(model_name=model_name)

from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import AzureOpenAIEmbeddings
class OpenAIModel(EmbeddingModelsProtocol):
    """Configurator for Azure OpenAI embeddings."""
    def configureModel(self, model_name: str):
        return AzureOpenAIEmbeddings(
            model=model_name,
            azure_endpoint=INGESTION_CONFIG["AZURE_OPENAI_ENDPOINT"],
            api_key=INGESTION_CONFIG["AZURE_OPENAI_API_KEY"],
            api_version=INGESTION_CONFIG["AZURE_OPENAI_API_VERSION"],
            azure_deployment=model_name
        )