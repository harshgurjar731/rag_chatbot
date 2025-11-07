from typing import Protocol
from typing import List
from langchain_core.documents import Document

class EmbeddingModelsProtocol(Protocol):
    def configureModel(self):
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
class HuggingFaceModel(EmbeddingModelsProtocol):
    def configureModel(self, model_name: str):
        return HuggingFaceEmbeddings(model_name=model_name)

AZURE_OPENAI_ENDPOINT = "https://rupalitest.openai.azure.com/"
AZURE_OPENAI_API_KEY = "GHjMpAUMjqSYSuVPp4oHkI1bhAAsWQlihigch0uTWxoCI0kdRhQdJQQJ99BKACYeBjFXJ3w3AAABACOGu0tn"

from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import AzureOpenAIEmbeddings
class OpenAIModel(EmbeddingModelsProtocol):
    def configureModel(self, model_name: str):
        print("Model Name: ", model_name)
        return AzureOpenAIEmbeddings(
            model=model_name,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
            azure_deployment=model_name
        )