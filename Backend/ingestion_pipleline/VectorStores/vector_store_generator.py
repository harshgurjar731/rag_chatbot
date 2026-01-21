from ingestion_pipleline.VectorStores.qdrant_vector_store import QDrantVectorDB
from ingestion_pipleline.VectorStores.chroma_vector_store import ChromaVectorDB

def create_vector_store(provider: str):
    if (provider.lower() == "QDrant".lower()):
        return QDrantVectorDB()
    elif (provider.lower() == "Chroma".lower() or provider.lower() == "ChromaDB".lower()):
        return ChromaVectorDB()
    else:
        print(f"VectorDB '{provider}' not supported currently")