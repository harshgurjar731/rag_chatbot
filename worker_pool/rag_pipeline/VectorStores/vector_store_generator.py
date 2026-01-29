from rag_pipeline.VectorStores.qdrant_vector_store import QDrantVectorDB
from rag_pipeline.VectorStores.chroma_vector_store import ChromaVectorDB

def create_vector_store(provider: str):
    if (provider.lower() == "QDrant".lower()):
        return QDrantVectorDB()
    elif (provider.lower() == "Chroma".lower() or provider.lower() == "ChromaDB".lower()):
        return ChromaVectorDB()
    else:
        print("VectorDB not supported currently")