"""
STUB SERVICE
Refactored: The heavy embedding logic has been moved to `ingestion_pool`.
This file exists only to prevent ImportErrors if legacy code tries to import it.
Runtime usage of these functions should now throw an error or handle dispatching to Redis if refactored further.
"""

def embed_and_store(*args, **kwargs):
    raise NotImplementedError("Embedding has been moved to the Ingestion Pool service.")

def load_chunks(*args, **kwargs):
    raise NotImplementedError("Chunk loading for embedding is now handled in Ingestion Pool.")

def check_embeddings_status(*args, **kwargs):
    # This might be needed for the UI check loop.
    # If the UI polls this, we might need a lightweight way to check the DB/VectorDB status
    # WITHOUT importing heavy libraries. E.g. just querying the SQL DB status flag.
    raise NotImplementedError("Embedding status check should be refactored to check SQL metadata only.")

def delete_vector_store(*args, **kwargs):
     raise NotImplementedError("Vector deletion is now handled via Redis dispatch.")
