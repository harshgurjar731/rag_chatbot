# Backend/Services/chunking_service.py

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

from langchain_core.documents import Document

def load_docs_from_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Document(page_content=d["content"], metadata=d["metadata"]) for d in data]

def save_chunks_to_json(chunks: list[Document], output_path: Path):
    # Convert Document objects to serializable format
    serializable = [
        {"content": chunk.page_content, "metadata": chunk.metadata}
        for chunk in chunks
    ]
    # Save to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

# def chunk_documents(
#     docs: List[Document],
#     method: str = "recursive",
#     chunk_size: int = 512,
#     chunk_overlap: int = 50,
#     file_path: str = None
# ) -> List[Document]:
#     """
#     Split documents using the specified chunking method.

#     Args:
#         docs: List of langchain Document objects to split.
#         method: Chunking method ('recursive', 'character', 'markdown', 'token').
#         chunk_size: Max number of characters or tokens per chunk.
#         chunk_overlap: Number of characters/tokens to overlap between chunks.

#     Returns:
#         List of chunked Document objects.
#     """

#     method = method.lower()

#     if method == "character":
#         splitter = CharacterTextSplitter(
#             chunk_size=chunk_size,
#             chunk_overlap=chunk_overlap
#         )
#     elif method == "recursive":
#         splitter = RecursiveCharacterTextSplitter(
#             chunk_size=chunk_size,
#             chunk_overlap=chunk_overlap
#         )
#     elif method == "markdown":
#         splitter = MarkdownHeaderTextSplitter(
#             headers_to_split_on=[("#", "heading")]  # Customize if needed
#         )
#     elif method == "token":
#         splitter = TokenTextSplitter(
#             chunk_size=chunk_size,
#             chunk_overlap=chunk_overlap
#         )
#     else:
#         raise ValueError(f"Unsupported chunking method: {method}")
#     doucment_chunks = splitter.split_documents(docs)
#     return doucment_chunks
#     #return splitter.split_documents(docs)


def chunk_documents(
    docs: List[Document],
    method: str = "recursive",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    file_path: str = None
) -> List[Document]:
    """
    Split documents using the specified chunking method while preserving source metadata.
    If no source is found, it will use file_path as the source.

    Args:
        docs: List of langchain Document objects to split.
        method: Chunking method ('recursive', 'character', 'markdown', 'token').
        chunk_size: Max number of characters or tokens per chunk.
        chunk_overlap: Number of characters/tokens to overlap between chunks.
        file_path: Optional path to the source file (used if no 'source' metadata exists).

    Returns:
        List of chunked Document objects with source metadata retained.
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
            headers_to_split_on=[("#", "heading")]  # Customize if needed
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
        # If 'source' exists in original, keep it
        if "source" not in chunk.metadata or not chunk.metadata["source"]:
            # If no source, use provided file_path as fallback
            if file_path:
                chunk.metadata["source"] = file_path
            else:
                chunk.metadata["source"] = "Unknown source"

    return document_chunks