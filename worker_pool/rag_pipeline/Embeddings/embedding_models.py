from typing import Protocol
from typing import List
from langchain_core.documents import Document
from rag_pipeline.Config.rag_config import RAG_CONFIG

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
    
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_experimental.open_clip.open_clip import OpenCLIPEmbeddings
class HuggingFaceModel(EmbeddingModelsProtocol):
    def configureModel(self, model_name: str):
        if (model_name == "ViT-H-14"):
            print("In clip embedding:", model_name) #TODOANKIT - See how to handle CLIP Model embedding
            return OpenCLIPEmbeddings(model_name=model_name)
        return HuggingFaceEmbeddings(model_name=model_name)

from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import AzureOpenAIEmbeddings
class OpenAIModel(EmbeddingModelsProtocol):
    def configureModel(self, model_name: str):
        return AzureOpenAIEmbeddings(
            model=model_name,
            azure_endpoint=RAG_CONFIG["AZURE_OPENAI_ENDPOINT"],
            api_key=RAG_CONFIG["AZURE_OPENAI_API_KEY"],
            api_version=RAG_CONFIG["AZURE_OPENAI_API_VERSION"],
            azure_deployment=model_name
        )