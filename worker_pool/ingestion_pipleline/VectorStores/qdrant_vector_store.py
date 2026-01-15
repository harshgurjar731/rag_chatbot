"""
Qdrant Vector Store Adapter.

This module implements the VectorStoreProtocol for Qdrant, providing support for
high-performance vector search, filtering, and cloud-based deployments.
"""
from ingestion_pipleline.VectorStores.vector_store_protocol import VectorStoreProtocol
from typing import List, Dict, Any, Optional
from PIL import Image
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from langchain_experimental.open_clip.open_clip import OpenCLIPEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings, OpenAIEmbeddings
import json
import os
import fitz  # PyMuPDF
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update this path as needed
import camelot
import csv
import io
import uuid
from qdrant_client import QdrantClient, models
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
import concurrent.futures

QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.cxNfWC0cJ3ekgS6AgWfaIH68vRu0apXHCnnIw7FzgjA"
#QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.stqye0XmMsoZUJ-oXkhD8a8UmlibnKSa_JfrRKWAll0"
#QDRANT_CLUSTER_URL = "https://6c504361-ebbd-4169-ac71-56b10bc167d0.us-east4-0.gcp.cloud.qdrant.io:6333"
QDRANT_CLUSTER_URL = "https://e53339bc-373e-425a-a9b2-fddccecdd40c.us-east-1-1.aws.cloud.qdrant.io:6333"
QDRANT_TIMEOUT = 120

