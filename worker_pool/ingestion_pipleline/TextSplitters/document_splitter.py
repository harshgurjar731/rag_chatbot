"""
Document splitting (chunking) logic.

This module processes loaded documents and splits them into smaller chunks
suitable for embedding, using various LangChain splitter implementations.
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
from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    TokenTextSplitter,
)
from ingestion_pipleline.Config.Config import INGESTION_CONFIG

def split_document(doc: DocumentRecord, loadedDocs: List[Document]) -> List[Document]:
    """
    Split a document into chunks based on the specified method.

    Supports 'character', 'recursive', 'markdown', and 'token' based splitting.
    Also ensures metadata like 'source' is preserved or set on chunks.

    Args:
        doc (DocumentRecord): Document metadata record (contains split config).
        loadedDocs (List[Document]): The loaded document(s) to split.

    Returns:
        List[Document]: The list of chunked documents.
    """
    method = doc.textSplitMethod.lower()
    print("In Splitter")
    if method == "character".lower():
        print("In Character", doc.chunkSize, doc.chunkOverlap)
        splitter = CharacterTextSplitter(
            chunk_size=doc.chunkSize or INGESTION_CONFIG["default_chunk_size"],
            chunk_overlap=doc.chunkOverlap or INGESTION_CONFIG["default_chunk_overlap"]
        )
    elif method == "recursive".lower():
        print("In Recursive", doc.chunkSize, doc.chunkOverlap)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=doc.chunkSize or INGESTION_CONFIG["default_chunk_size"],
            chunk_overlap=doc.chunkOverlap or INGESTION_CONFIG["default_chunk_overlap"]
        )
    elif method == "markdown":
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "heading")]
        )
    elif method == "token":
        splitter = TokenTextSplitter(
            chunk_size=doc.chunkSize or INGESTION_CONFIG["default_chunk_size"],
            chunk_overlap=doc.chunkOverlap or INGESTION_CONFIG["default_chunk_overlap"]
        )
    else:
       return loadedDocs

    # ✅ Split documents
    document_chunks = splitter.split_documents(loadedDocs)
    print("In Splitter before Metadata")
    # ✅ Preserve or set 'source' metadata
    for chunk in document_chunks:
        if "source" not in chunk.metadata or not chunk.metadata["source"]:
            if doc.filePath:
                chunk.metadata["source"] = doc.filePath
            else:
                chunk.metadata["source"] = "Unknown source"
    print("In Splitter after Metadata", document_chunks.count)
    return document_chunks
