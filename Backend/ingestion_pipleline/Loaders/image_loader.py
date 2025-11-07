from ingestion_pipleline.Loaders.loader_protocol import LoaderProtocol
from pathlib import Path
from typing import List
from PIL import Image
from langchain_core.documents import Document
import json
import os
import fitz  # PyMuPDF
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update this path as needed
import camelot
import csv
import pymupdf
import io

def ocr_image_with_tesseract(image_path: str) -> str:
    """Perform OCR on an image using pytesseract."""
    try:
        text = pytesseract.image_to_string(Image.open(image_path), lang='eng')
        return text
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed on {image_path}: {e}")

class ImageLoader(LoaderProtocol):
    def load(self, path: str) -> List[Document]:
        try:
            print("In ImageLoader")
            file_path = Path(path)
            document_list:List[Document] = []
            content = ocr_image_with_tesseract(str(file_path))
            print("1", content)
            if content.strip():
                document_list.append(Document(
                    page_content=content, 
                    metadata={
                        "source": str(file_path),
                        "content_type": "ocr_image",
                        "file_size_kb": file_path.stat().st_size / 1024
                    }
                ))
        except RuntimeError as e:
            raise ValueError(f"Image processing error: {e}")
        
        return document_list