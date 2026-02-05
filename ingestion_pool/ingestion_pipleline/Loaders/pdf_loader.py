from ingestion_pipleline.Loaders.loader_protocol import LoaderProtocol
from langchain_community.document_loaders import UnstructuredImageLoader
from pathlib import Path
from typing import List
from PIL import Image
from langchain_core.documents import Document
import json
import os
# import PyMuPDF  # PyMuPDF
import pymupdf
import pytesseract
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Commented out for Linux/Docker
# In Docker, tesseract is in PATH (installed via apt/conda)
import camelot
import csv
import io

class PDFLoader(LoaderProtocol):
    def load(self, path: str) -> List[Document]:
        file_path = Path(path)
        document_list:List[Document] = []
        try:
            pdf_document = pymupdf.open(path)
            
            # Extract file-level metadata once
            file_metadata = {
                "source": path,
                "file_size_kb": file_path.stat().st_size / 1024,
                "total_pages": pdf_document.page_count
            }
            for page_num, page in enumerate(pdf_document):
                
                # 1. Extract and store general text
                text_content = page.get_text().strip()
                if text_content:
                    document_list.append(Document(
                        page_content=text_content,
                        metadata={**file_metadata, "page_number": page_num + 1, "content_type": "text"}
                    ))
                # 2. Extract tables and store as separate documents
                try:
                    tables = camelot.read_pdf(str(file_path), pages=str(page_num + 1), flavor='stream')
                    for table_idx, table in enumerate(tables):
                        table_string = table.df.to_string()
                        document_list.append(Document(
                            page_content=table_string,
                            metadata={**file_metadata, "page_number": page_num + 1, "content_type": "table", "table_index": table_idx + 1}
                        ))
                except Exception as e:
                    print(f"Warning: Failed to extract tables from page {page_num + 1}: {e}")
                
                # # 3. Extract and OCR images and store as separate documents
                # for img_idx, img in enumerate(page.get_images(full=True)):
                #     try:
                #         image_meta = extract_and_save_image(
                #             doc=pdf_document,
                #             img_info=img,
                #             page_num=page_num,
                #             file_id=file_id,
                #             text=text_content,
                #             output_dir=output_dir,
                #             stats=stats,
                #             mode="embed",
                #         )
                #         if image_meta:
                #             page_images_meta.append(image_meta)
                #     except Exception as e:
                #         print(f"⚠️ Embedded image error (page {page_num+1}): {e}")
                #         stats["errors"] += 1
                
                
                
                # image_list = page.get_images(full=True)
                # for img_index, img_info in enumerate(image_list):
                #     xref = img_info[0]
                #     base_image = pdf_document.extract_image(xref)
                #     image_bytes = base_image["image"]
                    
                #     try:
                #         ocr_text = pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)), lang='eng')
                #         if ocr_text.strip():
                #             document_list.append(Document(
                #                 page_content=ocr_text,
                #                 metadata={**file_metadata, "page_number": page_num + 1, "content_type": "ocr_image", "image_index": img_index + 1}
                #             ))
                #     except Exception as e:
                #         print(f"Warning: Failed to OCR image on page {page_num + 1}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load PDF file {file_path}: {e}")
        
        return document_list
