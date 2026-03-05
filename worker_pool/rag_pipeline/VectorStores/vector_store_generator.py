# from rag_pipeline.VectorStores.qdrant_vector_store import QDrantVectorDB  # lazy-imported below
# from rag_pipeline.VectorStores.chroma_vector_store import ChromaVectorDB  # lazy-imported below

def create_vector_store(provider: str):
    if (provider.lower() == "QDrant".lower()):
        from rag_pipeline.VectorStores.qdrant_vector_store import QDrantVectorDB
        return QDrantVectorDB()
    elif (provider.lower() == "Chroma".lower() or provider.lower() == "ChromaDB".lower()):
        from rag_pipeline.VectorStores.chroma_vector_store import ChromaVectorDB
        return ChromaVectorDB()
    else:
        print("VectorDB not supported currently")