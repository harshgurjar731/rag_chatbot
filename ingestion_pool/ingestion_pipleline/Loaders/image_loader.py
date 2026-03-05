from ingestion_pipleline.Loaders.loader_protocol import LoaderProtocol
from langchain_community.document_loaders import ImageCaptionLoader
from pathlib import Path
from typing import List
from langchain_core.documents import Document


class ImageLoader(LoaderProtocol):
    def load(self, path: str) -> List[Document]:
        file_path = Path(path)
        try:
            file_metadata = {
                "source": path,
                "content_type": "image",
                "file_size_kb": file_path.stat().st_size / 1024,
            }
            loader = ImageCaptionLoader(str(file_path))
            docs = loader.load()
            if docs:
                # Extract file-level metadata once
                docs[0].metadata.update(file_metadata)
            return docs
        except Exception as e:
            raise ValueError(f"Image processing error: {e}")