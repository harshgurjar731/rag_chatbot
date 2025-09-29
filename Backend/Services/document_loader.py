from pathlib import Path
from typing import List
from langchain_core.documents import Document
import json
import os
from mistralai import Mistral
import fitz  # PyMuPDF
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
import camelot
import csv
import io



from langchain_community.document_loaders import (
    UnstructuredWordDocumentLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    TextLoader,
    CSVLoader,
    PyPDFLoader,
)

from config import CONFIG  # ✅ centralized config

# 1
# def save_docs_to_json(docs: List[Document], path: Path) -> None:
#     """Save list of Document objects into JSON format."""
#     try:
#         data = [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs]
#         with open(path, "w", encoding="utf-8") as f:
#             json.dump(data, f, ensure_ascii=False, indent=2)
#     except Exception as e:
#         raise RuntimeError(f"Failed to save JSON: {e}")


# def ocr_image_to_json(file_path: str) -> dict:             # replaced
#     """Upload an image to Mistral OCR and return cleaned text in JSON format."""
#     try:
#         # 🔑 Load API key from config
#         api_key = CONFIG["mistral_api_key"]
#         if not api_key:
#             return {"error": "Mistral API key not configured."}

#         client = Mistral(api_key=api_key)

#         # Ensure file exists
#         file_location = Path(file_path)
#         if not file_location.exists():
#             return {"error": f"File not found: {file_path}"}

#         content = file_location.read_bytes()
#         filename = file_location.name
#         print(f"Processing: {filename}")

#         # Upload file for OCR
#         uploaded = client.files.upload(
#             file={"file_name": filename, "content": content},
#             purpose="ocr"
#         )

#         file_id = getattr(uploaded, "id", None)
#         if not file_id:
#             return {"error": "File upload failed, no file_id returned."}

#         signed_url = client.files.get_signed_url(file_id=file_id).url

#         # Prompt for clean JSON output
#         messages = [
#             {
#                 "role": "user",
#                 "content": [
#                     {
#                         "type": "text",
#                         "text": """You are an OCR and data extraction assistant.

# Task:
# - Extract all readable text from the image.
# - Remove non-printable characters, escape sequences, and line breaks.
# - Combine the text into a single continuous paragraph.

# Output:
# - Respond ONLY in valid JSON with this format:

# {
#   "content": "<cleaned_text_in_one_paragraph>"
# }
# """
#                     },
#                     {
#                         "type": "document_url",
#                         "document_url": signed_url
#                     }
#                 ]
#             }
#         ]

#         # Run chat completion
#         response = client.chat.complete(model="mistral-small-latest", messages=messages)

#         # Safely extract text
#         if not response.choices:
#             return {"error": "No response returned from OCR."}

#         content_text = response.choices[0].message.content.strip()

#         # Remove ```json fences if present
#         if content_text.startswith("```"):
#             content_text = content_text.strip("`")  # remove backticks
#             content_text = content_text.replace("json\n", "", 1).replace("json", "", 1).strip()

#         # Ensure JSON parsing
#         try:
#             return json.loads(content_text)
#         except json.JSONDecodeError:
#             return {"content": content_text}

#     except Exception as e:
#         return {"error": str(e)}


# def load_file_with_old_loader(file_path: str, loader_type: str) -> List[Document]: # replaced
#     """Load files into LangChain Document objects and save them as JSON."""
#     file_path = Path(file_path)  # ✅ Ensure Path object always

#     # --- Image formats ---
#     if loader_type.lower() in ["jpg", "jpeg", "png", "webp"]:
#         ocr_result = ocr_image_to_json(str(file_path))
#         if "error" in ocr_result:
#             raise ValueError(f"OCR Error: {ocr_result['error']}")
#         document_list = [Document(page_content=ocr_result.get("content", ""), metadata={"source": str(file_path)})]
#         save_docs_to_json(document_list, file_path.with_suffix('.json'))
#         return document_list

