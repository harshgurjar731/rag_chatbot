from ingestion_pipleline.Loaders.loader_protocol import LoaderProtocol
from langchain_community.document_loaders import ImageCaptionLoader
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
        file_path = Path(path)
        try:
            file_metadata = {
                "source": path,
                "content_type": "image",
                "file_size_kb": file_path.stat().st_size / 1024,
            }
            loader = ImageCaptionLoader(file_path)
            docs = loader.load()
            # Extract file-level metadata once
            docs[0].metadata.update(file_metadata)
            return docs
        except RuntimeError as e:
            raise ValueError(f"Image processing error: {e}")
        
        return document_list