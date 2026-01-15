"""
Document loading entry point.

This module acts as a factory/dispatcher to load documents using the appropriate
loader implementation based on file type.
"""
from sqlmodel import Session, select
from models.FileRecord import FileRecord
from database import get_session
from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
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
    """
    Load a document with metadata based on its type.

    Automatically determines the correct loader (PDF, Image, etc.) based on the
    document record's loaderType or file extension.

    Args:
        doc (DocumentRecord): The document metadata record.

    Returns:
        List[Document]: A list of loaded LangChain documents.
    
    Raises:
        ValueError: If loader type cannot be determined.
    """
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
                loader_type = doc.filePath.suffix[1:]
    
    if not loader_type:
        raise ValueError(f"Could not determine loader type for file: {doc.filePath}")
        return []