#     # --- Documents ---
#     loader = None
#     if loader_type == "pdf":
#         loader = PyPDFLoader(str(file_path))
#     elif loader_type == "txt":
#         # ✅ autodetect_encoding fallback safe
#         try:
#             loader = TextLoader(str(file_path), encoding="utf-8", autodetect_encoding=True)
#         except TypeError:
#             loader = TextLoader(str(file_path), encoding="utf-8")
#     elif loader_type == "docx":
#         loader = UnstructuredWordDocumentLoader(str(file_path))
#     elif loader_type == "html":
#         loader = UnstructuredHTMLLoader(str(file_path))
#     elif loader_type == "md":
#         loader = UnstructuredMarkdownLoader(str(file_path))
#     elif loader_type == "csv":
#         loader = CSVLoader(str(file_path))
#     else:
#         raise ValueError(f"Unsupported loader type: {loader_type}")

#     try:
#         document_list = loader.load()
#         save_docs_to_json(document_list, file_path.with_suffix('.json'))
#         return document_list
#     except Exception as e:
#         raise RuntimeError(f"Failed to load file {file_path}: {e}")


# 2
# # Assuming these functions are defined elsewhere
# def ocr_image_with_tesseract(image_path: str) -> str:
#     """Perform OCR on an image using pytesseract."""
#     try:
#         from PIL import Image
#         text = pytesseract.image_to_string(Image.open(image_path), lang='hin+eng+fra+deu+ita+spa+por+rus+jpn+kor+chi_sim')
#         return text
#     except Exception as e:
#         raise RuntimeError(f"Tesseract OCR failed on {image_path}: {e}")



# def load_file_with_loader(file_path: str, loader_type: str) -> List[Document]:
#     """
#     Loads various file types into LangChain Document objects using
#     Tesseract for images, PyMuPDF/Camelot for PDFs, and native Python libraries
#     for other document types.
#     """
#     file_path = Path(file_path)

#     document_list = []
#     content = ""
    
#     # --- Image Formats (using Pytesseract) ---
#     if loader_type.lower() in ["jpg", "jpeg", "png", "webp"]:
#         try:
#             content = ocr_image_with_tesseract(str(file_path))
#             document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
#         except RuntimeError as e:
#             raise ValueError(f"Image processing error: {e}")

#     # --- PDF Documents (using PyMuPDF and Camelot) ---
#     elif loader_type.lower() == "pdf":
#         try:
#             # 1. Extract tables with Camelot
#             tables = camelot.read_pdf(str(file_path), pages='all', flavor='stream')
#             table_content = ""
#             if tables:
#                 for table in tables:
#                     table_content += table.df.to_string() + "\n\n"

#             # 2. Extract general text with PyMuPDF
#             pdf_document = fitz.open(file_path)
#             full_text = ""
#             for page in pdf_document:
#                 full_text += page.get_text()

#             # Combine and create a single document for simplicity
#             combined_content = f"Tables:\n{table_content}\n\nText:\n{full_text}"
#             document_list.append(Document(page_content=combined_content, metadata={"source": str(file_path)}))

#         except Exception as e:
#             raise RuntimeError(f"Failed to load PDF file {file_path}: {e}")

#     # --- Other Document Types (using native Python) ---
#     elif loader_type.lower() == "txt":
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#             document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
#         except Exception as e:
#             raise RuntimeError(f"Failed to load TXT file {file_path}: {e}")
            
#     elif loader_type.lower() == "html":
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#             document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
#         except Exception as e:
#             raise RuntimeError(f"Failed to load HTML file {file_path}: {e}")

#     elif loader_type.lower() == "md":
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#             document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
#         except Exception as e:
#             raise RuntimeError(f"Failed to load Markdown file {file_path}: {e}")

#     elif loader_type.lower() == "csv":
#         try:
#             content = ""
#             with open(file_path, newline='', encoding='utf-8') as csvfile:
#                 reader = csv.reader(csvfile)
#                 for row in reader:
#                     content += ', '.join(row) + '\n'
#             document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
#         except Exception as e:
#             raise RuntimeError(f"Failed to load CSV file {file_path}: {e}")

#     else:
#         raise ValueError(f"Unsupported loader type: {loader_type}")

