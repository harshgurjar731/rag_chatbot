"""
This module provides the core RAG retrieval logic.

It includes functions to retrieve text and image answers using the RAG pipeline,
incorporating query decomposition, rewriting, vector store retrieval, and reranking.
"""

from typing import List
import json
from operator import itemgetter
from collections import defaultdict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_models import ChatOpenAI
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS, Chroma
from langchain_core.load import dumps, loads

from Services.guardrail import validate_output
from Services.reranker_service import get_reranker
from utils.llm_factory import LLMFactory
from config import CONFIG
import base64
import tempfile

from rag_pipeline.LLMs.llm_model_protocol import create_llm_model
from rag_pipeline.Config.rag_prompts import RAG_PROMPTS
from rag_pipeline.utility.Utils import get_final_prompt
from rag_pipeline.Config.rag_config import RAG_CONFIG
from rag_pipeline.Services.query_decomposition import iterative_query_decomposition
from rag_pipeline.Services.query_rewriting_handler import handle_query_rewriting, handle_chunk_union, history_based_query_generator

from rag_pipeline.Embeddings.embedding_models import create_embedding_model
from rag_pipeline.VectorStores.vector_store_generator import create_vector_store
from rag_pipeline.Reranker.reranking_helper import apply_reranker, get_reranker_model

def encode_image_to_base64(path: str) -> str:
    """
    Encode an image file to a base64 string.

    Args:
        path (str): The file path to the image.

    Returns:
        str: The base64 encoded string of the image.
    """
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
        
