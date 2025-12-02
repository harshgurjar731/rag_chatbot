# services/unified_rag_pipeline.py

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

from ingestion_pipleline.Embeddings.embedding_models import create_embedding_model
from ingestion_pipleline.VectorStores.vector_store_generator import create_vector_store
from ingestion_pipleline.Reranker.reranking_helper import apply_reranker, get_reranker_model

def encode_image_to_base64(path: str) -> str:
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
    """General purpose chatbot without using any file/vector store data."""
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

    updated_query = history_based_query_generator(
        query = query,
        llm= llm,
        message_history=message_history
    )
    print("Query Optimizer", query_optimizer)
    print("Updated Query based on history", updated_query)
    rewritten_queries = handle_query_rewriting(
        rewritingType=query_optimizer,
        query=updated_query,
        llm= llm,
    )
    if (query_optimizer.lower() == "multiquery" or query_optimizer.lower() == "ragfusion"):
        retrieval_top_k = RAG_CONFIG["default_multiquery_retrieval_top_k"]
    else:
        retrieval_top_k = RAG_CONFIG["default_query_retrieval_top_k"]
                                        
    print("Rewritten Queries: ", rewritten_queries)
    all_chunks_array = vector_db.test_retrieval(collection=vector_store_collection_name, embedding=embedding_model, queryList=rewritten_queries, topk=retrieval_top_k, selected_docs=selected_documents) 
    if(len(all_chunks_array) == 1):
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
    final_response = chatbot_chain.invoke({"question": updated_query, "context": returned_chunks})

    # # ✅ Apply guardrails
    # validated = validate_output(final_answer, guardrail_level)
    # if "⚠️ Response blocked" in validated["answer"]:
    #     return validated

    # final_answer = validated["answer"]

    # ✅ Handle sources
    print("LLM Answer:", final_response)
    final_response_obj = json.loads(final_response)
    print("LLM Response:", final_response_obj["response"])
    
    used_chunk_indices = final_response_obj["used_chunks"]
    used_chunks = [returned_chunks[i] for i in used_chunk_indices]

    unique_pairs = set()

    for chunk in used_chunks:
        metadata = chunk.metadata
        source = metadata["source"]
        page = metadata["page_number"]
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


    return {"answer": final_response_obj["response"].strip(),
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
    """General purpose chatbot without using any file/vector store data."""
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

