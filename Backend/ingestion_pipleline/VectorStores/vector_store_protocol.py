from typing import Protocol
from typing import List, Dict, Any
from langchain_core.documents import Document

class VectorStoreProtocol(Protocol):
    def create_collection(self, name: str, dimension: int) -> None:
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
    