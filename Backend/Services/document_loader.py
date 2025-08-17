from pathlib import Path
from typing import List
from langchain_core.documents import Document
import json
from pathlib import Path

from langchain_community.document_loaders import (
    UnstructuredPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    TextLoader,
    CSVLoader,
    PyPDFLoader,
)



def save_docs_to_json(docs, path: Path):
    data = [
        {"content": doc.page_content, "metadata": doc.metadata}
        for doc in docs
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def load_file_with_loader(file_path: str, loader_type: str):
    file_path = Path(file_path)  # ✅ ensure Path object always

    if loader_type == "pdf":
        loader = PyPDFLoader(str(file_path))
    elif loader_type == "txt":
        loader = TextLoader(str(file_path), encoding="utf-8", autodetect_encoding=True)
    elif loader_type == "docx":
        loader = UnstructuredWordDocumentLoader(str(file_path))
    elif loader_type == "html":
        loader = UnstructuredHTMLLoader(str(file_path))
    elif loader_type == "md":
        loader = UnstructuredMarkdownLoader(str(file_path))
    elif loader_type == "csv":
        loader = CSVLoader(str(file_path))
    else:
        raise ValueError(f"Unsupported loader type: {loader_type}")

    document_list = loader.load()
    save_docs_to_json(document_list, file_path.with_suffix('.json'))
    return document_list
