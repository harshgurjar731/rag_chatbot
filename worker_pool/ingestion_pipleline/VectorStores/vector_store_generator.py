"""
Vector Store Factory.

This module provides a unified method to instantiate vector store adapters
based on the provider name.
"""
from ingestion_pipleline.VectorStores.qdrant_vector_store import QDrantVectorDB
from ingestion_pipleline.VectorStores.chroma_vector_store import ChromaVectorDB

def create_vector_store(provider: str):
    """
    Factory function to create a vector store instance.

    Args:
        provider (str): 'QDrant' or 'Chroma'/'ChromaDB'.

    Returns:
        VectorStoreProtocol: Logic adapter for the requested vector store.
    """
    if (provider.lower() == "QDrant".lower()):
        return QDrantVectorDB()
    elif (provider.lower() == "Chroma".lower() or provider.lower() == "ChromaDB".lower()):
        return ChromaVectorDB()
    else:
        print("VectorDB not supported currently")