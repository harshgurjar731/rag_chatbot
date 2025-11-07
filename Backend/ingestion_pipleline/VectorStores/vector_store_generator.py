from ingestion_pipleline.VectorStores.qdrant_vector_store import QDrantVectorDB

def create_vector_store(provider: str):
    if (provider.lower() == "QDrant".lower()):
        return QDrantVectorDB()
    else:
        print("VectorDB not supported currently")