#     # Save documents to JSON
#     if document_list:
#         save_docs_to_json(document_list, file_path.with_suffix('.json'))
    
#     return document_list




import os
import io
import json
from pathlib import Path
from typing import List
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import camelot
import csv
from langchain_core.documents import Document


def save_docs_to_json(docs: List[Document], path: Path) -> None:
    """Save list of Document objects into JSON format."""
    try:
        data = [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise RuntimeError(f"Failed to save JSON: {e}")


def ocr_image_with_tesseract(image_path: str) -> str:
    """Perform OCR on an image using pytesseract."""
    try:
        from PIL import Image
        # Using a comprehensive set of languages for better OCR accuracy
        text = pytesseract.image_to_string(Image.open(image_path), lang='hin+eng+fra+deu+ita+spa+por+rus+jpn+kor+chi_sim')
        return text
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed on {image_path}: {e}")


def load_file_with_loader(file_path: str, loader_type: str) -> List[Document]:
    """
    Loads various file types into LangChain Document objects using
    Tesseract for images, PyMuPDF/Camelot for PDFs, and native Python libraries
    for other document types, including embedded images in PDFs.
    """
    file_path = Path(file_path)

    document_list = []
    content = ""
   
    # --- Image Formats (using Pytesseract) ---
    if loader_type.lower() in ["jpg", "jpeg", "png", "webp"]:
        try:
            content = ocr_image_with_tesseract(str(file_path))
            document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
        except RuntimeError as e:
            raise ValueError(f"Image processing error: {e}")

    # --- PDF Documents (using PyMuPDF and Camelot) ---
    elif loader_type.lower() == "pdf":
        try:
            pdf_document = fitz.open(file_path)
            full_content = ""
           
            for page_num, page in enumerate(pdf_document):
                # 1. Extract general text with PyMuPDF
                full_content += page.get_text() + "\n\n"

                # 2. Extract tables with Camelot (if needed)
                try:
                    tables = camelot.read_pdf(str(file_path), pages=str(page_num + 1), flavor='stream')
                    if tables:
                        for table in tables:
                            full_content += f"Table on page {page_num + 1}:\n"
                            full_content += table.df.to_string() + "\n\n"
                except Exception as e:
                    print(f"Warning: Failed to extract tables from page {page_num + 1}: {e}")
                    pass # Continue processing even if table extraction fails

                # 3. Extract and OCR images from the page
                image_list = page.get_images(full=True)
                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                   
                    try:
                        # Process image data directly from memory
                        ocr_text = pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)), lang='hin+eng+fra+deu+ita+spa+por+rus+jpn+kor+chi_sim')
                        full_content += f"OCR from image on page {page_num + 1}:\n"
                        full_content += ocr_text + "\n\n"
                       
                    except Exception as e:
                        print(f"Warning: Failed to OCR image on page {page_num + 1}: {e}")
           
            document_list.append(Document(page_content=full_content, metadata={"source": str(file_path)}))

        except Exception as e:
            raise RuntimeError(f"Failed to load PDF file {file_path}: {e}")

    # --- Other Document Types (using native Python) ---
    elif loader_type.lower() == "txt":
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
        except Exception as e:
            raise RuntimeError(f"Failed to load TXT file {file_path}: {e}")
           
    elif loader_type.lower() == "html":
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
        except Exception as e:
            raise RuntimeError(f"Failed to load HTML file {file_path}: {e}")

    elif loader_type.lower() == "md":
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
        except Exception as e:
            raise RuntimeError(f"Failed to load Markdown file {file_path}: {e}")

    elif loader_type.lower() == "csv":
        try:
            content = ""
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    content += ', '.join(row) + '\n'
            document_list.append(Document(page_content=content, metadata={"source": str(file_path)}))
        except Exception as e:
            raise RuntimeError(f"Failed to load CSV file {file_path}: {e}")

    else:
        raise ValueError(f"Unsupported loader type: {loader_type}")

    # Save documents to JSON
    if document_list:
        save_docs_to_json(document_list, file_path.with_suffix('.json'))
   
    return document_list