def get_rag_answer_text(
    query: str,
    search_image: str,
    message_history: any,
    selected_documents: List[str],
    llm_model_name: str = None,
    llm_model_provider: str = None,
    temperature: float = None,
    token_size: int = 256,
    include_sources: bool = False,
    guardrail_level: str = "none",
    embedding_model_name: str = "",
    embedding_model_provider: str = "",
    vector_store_provider: str = "",
    vector_store_collection_name: str = "",
    vector_store_top_k: int = 20,
    reranker_type: str = None,
    reranker_top_k: int = 5,
    query_optimizer: str = "none"
):
    """
    Generate a text-based RAG answer.

    This function orchestrates the entire RAG pipeline for text queries, including:
    1. Query history contextualization (if enabled).
    2. Query optimization/rewriting (MultiQuery, RAGFusion, etc.).
    3. Document retrieval from the vector store.
    4. Reranking of retrieved documents.
    5. Final answer generation using the LLM with the retrieved context.

    Args:
        query (str): The user's query.
        search_image (str): (Unused in text RAG, but kept for signature compatibility).
        message_history (any): The conversation history.
        selected_documents (List[str]): List of document identifiers to filter by.
        llm_model_name (str): LLM model name.
        llm_model_provider (str): LLM provider.
        temperature (float): LLM temperature.
        token_size (int): Max tokens for response.
        include_sources (bool): Whether to include source citations.
        guardrail_level (str): Guardrail configuration.
        embedding_model_name (str): Embedding model name.
        embedding_model_provider (str): Embedding provider.
        vector_store_provider (str): Vector store provider (e.g., Qdrant, Chroma).
        vector_store_collection_name (str): collection/datastore name.
        vector_store_top_k (int): Number of docs to retrieve.
        reranker_type (str): Reranker technique/model to use.
        reranker_top_k (int): Number of docs after reranking.
        query_optimizer (str): Query optimization strategy.

    Returns:
        dict: The final response containing the answer and citations.
    """
    if not llm_model_name or not llm_model_provider:
        raise ValueError("LLM model & provider name must be provided")

    llm = create_llm_model(
        provider=llm_model_provider,
        model_name=llm_model_name,
        temperature=temperature,
        max_tokens=token_size
    )

    rag_prompt_template = get_final_prompt(prompt=RAG_PROMPTS["rag_template"], use_knowledge_base=True, include_sources= include_sources)
    system_prompt = [("system", rag_prompt_template)]
    prompt_final = system_prompt + message_history
    
    print("***************************************************************************")
    print("\n\nPrompt Final:", prompt_final)

    embedding_model = create_embedding_model(provider=embedding_model_provider, model_name=embedding_model_name)
    
    vector_db = create_vector_store(
        provider=vector_store_provider
    )

    if (False): #query_decomposition_enabled
        iterative_query_answer = iterative_query_decomposition(
            query=query,
            history=message_history,
            llm=llm,
            vdb=vector_db,
            collection_name=vector_store_collection_name,
            ranker=get_reranker_model(reranker_type=reranker_type, model_name=""),
            enable_citations=False,
            ranker_top_k=4,
            top_k=12,
            embedding=embedding_model,
            selected_documents=selected_documents
        )
        return iterative_query_answer.trim()
    
    returned_chunks: List[Document] = []
    all_chunks_array = []

    # updated_query = history_based_query_generator(
    #     query = query,
    #     llm= llm,
    #     message_history=message_history
    # )
    updated_query = query
    print("Query Optimizer", query_optimizer)
    print("Updated Query based on history", updated_query)
    # rewritten_queries = handle_query_rewriting(
    #     rewritingType=query_optimizer,
    #     query=updated_query,
    #     llm= llm,
    # )
    rewritten_queries = [updated_query]
    if (query_optimizer.lower() == "multiquery" or query_optimizer.lower() == "ragfusion"):
        retrieval_top_k = RAG_CONFIG["default_multiquery_retrieval_top_k"]
    else:
        retrieval_top_k = RAG_CONFIG["default_query_retrieval_top_k"]
                                        
    print("Rewritten Queries: ", rewritten_queries)
    all_chunks_array = vector_db.test_retrieval(collection=vector_store_collection_name, embedding=embedding_model, queryList=rewritten_queries, topk=retrieval_top_k, selected_docs=selected_documents) 
    if(len(all_chunks_array) == 0):
        returned_chunks = []
    elif(len(all_chunks_array) == 1):
        returned_chunks = all_chunks_array[0]
    else :
        returned_chunks = handle_chunk_union(
            rewritingType= query_optimizer,
            retrieved_chunks = all_chunks_array
        )
    if(reranker_type and reranker_type.lower() != "none"): 
        print("RERANKING: ", reranker_type)
        returned_chunks = apply_reranker(
            reranker_type=reranker_type,
            model_name= "",  #TODOANKIT
            query= updated_query, 
            docs=returned_chunks, 
            top_k= reranker_top_k)

    # print("Reranked Chunks", returned_chunks)

    for index, chunk in enumerate(returned_chunks):
        if isinstance(chunk.metadata, dict):
            chunk.metadata["tempID"] = index

    prompt = ChatPromptTemplate.from_messages(prompt_final)
    print("\n\nFinal Query to LLM:", updated_query)

    # ✅ Chain: prompt → LLM → output parser
    chatbot_chain = (
        {"question": lambda x: x["question"], "context": lambda x: x["context"]}
        | prompt
        | llm
        | StrOutputParser()
    )

    # Raw LLM output
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("Unified_RAG_Chain") as span:
        span.set_attribute("query", updated_query)
        final_response = chatbot_chain.invoke({"question": updated_query, "context": returned_chunks})
        span.set_attribute("response_length", len(final_response))

    # # ✅ Apply guardrails
    # validated = validate_output(final_answer, guardrail_level)
    # if "⚠️ Response blocked" in validated["answer"]:
    #     return validated

    # final_answer = validated["answer"]

    # ✅ Handle sources
    print("LLM Answer:", final_response)
    try:
        final_response_obj = json.loads(final_response)
        # Handle cases where response might be missing keys
        if not isinstance(final_response_obj, dict):
             # If it parsed but is not a dict (e.g. list or string), treat as raw response
             final_response_obj = {"response": str(final_response_obj), "used_chunks": []}
        
        print("LLM Response:", final_response_obj.get("response", "")[:100]) # Print first 100 char safe
        used_chunk_indices = final_response_obj.get("used_chunks", [])
    except json.JSONDecodeError:
        print("⚠️ Warning: LLM validation failed to return JSON. Using raw text.")
        final_response_obj = {"response": final_response}
        # Fallback: assume all chunks were potentially relevant or none. 
        # For safety, let's say none to avoid hallucinated citations, 
        # or maybe we can try to heuristic match? For now, empty list is safest to prevent crashes.
        used_chunk_indices = []
    
    # Ensure used_chunk_indices is a list
    if not isinstance(used_chunk_indices, list):
        used_chunk_indices = []

    # Check if used_chunk_indices contains valid integers/strings that map to returned_chunks
    valid_indices = []
    for idx in used_chunk_indices:
        try:
            i = int(idx)
            if 0 <= i < len(returned_chunks):
                valid_indices.append(i)
        except (ValueError, TypeError):
            pass
            
    used_chunks = [returned_chunks[i] for i in valid_indices]

    unique_pairs = set()

    for chunk in used_chunks:
        metadata = chunk.metadata
        if isinstance(metadata, dict):
            source = metadata.get("source", "Unknown Source")
            page = metadata.get("page_number", "N/A")
            unique_pairs.add((source, page))

    unique_list = [{"source": s, "page_number": p} for s, p in unique_pairs]

    # Convert to JSON string
    source_json_string = json.dumps(unique_list, indent=2)
    print("source_json_string:", source_json_string)
    # if include_sources and "Sources:" in final_answer:
    #     parts = final_answer.split("Sources:")
    #     answer_text = parts[0].strip()
    #     sources_text = parts[1].strip() if len(parts) > 1 else ""
    #     return {
    #         "answer": answer_text + "\n\nSources: " + str(sources_text.split("\n") if sources_text else [])
    #     }


    answer_text = final_response_obj["response"]
    if isinstance(answer_text, dict) or isinstance(answer_text, list):
        answer_text = json.dumps(answer_text)
    
    return {"answer": str(answer_text).strip(),
            "images": [],
            "citations": source_json_string}


