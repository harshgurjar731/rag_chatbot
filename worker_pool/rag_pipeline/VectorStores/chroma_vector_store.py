from rag_pipeline.VectorStores.vector_store_protocol import VectorStoreProtocol
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings, OpenAIEmbeddings
import os

CHROMA_PERSIST_DIRECTORY = "./chroma_db"

class ChromaVectorDB(VectorStoreProtocol):
    def __init__(self, persist_directory: str = CHROMA_PERSIST_DIRECTORY):
        chroma_host = os.getenv("CHROMA_SERVER_HOST")
        chroma_port = os.getenv("CHROMA_SERVER_PORT", "8000")
        
        if chroma_host:
             # Use HTTP client for containerized ChromaDB
            self.client = chromadb.HttpClient(host=chroma_host, port=int(chroma_port))
            print(f"Connected to ChromaDB at {chroma_host}:{chroma_port}")
        else:
            # Fallback to local persistence
            self.client = chromadb.PersistentClient(path=persist_directory)

    def create_collection(self, name: str, embedding: HuggingFaceEmbeddings | OpenAIEmbeddings) -> None:
        # Note: Chroma handles embeddings differently if using its built-in functions, 
        # but here we follow the protocol where embeddings might be handled externally or via this instance.
        self.client.get_or_create_collection(name=name)
        print(f"Collection '{name}' created or already exists in Chroma.")

    def delete_collection(self, name: str) -> bool:
        try:
            self.client.delete_collection(name=name)
            print(f"Collection '{name}' deleted from Chroma.")
            return True
        except Exception as e:
            print(f"Error deleting collection '{name}': {e}")
            return False

    def insert_vectors(self, collection: str, vectors: List[List[float]], metadata: List[Dict[str, Any]], ids: List[str] = None) -> List[str]:
        chroma_coll = self.client.get_collection(name=collection)
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        
        # Chroma expects metadata to be flat (Dict[str, str | int | float | bool])
        # We might need to flatten or JSON stringify nested metadata if necessary.
        processed_metadata = []
        for meta in metadata:
            flat_meta = {}
            for k, v in meta.items():
                if isinstance(v, (dict, list)):
                    flat_meta[k] = str(v)
                else:
                    flat_meta[k] = v
            processed_metadata.append(flat_meta)

        chroma_coll.add(
            embeddings=vectors,
            metadatas=processed_metadata,
            ids=ids
        )
        return ids

    def query(self, collection: str, vector: List[float], top_k: int = 5, filters: Dict[str, Any] = None) -> List[Dict]:
        chroma_coll = self.client.get_collection(name=collection)
        
        where_filter = None
        if filters:
            # Chroma 'where' filter: {"metadata_field": "value"} or complex operators
            # Here we assume simple equality filters for compatibility with common protocol usage
            if len(filters) == 1:
                where_filter = filters
            else:
                where_filter = {"$and": [{k: v} for k, v in filters.items()]}

        results = chroma_coll.query(
            query_embeddings=[vector],
            n_results=top_k,
            where=where_filter
        )

        # Reformat Chroma results to List[Dict] matching expected protocol output
        formatted_results = []
        if results['ids']:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "score": results['distances'][0][i] if 'distances' in results else None,
                    "metadata": results['metadatas'][0][i],
                    "document": results['documents'][0][i] if results['documents'] else None
                })
        return formatted_results

    def delete(self, collection: str, ids: List[str]) -> None:
        chroma_coll = self.client.get_collection(name=collection)
        chroma_coll.delete(ids=ids)

    def get_by_id(self, collection: str, id: str) -> Dict:
        chroma_coll = self.client.get_collection(name=collection)
        result = chroma_coll.get(ids=[id])
        if result['ids']:
            return {
                "id": result['ids'][0],
                "metadata": result['metadatas'][0],
                "document": result['documents'][0] if result['documents'] else None
            }
        return {}

    def insert_docs(self, collection: str, documents: List[Document], chunkids: List[str], embedding: HuggingFaceEmbeddings | OpenAIEmbeddings) -> bool:
        from langchain_chroma import Chroma
        vector_store = Chroma(
            client=self.client,
            collection_name=collection,
            embedding_function=embedding,
        )
        added_ids = vector_store.add_documents(documents=documents, ids=chunkids)
        return len(added_ids) > 0

    def test_retrieval(self, collection: str, embedding: HuggingFaceEmbeddings | OpenAIEmbeddings, queryList: List[str], topk: int, selected_docs: List[str] = []) -> List[List[Document]]:
        # Use raw chromadb client to avoid langchain_chroma version mismatch (_type KeyError)
        chroma_coll = self.client.get_collection(name=collection)

        results = []
        for query in queryList:
            filter_dict = None
            if selected_docs:
                if len(selected_docs) == 1:
                    filter_dict = {"source": selected_docs[0]}
                else:
                    filter_dict = {"source": {"$in": selected_docs}}

            # Embed the query ourselves
            query_embedding = embedding.embed_query(query)

            query_results = chroma_coll.query(
                query_embeddings=[query_embedding],
                n_results=topk,
                where=filter_dict,
                include=["documents", "metadatas", "distances"]
            )

            docs = []
            if query_results.get("ids") and query_results["ids"][0]:
                for i in range(len(query_results["ids"][0])):
                    page_content = (query_results["documents"][0][i] if query_results.get("documents") else "") or ""
                    metadata = (query_results["metadatas"][0][i] if query_results.get("metadatas") else {}) or {}
                    docs.append(Document(page_content=page_content, metadata=metadata))
            results.append(docs)
        return results

    def retrieve_docs_for_embeddings(self, collection: str, embeddings: List[List[float]], topk: int, selected_docs: List[str] = []) -> List[List[Document]]:
        from langchain_chroma import Chroma
        # We don't strictly need the embedding function for search if we have the vectors,
        # but LangChain's Chroma wrapper might expect it or we can use the raw client.
        
        chroma_coll = self.client.get_collection(name=collection)
        
        results = []
        for emb in embeddings:
            filter_dict = None
            if selected_docs:
                if len(selected_docs) == 1:
                    filter_dict = {"source": selected_docs[0]}
                else:
                    filter_dict = {"source": {"$in": selected_docs}}
            
            query_results = chroma_coll.query(
                query_embeddings=[emb],
                n_results=topk,
                where=filter_dict
            )
            
            docs = []
            if query_results['ids']:
                for i in range(len(query_results['ids'][0])):
                    docs.append(Document(
                        page_content=query_results['documents'][0][i] if query_results['documents'] else "",
                        metadata=query_results['metadatas'][0][i]
                    ))
            results.append(docs)
        return results
