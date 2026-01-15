"""
Service for chunking text documents into smaller pieces.

This module provides functionality to split documents using various methods
(character, recursive, markdown, token) and manage document loading/saving.
"""

from typing import List
from langchain_core.documents import Document
import json
from pathlib import Path
from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    TokenTextSplitter,
)
from config import CONFIG  # ✅ Use centralized config

def load_docs_from_json(path: Path) -> List[Document]:
    """
    Loads documents from a JSON file.

    Args:
        path (Path): Path to the JSON file.

    Returns:
        List[Document]: A list of LangChain Document objects.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Document(page_content=d["content"], metadata=d["metadata"]) for d in data]

def save_chunks_to_json(chunks: List[Document], output_path: Path):
    """
    Saves a list of document chunks to a JSON file.

    Args:
        chunks (List[Document]): List of document chunks to save.
        output_path (Path): Destination path for the JSON file.
    """
    serializable = [
        {"content": chunk.page_content, "metadata": chunk.metadata}
        for chunk in chunks
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

def chunk_documents(
    docs: List[Document],
    method: str = CONFIG["default_chunk_method"],   # ✅ from config
    chunk_size: int = CONFIG["default_chunk_size"], # ✅ from config
    chunk_overlap: int = CONFIG["default_chunk_overlap"], # ✅ from config
    file_path: str = None
) -> List[Document]:
    """
    Split documents using the specified chunking method while preserving source metadata.
    Defaults come from .env via config.py.
    """

    method = method.lower()

    if method == "character":
        splitter = CharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    elif method == "recursive":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    elif method == "markdown":
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "heading")]
        )
    elif method == "token":
        splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    else:
        raise ValueError(f"Unsupported chunking method: {method}")

    # ✅ Split documents
    document_chunks = splitter.split_documents(docs)

    # ✅ Preserve or set 'source' metadata
    for chunk in document_chunks:
        if "source" not in chunk.metadata or not chunk.metadata["source"]:
            if file_path:
                chunk.metadata["source"] = file_path
            else:
                chunk.metadata["source"] = "Unknown source"

    return document_chunks
