from typing import Protocol
from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings, OpenAIEmbeddings

class VectorStoreProtocol(Protocol):
    def create_collection(self, name: str, embedding: HuggingFaceEmbeddings|OpenAIEmbeddings) -> None:
        ...

    def delete_collection(self, name: str) -> bool:
        ...
    
    def insert_vectors(self, collection: str, vectors: List[List[float]], metadata: List[Dict[str, Any]]) -> List[str]:
        ...
    
    def query(self, collection: str, vector: List[float], top_k: int = 5, filters: Dict[str, Any] = None) -> List[Dict]:
        ...
    
    def delete(self, collection: str, ids: List[str]) -> None:
        ...

    def get_by_id(self, collection: str, id: str) -> Dict:
        ...
    
    def insert_docs(self, collection: str, documents: List[Document], chunkids: List[str], embedding: HuggingFaceEmbeddings|OpenAIEmbeddings) -> bool:
        ...
    
    def test_retrieval(self, collection: str, embedding: HuggingFaceEmbeddings|OpenAIEmbeddings, queryList: List[str], topk: int, selected_docs: List[str] = []) -> List[List[Document]]:
        ...

    def retrieve_docs_for_embeddings(self, collection: str, embeddings: List[List[float]], topk: int, selected_docs: List[str] = []) -> List[List[Document]]:
        ...
    