from ingestion_pipleline.VectorStores.vector_store_protocol import VectorStoreProtocol
from typing import List, Dict, Any
from PIL import Image
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
import json
import os
import fitz  # PyMuPDF
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update this path as needed
import camelot
import csv
import io
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue

QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.stqye0XmMsoZUJ-oXkhD8a8UmlibnKSa_JfrRKWAll0"
QDRANT_CLUSTER_URL = "https://6c504361-ebbd-4169-ac71-56b10bc167d0.us-east4-0.gcp.cloud.qdrant.io:6333"
QDRANT_TIMEOUT = 120

class QDrantVectorDB(VectorStoreProtocol):
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_CLUSTER_URL, api_key=QDRANT_API_KEY, timeout=QDRANT_TIMEOUT)

    def create_collection(self, name: str, dimension: int) -> None:
        if (self.client.collection_exists(collection_name=name)):
            return
        result = self.client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE)
        )
        print("Results create collection: ", result)

    def delete_collection(self, name: str) -> bool:
        result = self.client.delete_collection(
            collection_name=name
        )
        print("Delete Success - ", result)
        return result


    def insert_docs(self, collection: str, documents: List[Document], chunkids: List[str], embedding: Embeddings|None):
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=collection,
            embedding=embedding,
        )
        added_ids = vector_store.add_documents(documents=documents, ids= chunkids)
        print("******************************8added ids******************************\n", added_ids)
   
    # def insert_vectors(self, collection: str, vectors, metadata):
    #     ids = [str(uuid.uuid4()) for _ in vectors]
    #     points = [
    #         PointStruct(id=id_, vector=vec, payload=meta)
    #         for id_, vec, meta in zip(ids, vectors, metadata)
    #     ]
    #     self.client.upsert(collection_name=collection, points=points)
    #     return ids

    # def query(self, collection, queryString, top_k=5, filters=None):
    #     qdrant_filters = None
    #     if filters:
    #         qdrant_filters = Filter(
    #             must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items()]
    #         )

    #     result = self.client.search(
    #         collection_name=collection,
    #         query_vector=vector,
    #         limit=top_k,
    #         query_filter=qdrant_filters
    #     )

    #     return [r.dict() for r in result]

    def delete(self, collection, ids):
        self.client.delete(collection_name=collection, points_selector=ids)

    def get_by_id(self, collection, id):
        result = self.client.retrieve(collection_name=collection, ids=[id])
        return result[0].dict() if result else None

    def test_retrieval(self, collection: str, embedding: Embeddings, query: str, topk: int) -> List[Document]:
        print("Inside Retrieval", collection, embedding)
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=collection,
            embedding=embedding,
        )
        # vector_store already initialized earlier (same collection & embedding)
        retriever = vector_store.as_retriever(
            search_kwargs={"k": topk}  # return top 3 most relevant chunks
        )
        print("Inside Retrieval", retriever)
        results = retriever.invoke(query)

        for i, doc in enumerate(results):
            print(f"\n--- Result {i+1} ---")
            print("Content:", doc.page_content)
            print("Metadata:", doc.metadata)
        
        return results