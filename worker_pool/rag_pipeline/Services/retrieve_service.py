"""
This module serves as the main entry point for document retrieval and question answering.

It orchestrates the flow between the chat answer retriever (pure LLM) and the RAG-based retriever
(knowledge base enabled), determining the appropriate strategy based on the request parameters.
"""

from fastapi import HTTPException
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from config import CONFIG
from rag_pipeline.rag_models import Message
from rag_pipeline.Config.rag_config import RAG_CONFIG
from rag_pipeline.Services.chat_answer_retriever import get_llm_answer
from rag_pipeline.Services.rag_retriever import get_rag_answer_text, get_rag_answer_image  # ✅ Unified RAG Pipeline
from typing import List
from rag_pipeline.Services.nemo_service import nemo_service

async def retrieve_documents(
    query: str,
    search_image: str,
    message_history: List[Message],
    selected_documents: List[str],
    query_optimizer: str = None,
    use_knowledge_base: bool = True,
    embedding_model_provider: str = None,
    embedding_model_name: str = None,
    llm_model_name: str = None,
    llm_model_provider: str = None,
    vector_db: str = None,
    file_id: list = None,
    temperature: float = None,
    token_size: int = None,
    sources: bool = False,
    guardrailOption: str = None,
    rerankerOption: str = None,
    datastore_id: str = None,
    is_vision_search: bool = False,
    # chatbot_id: str = "RAG_Document_Store"
):
    """
    Retrieve documents and generate an answer based on the provided query and configuration.

    This function acts as a facade, routing the request to either `get_llm_answer` (if no
    knowledge base is used) or `get_rag_answer_text`/`get_rag_answer_image` (if RAG is enabled).
    It handles history formatting and parameter extraction.

    Args:
        query (str): The user's query.
        search_image (str): Base64 encoded image string for vision search.
        message_history (List[Message]): List of previous messages in the conversation.
        selected_documents (List[str]): List of specific document IDs to restrict search to.
        query_optimizer (str, optional): Strategy for query optimization (e.g., "Multi Query").
        use_knowledge_base (bool, optional): Whether to use the RAG pipeline. Defaults to True.
        embedding_model_provider (str, optional): Provider for embeddings.
        embedding_model_name (str, optional): Name of the embedding model.
        llm_model_name (str, optional): Name of the LLM model.
        llm_model_provider (str, optional): Provider for the LLM.
        vector_db (str, optional): Vector database provider.
        file_id (list, optional): List of file IDs (legacy/unused).
        temperature (float, optional): LLM temperature.
        token_size (int, optional): Max tokens for response.
        sources (bool, optional): Whether to include sources in the response. Defaults to False.
        guardrailOption (str, optional): Guardrail level.
        rerankerOption (str, optional): Reranker type.
        datastore_id (str, optional): ID of the datastore to query.
        is_vision_search (bool, optional): Whether this is an image-based search. Defaults to False.

    Returns:
        dict: The final result containing the answer, images, and citations.
    """
    # -----------------------------
    # Load defaults from config
    # -----------------------------
    # query_optimizer = query_optimizer or CONFIG["default_query_optimizer"]
    # embedding_model_name = embedding_model_name or CONFIG["default_embedding_model"]
    # embedding_model_provider = 
    # llm_model_name = llm_model_name or CONFIG["default_llm_model"]
    # vector_db = vector_db or CONFIG["default_vector_db"]
    # temperature = temperature if temperature is not None else CONFIG["default_temperature"]
    # token_size = token_size or CONFIG["default_token_size"]
    # guardrailOption = guardrailOption or CONFIG["default_guardrail_option"]
    # rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

    print("In retrieve service:",query, llm_model_name, temperature, token_size, sources, guardrailOption,  )
    print("Message_History", message_history)

    if (guardrailOption == "on"):
        answer = await nemo_service.generate_response(query)
    # -----------------------------
    # Case 1: No files -> plain LLM answer
    # -----------------------------
    if (use_knowledge_base == False):
        print("In without knowledge base flow")
        result = get_llm_answer(
            query=query,
            llm_model_name=llm_model_name,
            llm_model_provider=llm_model_provider,
            temperature=temperature,
            token_size=token_size,
            include_sources=sources,
            guardrail_level=guardrailOption,
        )
        print ("Result", result)
        return result
    else:
        print("In knowledge base flow")
        print("is_vision_search", is_vision_search)
        if(is_vision_search):
            result = get_rag_answer_image(
                query=query,
                search_image= search_image,
                # message_history= past_messages,
                # selected_documents=selected_documents,
                # llm_model_name=llm_model_name,
                # llm_model_provider=llm_model_provider,
                # temperature=temperature,
                # token_size=token_size,
                include_sources=sources,
                # guardrail_level=guardrailOption,
                embedding_model_name= embedding_model_name,
                embedding_model_provider = embedding_model_provider,
                vector_store_provider= vector_db,
                vector_store_collection_name= f"datastore_{datastore_id}",
                vector_store_top_k= RAG_CONFIG["default_query_retrieval_top_k"],
                reranker_type= rerankerOption,
                reranker_top_k=RAG_CONFIG["default_rerank_top_k"],
                # query_optimizer= query_optimizer,
            )
            return result

        user_message = [("user", "{question}")]
        # conversation is tuple so it should be multiple of two
        # -1 is to keep last k conversation
        conv_history_count = RAG_CONFIG["default_conversation_history_count"]*2*-1
        conversation_history = []
        for message in message_history[conv_history_count:]:
            if message.role == "assistant":
                # Remove everything starting from "\nSources" (including it)
                clean_content = message.content.split("\nSources")[0].strip()
            else:
                clean_content = message.content
            conversation_history.append((message.role, clean_content))

        past_messages = conversation_history + user_message

        result = get_rag_answer_text(
            query=query,
            search_image= search_image,
            message_history= past_messages,
            selected_documents=selected_documents,
            llm_model_name=llm_model_name,
            llm_model_provider=llm_model_provider,
            temperature=temperature,
            token_size=token_size,
            include_sources=sources,
            guardrail_level=guardrailOption,
            embedding_model_name= embedding_model_name,
            embedding_model_provider = embedding_model_provider,
            vector_store_provider= vector_db,
            vector_store_collection_name= f"datastore_{datastore_id}",
            vector_store_top_k= RAG_CONFIG["default_query_retrieval_top_k"],
            reranker_type= rerankerOption,
            reranker_top_k=RAG_CONFIG["default_rerank_top_k"],
            query_optimizer= query_optimizer,
        )
        return result
    # -----------------------------
    # Case 2: Load embeddings for all files and merge
    # -----------------------------
    # merged_db = None
    # for f_id in file_id:
    #     new_db = load_embeddings(f_id, vector_db, embedding_model_name)
    #     if merged_db is None:
    #         merged_db = new_db
    #     else:
    #         merged_db.merge_from(new_db)

    # if merged_db is None:
    #     raise HTTPException(status_code=400, detail="No vector store found for the given files")

    # # -----------------------------
    # # Case 3: Use Unified RAG Pipeline
    # # -----------------------------
    # # Map query_optimizer names to modes in unified pipeline
    # mode_map = {
    #     "Multi Query": "multiquery",
    #     "Step Back": "stepback",
    #     "Rag Fusion": "ragfusion",
    #     "None": "none"
    # }
    # mode = mode_map.get(query_optimizer, "multiquery")

    # rag_pipeline = UnifiedRAGPipeline(
    #     db=merged_db,  # ✅ Single merged DB used for all retriever types
    #     llm_model_name=llm_model_name,
    #     temperature=temperature,
    #     token_size=token_size,
    #     guardrail_level=guardrailOption,
    #     rerankerOption=rerankerOption
    # )

    # result = rag_pipeline.run(
    #     query=query,
    #     include_sources=sources,
    #     mode=mode
    # )