class QDrantVectorDB(VectorStoreProtocol):
    """
    Qdrant Vector DB implementation.
    Manages connections to Qdrant Cloud or local instance and handles vector operations.
    """
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_CLUSTER_URL, api_key=QDRANT_API_KEY, timeout=QDRANT_TIMEOUT)

    def build_qdrant_filter(self, selected_files: List[str]) -> Optional[models.Filter]:
        """
        Build a Qdrant filter for a list of selected source files.
        If all files are selected, returns None (no filter needed).
        """
        # Skip filtering if all files are selected
        if not selected_files or len(selected_files) == 0:
            return None

        # Otherwise, build OR-style filter
        should_conditions = [
            models.FieldCondition(
                key="metadata.source",  # or "source_file" if not nested
                match=models.MatchValue(value=file_name)
            )
            for file_name in selected_files
        ]

        return models.Filter(should=should_conditions)
    

    def create_collection(self, name: str, embedding: HuggingFaceEmbeddings|OpenAIEmbeddings) -> None:
        """
        Create a new collection in Qdrant if it doesn't exist.
        
        Args:
            name (str): Collection name.
            embedding: Embedding model (used to determine vector dimension).
        """
        if (self.client.collection_exists(collection_name=name)):
            return
        dimension = len(embedding.embed_query("Test Query"))
        result = self.client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE)
        )
        self.client.create_payload_index(
            collection_name=name,
            field_name="metadata.source",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
        print("Results create collection: ", result)

    def delete_collection(self, name: str) -> bool:
        result = self.client.delete_collection(
            collection_name=name
        )
        print("Delete Success - ", result)
        return result


    def insert_docs(self, collection: str, documents: List[Document], chunkids: List[str], embedding: Embeddings|None):
        """
        Insert LangChain Documents into Qdrant using QdrantVectorStore wrapper.

        Args:
            collection (str): Collection name.
            documents (List[Document]): Documents to insert.
            chunkids (List[str]): IDs for the chunks.
            embedding (Embeddings): Embedding model.

        Returns:
            bool: True if insertion was successful.
        """
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=collection,
            embedding=embedding,
        )
        added_ids = vector_store.add_documents(documents=documents, ids= chunkids)
        return len(added_ids) > 0
   
    def insert_vectors(self, collection: str, vectors: List[List[float]], metadata: List[dict], chunk_ids: List[str]):
        points = [
            PointStruct(id=id_, vector=vec, payload=meta)
            for id_, vec, meta in zip(chunk_ids, vectors, metadata)
        ]
        result = self.client.upsert(collection_name=collection, points=points)
        return result.status == models.UpdateStatus.COMPLETED

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

    def test_retrieval(self, collection: str, embedding: Embeddings, queryList: List[str], topk: int, selected_docs: List[str] = []) -> List[List[Document]]:
        """
        Execute concurrent retrieval tests for multiple queries.

        Args:
            collection (str): Collection name.
            embedding (Embeddings): Embedding model.
            queryList (List[str]): List of query strings.
            topk (int): Number of results per query.
            selected_docs (List[str], optional): Filter by source filenames.

        Returns:
            List[List[Document]]: Results for each query.
        """
        # vector_store = QdrantVectorStore(
        #     client=self.client,
        #     collection_name=collection,
        #     embedding=embedding,
        # )

        filter = self.build_qdrant_filter(
            selected_files=selected_docs
        )

        search_kwargs = {"k": topk}
        if filter:
            search_kwargs["filter"] = filter

        queries_embedded = embedding.embed_documents(queryList)

        print("Embedded Queries: ", queries_embedded)

        def search(q_emb):
            return self.client.search(
                collection_name=collection,
                query_vector=q_emb,
                limit=topk,
                query_filter=filter
            )
        
        def scored_point_to_document(point):
            return Document(
                page_content=point.payload["page_content"],
                #metadata={k: v for k, v in point.payload.items() if k != "page_content"}
                metadata=point.payload["metadata"]
            )

        with concurrent.futures.ThreadPoolExecutor() as ex:
            all_results = list(ex.map(search, queries_embedded))

        documents_for_query: List[List[Document]] = []
        for i, result_set in enumerate(all_results):
            print(f"\nResults for query: {queryList[i]}")
            for point in result_set:
                print(
                    "ID:", point.id,
                    "Score:", point.score,
                    "Metadata:", point.payload    # <-- HERE
                )
            documents_for_query.append([scored_point_to_document(p) for p in result_set])


        print("Outside For Loop", len(documents_for_query))
        # # vector_store already initialized earlier (same collection & embedding)
        # retriever = vector_store.as_retriever(
        #     search_kwargs=search_kwargs
        #         # return top 3 most relevant chunks
        # )

        # def invoke_fetch_for_query(retriever, query):
        #     return retriever.invoke(query)

        # with concurrent.futures.ThreadPoolExecutor() as executor:
        #     futures = [executor.submit(invoke_fetch_for_query, retriever, q) for q in queryList]
        #     results = [f.result() for f in futures]


        # # results = retriever.invoke(query)
        # print("Vector DB retrieved query count - ", len(results))
        # print("First query chunk count", len(results[0]))
        
        return documents_for_query
    
    def retrieve_docs_for_embeddings(self, collection: str, embeddings:List[List[str]], topk: int, selected_docs: List[str] = []) -> List[List[Document]]:
        # vector_store = QdrantVectorStore(
        #     client=self.client,
        #     collection_name=collection,
        #     embedding=embedding,
        # )

        filter = self.build_qdrant_filter(
            selected_files=selected_docs
        )

        search_kwargs = {"k": topk}
        if filter:
            search_kwargs["filter"] = filter

        queries_embedded = embeddings

        print("Embedded Queries: ", queries_embedded)

        def search(q_emb):
            return self.client.search(
                collection_name=collection,
                query_vector=q_emb,
                limit=topk,
                query_filter=filter
            )
        
        def scored_point_to_document(point):
            return Document(
                page_content=point.payload.get("page_content", ""),
                #metadata={k: v for k, v in point.payload.items() if k != "page_content"}
                metadata=point.payload["metadata"]
            )

        with concurrent.futures.ThreadPoolExecutor() as ex:
            all_results = list(ex.map(search, queries_embedded))

        documents_for_query: List[List[Document]] = []
        for i, result_set in enumerate(all_results):
            # print(f"\nResults for query: {queryList[i]}")
            for point in result_set:
                print(
                    "ID:", point.id,
                    "Score:", point.score,
                    "Metadata:", point.payload    # <-- HERE
                )
            documents_for_query.append([scored_point_to_document(p) for p in result_set])


        print("Outside For Loop", len(documents_for_query))
        # # vector_store already initialized earlier (same collection & embedding)
        # retriever = vector_store.as_retriever(
        #     search_kwargs=search_kwargs
        #         # return top 3 most relevant chunks
        # )

        # def invoke_fetch_for_query(retriever, query):
        #     return retriever.invoke(query)

        # with concurrent.futures.ThreadPoolExecutor() as executor:
        #     futures = [executor.submit(invoke_fetch_for_query, retriever, q) for q in queryList]
        #     results = [f.result() for f in futures]


        # # results = retriever.invoke(query)
        # print("Vector DB retrieved query count - ", len(results))
        # print("First query chunk count", len(results[0]))
        
        return documents_for_query
    

    