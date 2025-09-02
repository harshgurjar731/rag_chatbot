from pathlib import Path
from typing import List
from langchain_core.documents import Document
import json
import os
from mistralai import Mistral

from langchain_community.document_loaders import (
    UnstructuredPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    TextLoader,
    CSVLoader,
    PyPDFLoader,
)


def save_docs_to_json(docs: List[Document], path: Path) -> None:
    """Save list of Document objects into JSON format."""
    try:
        data = [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise RuntimeError(f"Failed to save JSON: {e}")


def ocr_image_to_json(file_path: str) -> dict:
    """Upload an image to Mistral OCR and return cleaned text in JSON format."""
    try:
        # 🔑 Read API key safely
        api_key = "vIYwB5eYxQdtzjAseppl6don2TDBNOpe"
        client = Mistral(api_key=api_key)

        # Ensure file exists
        file_location = Path(file_path)
        if not file_location.exists():
            return {"error": f"File not found: {file_path}"}

        content = file_location.read_bytes()
        filename = file_location.name
        print(f"Processing: {filename}")

        # Upload file for OCR
        uploaded = client.files.upload(
            file={"file_name": filename, "content": content},
            purpose="ocr"
        )

        file_id = getattr(uploaded, "id", None)
        if not file_id:
            return {"error": "File upload failed, no file_id returned."}

        signed_url = client.files.get_signed_url(file_id=file_id).url

        # Prompt for clean JSON output
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """You are an OCR and data extraction assistant.

Task:
- Extract all readable text from the image.
- Remove non-printable characters, escape sequences, and line breaks.
- Combine the text into a single continuous paragraph.

Output:
- Respond ONLY in valid JSON with this format:

{
  "content": "<cleaned_text_in_one_paragraph>"
}
"""
                    },
                    {
                        "type": "document_url",
                        "document_url": signed_url
                    }
                ]
            }
        ]

        # Run chat completion
        response = client.chat.complete(model="mistral-small-latest", messages=messages)

        # Safely extract text
        if not response.choices:
            return {"error": "No response returned from OCR."}

        content_text = response.choices[0].message.content.strip()

        # Remove ```json fences if present
        if content_text.startswith("```"):
            content_text = content_text.strip("`")  # remove backticks
            content_text = content_text.replace("json\n", "", 1).replace("json", "", 1).strip()

        # Ensure JSON parsing
        try:
            return json.loads(content_text)
        except json.JSONDecodeError:
            return {"content": content_text}

    except Exception as e:
        return {"error": str(e)}


def load_file_with_loader(file_path: str, loader_type: str) -> List[Document]:
    """Load files into LangChain Document objects and save them as JSON."""
    file_path = Path(file_path)  # ✅ Ensure Path object always

    # --- Image formats ---
    if loader_type.lower() in ["jpg", "jpeg", "png", "webp"]:
        ocr_result = ocr_image_to_json(str(file_path))
        if "error" in ocr_result:
            raise ValueError(f"OCR Error: {ocr_result['error']}")
        document_list = [Document(page_content=ocr_result.get("content", ""), metadata={"source": str(file_path)})]
        save_docs_to_json(document_list, file_path.with_suffix('.json'))
        return document_list

    # --- Documents ---
    loader = None
    if loader_type == "pdf":
        loader = PyPDFLoader(str(file_path))
    elif loader_type == "txt":
        # ✅ autodetect_encoding is not always available → fallback safe
        try:
            loader = TextLoader(str(file_path), encoding="utf-8", autodetect_encoding=True)
        except TypeError:
            loader = TextLoader(str(file_path), encoding="utf-8")
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

    try:
        document_list = loader.load()
        save_docs_to_json(document_list, file_path.with_suffix('.json'))
        return document_list
    except Exception as e:
        raise RuntimeError(f"Failed to load file {file_path}: {e}")
