from typing import Protocol
from typing import List
from langchain_core.documents import Document

class SplitterProtocol(Protocol):
    """Protocol for document splitters."""
    def split_documents(self, loadedDocs: List[Document]) -> List[Document]:
        ...