def get_rag_answer_image(
    query: str,
    search_image: str,
    #message_history: any,
    #selected_documents: List[str],
    # llm_model_name: str = None,
    # llm_model_provider: str = None,
    # temperature: float = None,
    # token_size: int = 256,
    include_sources: bool = False,
    #guardrail_level: str = "none",
    embedding_model_name: str = "",
    embedding_model_provider: str = "",
    vector_store_provider: str = "",
    vector_store_collection_name: str = "",
    vector_store_top_k: int = 20,
    reranker_type: str = None,
    reranker_top_k: int = 5,
    #query_optimizer: str = "none"
):
    """
    Generate an answer using image retrieval (Vision RAG).

    This function embeds the query (text or image) and retrieves relevant images from
    the vector store.

    Args:
        query (str): The user's text query.
        search_image (str): Base64 encoded image string for image-to-image search.
        include_sources (bool): Whether to include sources (placeholder).
        embedding_model_name (str): Embedding model to use for image/text embedding.
        embedding_model_provider (str): Provider for the embedding model.
        vector_store_provider (str): Vector store provider.
        vector_store_collection_name (str): Collection name (will append "_image").
        vector_store_top_k (int): Number of images to retrieve.
        reranker_type (str): Reranker type (not currently active for images).
        reranker_top_k (int): Reranking top K.

    Returns:
        dict: Response containing retrieved image base64 strings.
    """
    # if not llm_model_name or not llm_model_provider:
    #     raise ValueError("LLM model & provider name must be provided")

    # llm = create_llm_model(
    #     provider=llm_model_provider,
    #     model_name=llm_model_name,
    #     temperature=temperature,
    #     max_tokens=token_size
    # )

    # rag_prompt_template = get_final_prompt(prompt=RAG_PROMPTS["rag_template"], use_knowledge_base=True, include_sources= include_sources)
    # system_prompt = [("system", rag_prompt_template)]
    # prompt_final = system_prompt + message_history
    
    # print("***************************************************************************")
    # print("\n\nPrompt Final:", prompt_final)

    # embedding_model = create_embedding_model(provider=embedding_model_provider, model_name=embedding_model_name)
    
    embeddingModel = create_embedding_model(
            provider=embedding_model_provider,
            model_name=embedding_model_name, #TODOANKIT: Replace with image_embedding_model -> when supporting multiple models for text and image
        )
    print("Image search 1")
    if(search_image and len(search_image)):
        print("In Image embedding flow")
        print("Image search 2")
        b64_string = search_image.split(",", 1)[1]
        image_bytes = base64.b64decode(b64_string)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")  
        temp_file.write(image_bytes)
        temp_file.close()
        queries_embedded = embeddingModel.embed_image([temp_file.name])
    else:
        print("Image search 3")
        queries_embedded = embeddingModel.embed_documents([query])

    vector_db = create_vector_store(
        provider=vector_store_provider
    )
    collection_name = str(vector_store_collection_name) + "_image"
    # vector_store already initialized earlier (same collection & embedding)
    print("Collection Name", collection_name)
    results = vector_db.retrieve_docs_for_embeddings(collection=collection_name, embeddings=queries_embedded, topk= vector_store_top_k)
    
    images_b64 = [
        encode_image_to_base64(doc.metadata["image_path"])
        for result in results
        for doc in result
        if "image_path" in doc.metadata
    ]

    return {"answer": "",
            "images": images_b64,
            "citations": "[]"}

