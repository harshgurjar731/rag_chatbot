from typing import Protocol
from typing import List
from langchain_core.documents import Document

class LoaderProtocol(Protocol):
    """Protocol defining the interface for document loaders."""
    def load(self, path: str) -> List[Document]:
        """
        Load documents from a file path.

        Args:
            path (str): Absolute file path.

        Returns:
            List[Document]: Loaded documents.
        """
        ...