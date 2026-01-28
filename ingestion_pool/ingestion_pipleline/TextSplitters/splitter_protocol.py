from typing import Protocol
from typing import List
from langchain_core.documents import Document

class SplitterProtocol(Protocol):
    def split_documents(self, loadedDocs: List[Document]) -> List[Document]:
        ...