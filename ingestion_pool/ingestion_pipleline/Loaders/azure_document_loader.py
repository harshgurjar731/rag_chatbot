import os
from typing import List, Optional
from pathlib import Path
from langchain_core.documents import Document
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from ingestion_pipleline.Loaders.loader_protocol import LoaderProtocol
from ingestion_pipleline.Config.Config import INGESTION_CONFIG

class AzureDocumentLoader(LoaderProtocol):
    def __init__(self):
        self.endpoint = INGESTION_CONFIG.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.key = INGESTION_CONFIG.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        
        if not self.endpoint or not self.key:
            raise ValueError("Azure Document Intelligence credentials not found. Please set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY in your environment.")

    def load(self, path: str) -> List[Document]:
        """
        Loads a document using Azure Document Intelligence (prebuilt-layout model).
        Extracts text and tables.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        client = DocumentIntelligenceClient(
            endpoint=self.endpoint, 
            credential=AzureKeyCredential(self.key)
        )

        with open(file_path, "rb") as f:
            poller = client.begin_analyze_document(
                "prebuilt-layout", 
                body=f,
                content_type="application/octet-stream"
            )
            result = poller.result()

        documents: List[Document] = []
        
        # Base metadata
        file_metadata = {
            "source": path,
            "filename": file_path.name,
            "file_size_kb": file_path.stat().st_size / 1024,
            "model": "prebuilt-layout"
        }

        # 1. Extract Text from Pages
        for page in result.pages:
            # Reconstruct page text from lines to maintain some structure equivalent to get_text()
            # Alternatively, we can use content from lines
            # Azure result.content contains full text, but page.lines gives us per-page text roughly.
            # Using page offset/length in result.content is more accurate if we want exact page text.
            
            # However, for simplicity and mimicking pdf_loader which often just gets text:
            # We can iterate through lines.
            
            page_text = ""
            if page.lines:
                page_text = "\n".join([line.content for line in page.lines])
            
            if page_text.strip():
                documents.append(Document(
                    page_content=page_text,
                    metadata={
                        **file_metadata,
                        "page_number": page.page_number,
                        "content_type": "text"
                    }
                ))

        # 2. Extract Tables
        if result.tables:
            for idx, table in enumerate(result.tables):
                # Convert table to a simplified markdown or CSV-like string representation
                # This is a basic representation. 
                
                table_content = []
                
                # We can construct a matrix if needed, but for now let's just dump cells
                # or try to format it.
                # Let's try to make a simple CSV representation.
                
                rows = table.row_count
                cols = table.column_count
                
                # Initialize grid
                grid = [["" for _ in range(cols)] for _ in range(rows)]
                
                for cell in table.cells:
                    r = cell.row_index
                    c = cell.column_index
                    # Handle spanning if necessary, but keep it simple for now
                    if r < rows and c < cols:
                        grid[r][c] = cell.content
                
                # Convert to string (CSV-ish)
                table_str = "\n".join([", ".join(row) for row in grid])
                
                # Find which page this table belongs to (using bounding regions of first cell)
                page_num = 1
                if table.bounding_regions:
                     page_num = table.bounding_regions[0].page_number

                documents.append(Document(
                    page_content=table_str,
                    metadata={
                        **file_metadata,
                        "page_number": page_num,
                        "content_type": "table",
                        "table_index": idx + 1
                    }
                ))

        return documents
