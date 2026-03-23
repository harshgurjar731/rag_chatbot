from typing import Protocol
from typing import List
from langchain_core.documents import Document
from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from langchain_mistralai import MistralAIEmbeddings

class EmbeddingModelsProtocol(Protocol):
    def configureModel(self, model_name: str):
        ...

def create_embedding_model(provider: str, model_name: str):
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
    elif (provider.lower() == "mistral"):
        print("Creating Mistral Embedding")
        return MistralModel().configureModel(
            model_name=model_name
        )
    
from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_experimental.open_clip.open_clip import OpenCLIPEmbeddings  # lazy-imported below
class HuggingFaceModel(EmbeddingModelsProtocol):
    def configureModel(self, model_name: str):
        if (model_name == "ViT-H-14"):
            print("In clip embedding:", model_name) #TODOANKIT - See how to handle CLIP Model embedding
            from langchain_experimental.open_clip.open_clip import OpenCLIPEmbeddings
            return OpenCLIPEmbeddings(model_name=model_name)
        return HuggingFaceEmbeddings(model_name=model_name)

from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import AzureOpenAIEmbeddings
class OpenAIModel(EmbeddingModelsProtocol):
    def configureModel(self, model_name: str):
        return AzureOpenAIEmbeddings(
            model=model_name,
            azure_endpoint=INGESTION_CONFIG["AZURE_OPENAI_ENDPOINT"],
            api_key=INGESTION_CONFIG["AZURE_OPENAI_API_KEY"],
            api_version=INGESTION_CONFIG["AZURE_OPENAI_API_VERSION"],
            azure_deployment=model_name
        )

class MistralModel(EmbeddingModelsProtocol):
    def configureModel(self, model_name: str):
        mistral_api_key = INGESTION_CONFIG.get("mistral_api_key")
        if not mistral_api_key:
            raise ValueError("Missing mistral_api_key in config or environment")
        
        return MistralAIEmbeddings(
            api_key=mistral_api_key,
            model=model_name
        )