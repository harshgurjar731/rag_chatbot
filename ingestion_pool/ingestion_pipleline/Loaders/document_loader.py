from sqlmodel import Session, select
from models.FileRecord import FileRecord
from database import get_session
# from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from models.datastore import DataStore
from models.FileRecord import DocumentRecord 
from pathlib import Path
from typing import List, Protocol
from PIL import Image
from langchain_core.documents import Document
from ingestion_pipleline.Loaders.pdf_loader import PDFLoader
from ingestion_pipleline.Loaders.image_loader import ImageLoader
from ingestion_pipleline.Loaders.loader_protocol import LoaderProtocol
import mimetypes

def load_document_with_metadata(doc: DocumentRecord) -> List[Document]:
    # Sanitize file path (Fix for legacy path issue)
    raw_path = str(doc.filePath)
    if "ingestion_pipleline/data_directory" in raw_path:
        sanitized_path = raw_path.replace("ingestion_pipleline/data_directory", "data_directory")
        print(f"[*] Sanitized path from {raw_path} to {sanitized_path}")
        doc.filePath = sanitized_path # Assign as STRING, not Path object

    # Automatically determine file type if not provided
    print("LoaderType: ", doc.loaderType)
    if doc.loaderType == 'pdf':
        loaded_documents = PDFLoader().load(doc.filePath)
        return loaded_documents
    elif doc.loaderType == 'img':
        return ImageLoader().load(doc.filePath)

    if not doc.loaderType:
        mime_type, _ = mimetypes.guess_type(doc.filePath)
        if mime_type:
            if 'image' in mime_type:
                loader_type = mime_type.split('/')[-1]
            elif 'text' in mime_type:
                loader_type = 'txt'
            elif 'pdf' in mime_type:
                loader_type = 'pdf'
            elif 'csv' in mime_type:
                loader_type = 'csv'
            else:
                loader_type = Path(doc.filePath).suffix[1:] # Ensure Path object for suffix
    
    if not loader_type:
        raise ValueError(f"Could not determine loader type for file: {doc.filePath}")
        return []

