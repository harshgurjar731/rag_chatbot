# # services/retriever_service.py

# from fastapi import HTTPException
# from langchain.vectorstores import FAISS, Chroma
# from langchain.embeddings import HuggingFaceEmbeddings

# from config import CONFIG
# from Services.multi_query_retriever import get_multiquery_retriever
# from Services.multi_query_retriever_without_sources import get_multiquery_retriever_without_sources
# from Services.general_retriever import get_llm_answer
# from Services.step_back_retriever_with_source import get_stepback_retriever_with_sources
# from Services.step_back_retriever_without_source import get_stepback_retriever_without_sources
# from Services.rag_fusion_retriever_with_source import get_ragfusion_retriever_with_sources
# from Services.rag_fusion_retriever_without_sources import get_ragfusion_retriever_without_sources
# from Services.none_query import get_rag_response



# # -----------------------------
# # Load embeddings
# # -----------------------------
# def load_embeddings(file_id: int, vector_db: str = None, model_name: str = None):
#     """Load FAISS/Chroma embeddings for a given file ID."""

#     vector_db = vector_db or CONFIG["default_vector_db"]
#     model_name = model_name or CONFIG["default_embedding_model"]

#     embedding = HuggingFaceEmbeddings(model_name=model_name)

#     if vector_db == "faiss":
#         db = FAISS.load_local(
#             f"vectorstores/faiss_file_{file_id}",
#             embedding,
#             allow_dangerous_deserialization=True,
#         )
#         return db

#     elif vector_db == "chroma":
#         db = Chroma(
#             persist_directory=f"vectorstores/chroma_file_{file_id}",
#             embedding_function=embedding,
#         )
#         return db

#     else:
#         raise HTTPException(status_code=400, detail="Unsupported vector DB")


# # -----------------------------
# # Document Retrieval
# # -----------------------------
# def retrieve_documents(
#     query: str,
#     query_optimizer: str = None,
#     embedding_model_name: str = None,
#     llm_model_name: str = None,
#     vector_db: str = None,
#     file_id: list = None,
#     temperature: float = None,
#     token_size: int = None,
#     sources: bool = False,
#     guardrailOption: str = None,
#     rerankerOption: str = None,
#     chatbot_id: str = "RAG_Document_Store"
# ):
#     """Main entry for retrieving documents with selected retriever pipeline."""

#     # ✅ Load defaults from config if not provided
#     query_optimizer = query_optimizer or CONFIG["default_query_optimizer"]
#     embedding_model_name = embedding_model_name or CONFIG["default_embedding_model"]
#     llm_model_name = llm_model_name or CONFIG["default_llm_model"]
#     vector_db = vector_db or CONFIG["default_vector_db"]
#     temperature = temperature if temperature is not None else CONFIG["default_temperature"]
#     token_size = token_size or CONFIG["default_token_size"]
#     guardrailOption = guardrailOption or CONFIG["default_guardrail_option"]
#     rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

#     file_id = file_id or [0]
#     embedding = HuggingFaceEmbeddings(model_name=embedding_model_name)

#     # -----------------------------
#     # Case 1: No files -> plain LLM answer
#     # -----------------------------
#     if file_id == [0]:
#         return get_llm_answer(
#             query, llm_model_name, temperature, token_size, sources, guardrailOption
#         )

#     # -----------------------------
#     # Case 2: Merge embeddings from all files
#     # -----------------------------
#     db = None
#     for f_id in file_id:
#         new_db = load_embeddings(f_id, vector_db, embedding_model_name)
#         if db is None:
#             db = new_db
#         else:
#             db.merge_from(new_db)

#     # -----------------------------
#     # Case 3: Choose retriever pipeline
#     # -----------------------------
#     if query_optimizer == "Multi Query":
#         if sources:
#             result = get_multiquery_retriever(
#                 query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
#             )
#         else:
#             result = get_multiquery_retriever_without_sources(
#                 query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
#             )
            

#     elif query_optimizer == "Step Back":
#         if sources:
#             result = get_stepback_retriever_with_sources(
#                 query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
#             )
#         else:
#             result = get_stepback_retriever_without_sources(
#                 query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
#             )

#     elif query_optimizer == "Rag Fusion":
#         if sources:
#             result = get_ragfusion_retriever_with_sources(
#                 query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
#             )
#         else:
#             result = get_ragfusion_retriever_without_sources(
#                 query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
#             )

#     else:
#         retriever = db.as_retriever()
#         result = retriever.get_relevant_documents(query)

#     return result




# services/retriever_service.py

from fastapi import HTTPException
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from config import CONFIG
from Services.general_retriever import get_llm_answer
from Services.rag_pipeline import UnifiedRAGPipeline  # ✅ Unified RAG Pipeline


