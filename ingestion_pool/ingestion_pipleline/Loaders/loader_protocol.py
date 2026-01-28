from typing import Protocol
from typing import List
from langchain_core.documents import Document

class LoaderProtocol(Protocol):
    def load(self, path: str) -> List[Document]:
        ...