from sqlmodel import Session, select
from models.FileRecord import FileRecord
from database import get_session
# from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
from models.datastore import DataStore
from models.FileRecord import DocumentRecord 
from pathlib import Path
from typing import List, Protocol
from PIL import Image
from langchain_core.documents import Document
from ingestion_pipleline.Loaders.pdf_loader import PDFLoader
from ingestion_pipleline.Loaders.image_loader import ImageLoader
from ingestion_pipleline.Loaders.loader_protocol import LoaderProtocol
from ingestion_pipleline.Loaders.azure_document_loader import AzureDocumentLoader
import mimetypes

def load_document_with_metadata(doc: DocumentRecord) -> List[Document]:
    # Sanitize file path (Fix for Docker/Native mismatched paths + fuzzy matching)
    raw_path = str(doc.filePath)
    
    import os
    import re
    from ingestion_pipleline.Config.Config import _data_dir as DATA_DIRECTORY
    
    if not os.path.exists(raw_path):
        rel_path = raw_path.replace("\\", "/")
        if "data_directory/" in rel_path:
            rel_path = rel_path.split("data_directory/")[-1]
            
        candidate = os.path.join(DATA_DIRECTORY, rel_path)
        if os.path.exists(candidate):
            doc.filePath = candidate
            print(f"[*] Resolved mismatched path to {candidate}")
        else:
            filename = os.path.basename(rel_path)
            target_fuzzy = re.sub(r'[^a-zA-Z0-9\.]', '', filename).lower()
            print(f"[*] Path not found locally. Searching recursively for fuzzy match '{target_fuzzy}' in {DATA_DIRECTORY}...")
            
            found = False
            for root_dir, _, files in os.walk(DATA_DIRECTORY):
                for file in files:
                    file_fuzzy = re.sub(r'[^a-zA-Z0-9\.]', '', file).lower()
                    if target_fuzzy == file_fuzzy or (len(target_fuzzy) > 10 and target_fuzzy[:15] in file_fuzzy):
                        doc.filePath = os.path.join(root_dir, file)
                        print(f"[*] Found {filename} recursively at {doc.filePath}")
                        found = True
                        break
                if found:
                    break

    # Automatically determine file type if not provided
    print("LoaderType: ", doc.loaderType)
    if doc.loaderType == 'pdf':
        from ingestion_pipleline.Config.Config import INGESTION_CONFIG
        pdf_loader_type = INGESTION_CONFIG.get("pdf_loader_type", "local")
        
        if pdf_loader_type == "azure-document-intelligence":
            from ingestion_pipleline.Loaders.azure_document_loader import AzureDocumentLoader
            print(f"[*] Using AzureDocumentLoader for {doc.filePath}")
            return AzureDocumentLoader().load(doc.filePath)
        else:
            print(f"[*] Using local PDFLoader for {doc.filePath}")
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
                loader_type = Path(doc.filePath).suffix[1:] # Ensure Path object for suffix
    
    if not loader_type:
        raise ValueError(f"Could not determine loader type for file: {doc.filePath}")
        return []