# -----------------------------
# Load embeddings
# -----------------------------
# -----------------------------
# Load embeddings
# -----------------------------
def load_embeddings(file_id: int, vector_db: str = None, model_name: str = None):
    """
    Load FAISS/Chroma embeddings vector store for a given file ID.

    Args:
        file_id (int): The ID of the file.
        vector_db (str, optional): Vector database type ('faiss' or 'chroma'). Defaults to config.
        model_name (str, optional): Embedding model name. Defaults to config.

    Returns:
        VectorStore: The loaded vector store object.

    Raises:
        HTTPException: If the vector DB type is unsupported.
    """
    vector_db = vector_db or CONFIG["default_vector_db"]
    model_name = model_name or CONFIG["default_embedding_model"]

    embedding = HuggingFaceEmbeddings(model_name=model_name)

    if vector_db.lower() == "faiss":
        db = FAISS.load_local(
            f"vectorstores/faiss_file_{file_id}",
            embedding,
            allow_dangerous_deserialization=True,
        )
        return db

    elif vector_db.lower() == "chroma":
        db = Chroma(
            persist_directory=f"vectorstores/chroma_file_{file_id}",
            embedding_function=embedding,
        )
        return db

    else:
        raise HTTPException(status_code=400, detail="Unsupported vector DB")


# -----------------------------
# Document Retrieval
# -----------------------------
# -----------------------------
# Document Retrieval
# -----------------------------
def retrieve_documents(
    query: str,
    query_optimizer: str = None,
    embedding_model_name: str = None,
    llm_model_name: str = None,
    vector_db: str = None,
    file_id: list = None,
    temperature: float = None,
    token_size: int = None,
    sources: bool = False,
    guardrailOption: str = None,
    rerankerOption: str = None,
    chatbot_id: str = "RAG_Document_Store"
):
    """
    Main entry point for retrieving documents using the unified RAG pipeline.
    
    This function orchestrates the retrieval process by:
    1. Loading defaults from configuration.
    2. Handling cases with no files (plain LLM answer).
    3. Merging embeddings from multiple files if applicable.
    4. Initializing and running the UnifiedRAGPipeline with selected options.

    Args:
        query (str): The user's query.
        query_optimizer (str): Strategy for query optimization (e.g., 'Multi Query', 'Step Back').
        embedding_model_name (str): Name of the embedding model.
        llm_model_name (str): Name of the LLM model.
        vector_db (str): Vector database type.
        file_id (list): List of file IDs to retrieve from.
        temperature (float): LLM temperature.
        token_size (int): Max tokens for response.
        sources (bool): Whether to include sources in response.
        guardrailOption (str): Guardrail level.
        rerankerOption (str): Reranker option.
        chatbot_id (str): Chatbot identifier.

    Returns:
        dict: The result containing the answer, sources, and other metadata.
    """

    # -----------------------------
    # Load defaults from config
    # -----------------------------
    query_optimizer = query_optimizer or CONFIG["default_query_optimizer"]
    embedding_model_name = embedding_model_name or CONFIG["default_embedding_model"]
    llm_model_name = llm_model_name or CONFIG["default_llm_model"]
    vector_db = vector_db or CONFIG["default_vector_db"]
    temperature = temperature if temperature is not None else CONFIG["default_temperature"]
    token_size = token_size or CONFIG["default_token_size"]
    guardrailOption = guardrailOption or CONFIG["default_guardrail_option"]
    rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

    file_id = file_id or [0]

    # -----------------------------
    # Case 1: No files -> plain LLM answer
    # -----------------------------
    if file_id == [0]:
        return get_llm_answer(
            query=query,
            llm_model_name=llm_model_name,
            temperature=temperature,
            token_size=token_size,
            include_sources=sources,
            guardrail_level=guardrailOption,
        )

    # -----------------------------
    # Case 2: Load embeddings for all files and merge
    # -----------------------------
    merged_db = None
    for f_id in file_id:
        new_db = load_embeddings(f_id, vector_db, embedding_model_name)
        if merged_db is None:
            merged_db = new_db
        else:
            merged_db.merge_from(new_db)

    if merged_db is None:
        raise HTTPException(status_code=400, detail="No vector store found for the given files")

    # -----------------------------
    # Case 3: Use Unified RAG Pipeline
    # -----------------------------
    # Map query_optimizer names to modes in unified pipeline
    mode_map = {
        "Multi Query": "multiquery",
        "Step Back": "stepback",
        "Rag Fusion": "ragfusion",
        "None": "none"
    }
    mode = mode_map.get(query_optimizer, "multiquery")

    rag_pipeline = UnifiedRAGPipeline(
        db=merged_db,  # ✅ Single merged DB used for all retriever types
        llm_model_name=llm_model_name,
        temperature=temperature,
        token_size=token_size,
        guardrail_level=guardrailOption,
        rerankerOption=rerankerOption
    )

    result = rag_pipeline.run(
        query=query,
        include_sources=sources,
        mode=mode
    )

    return result
