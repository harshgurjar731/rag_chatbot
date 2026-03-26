"""
This module provides the core RAG retrieval logic.

It includes functions to retrieve text and image answers using the RAG pipeline,
incorporating query decomposition, rewriting, vector store retrieval, and reranking.
"""

import logging
logger = logging.getLogger(__name__)

from typing import List
import json
import os
from operator import itemgetter
from collections import defaultdict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_models import ChatOpenAI
from langchain.retrievers import ContextualCompressionRetriever
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

def _deduplicate_video_segments(chunks: List[Document]) -> List[Document]:
    """
    Deduplicate video chunks that share the same video_segment_id.
    
    When transcript and caption are stored as separate chunks, both may be
    retrieved for the same video segment. This keeps only the highest-ranked
    one (earliest in the list) to avoid wasting LLM context window.
    Non-video chunks pass through unchanged.
    """
    seen_segments = set()
    deduped = []
    
    for chunk in chunks:
        segment_id = chunk.metadata.get("video_segment_id") if isinstance(chunk.metadata, dict) else None
        
        if segment_id is None:
            # Non-video chunk — always keep
            deduped.append(chunk)
        elif segment_id not in seen_segments:
            # First time seeing this video segment — keep it
            seen_segments.add(segment_id)
            deduped.append(chunk)
        # else: duplicate video segment — skip
    
    if len(chunks) != len(deduped):
        logger.info(f"[DEDUP] Removed {len(chunks) - len(deduped)} duplicate video segment chunks")
    
    return deduped


def _load_graph_context(collection_name: str) -> str:
    """
    Load knowledge graph data from GraphML files for a given datastore.
    Returns a structured text summary of entities and relationships,
    or empty string if no graph data exists.
    """
    import glob
    import xml.etree.ElementTree as ET

    # Extract datastore_id from collection name (format: "datastore_123")
    datastore_id = collection_name.replace("datastore_", "")

    # Resolve graph directory (same DATA_DIRECTORY used by video_processing_pool)
    data_dir = os.getenv("DATA_DIRECTORY", "/app/data_directory")
    if not os.path.isabs(data_dir):
        # Resolve relative to project root (rag_chatbot)
        # This file is in rag_chatbot/worker_pool/rag_pipeline/Services/rag_retriever.py
        # Project root is 4 levels up
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        data_dir = os.path.abspath(os.path.join(base_dir, data_dir))
    
    graph_dir = os.path.join(data_dir, "video_graphs")

    pattern = os.path.join(graph_dir, f"graph_{datastore_id}_*.graphml")
    graph_files = glob.glob(pattern)

    if not graph_files:
        return ""

    all_entities = []
    all_relationships = []

    for gf in graph_files:
        try:
            tree = ET.parse(gf)
            root = tree.getroot()
            # GraphML namespace
            ns = {"g": "http://graphml.graphstruct.org/xmlns"}
            # Try with namespace first, then without
            nodes = root.findall(".//g:node", ns) or root.findall(".//{http://graphml.graphstruct.org/xmlns}node") or root.iter("node")
            edges = root.findall(".//g:edge", ns) or root.findall(".//{http://graphml.graphstruct.org/xmlns}edge") or root.iter("edge")

            node_labels = {}
            for node in nodes:
                node_id = node.get("id", "")
                # Extract label from data elements
                label = node_id
                node_type = "Entity"
                for data_el in node:
                    key = data_el.get("key", "").lower()
                    if "node_type" in key:
                        node_type = data_el.text or "Entity"
                    
                    if key in ["label", "name", "text", "class_name", "filename"]:
                        if data_el.text:
                            label = data_el.text
                    elif data_el.text and len(data_el.text) > len(label) and key not in ["uuid", "embedding", "cv_meta"]:
                        # Fallback for weird keys but exclude noise
                        label = data_el.text
                
                # Format node representation based on type
                if node_type == "Summary":
                    label = f'Summary: "{label}"'
                elif node_type == "Object":
                    label = f"Object: {label}"
                elif node_type == "Video":
                    label = f"Video: {label}"
                elif node_type == "Chunk":
                    label = f"Chunk (ID: {node_id.replace('chunk_', '')})"
                elif node_type == "Frame":
                    label = f"Frame (ID: {node_id.replace('frame_', '')})"
                
                node_labels[node_id] = label
                
                # Exclude purely structural nodes from the main entities list to reduce noise
                if node_type not in ["Chunk", "Frame"]:
                    all_entities.append(label)

            for edge in edges:
                src = edge.get("source", "")
                tgt = edge.get("target", "")
                rel_type = ""
                for data_el in edge:
                    if data_el.text:
                        rel_type = data_el.text
                        break
                src_label = node_labels.get(src, src)
                tgt_label = node_labels.get(tgt, tgt)
                rel_str = f"{src_label} --[{rel_type}]--> {tgt_label}" if rel_type else f"{src_label} --> {tgt_label}"
                
                # Filter out pure structural noise from relationships if not needed, 
                # but relationships like DESCRIBES or TEMPORAL_NEXT can be helpful context
                all_relationships.append(rel_str)
        except Exception as e:
            print(f"[GRAPH] Error parsing {gf}: {e}")
            continue

    if not all_entities and not all_relationships:
        return ""

    # Build structured text
    parts = ["[Knowledge Graph Context]"]
    if all_entities:
        unique_entities = list(dict.fromkeys(all_entities))  # deduplicate, preserve order
        parts.append(f"Entities: {', '.join(unique_entities)}")
    if all_relationships:
        parts.append("Relationships:")
        for rel in all_relationships:
            parts.append(f"  - {rel}")

    return "\n".join(parts)


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
    
    # Safe printing for Windows
    try:
        print("***************************************************************************")
        # Only print first few chars and handle encoding
        print("\n\nPrompt Final (truncated):", str(prompt_final)[:500].encode('ascii', 'ignore').decode('ascii'))
    except:
        pass

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
    qopt = (query_optimizer or "").lower()
    if (qopt == "multiquery" or qopt == "ragfusion"):
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
            rewritingType= qopt,
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

    # --- Video Segment Deduplication ---
    # When transcript and caption are separate chunks, both may be retrieved
    # for the same time segment. Keep only the highest-ranked one.
    returned_chunks = _deduplicate_video_segments(returned_chunks)

    # --- Knowledge Graph Context Injection ---
    # If GraphML files exist for this datastore, parse and inject as extra context
    try:
        graph_context = _load_graph_context(vector_store_collection_name)
        if graph_context:
            graph_doc = Document(
                page_content=graph_context,
                metadata={"source": "knowledge_graph", "content_type": "graph"}
            )
            returned_chunks.insert(0, graph_doc)
            print(f"[GRAPH] Injected knowledge graph context ({len(graph_context)} chars)")
    except Exception as e:
        print(f"[GRAPH] Could not load graph context: {e}")

    # print("Reranked Chunks", returned_chunks)

    for index, chunk in enumerate(returned_chunks):
        if isinstance(chunk.metadata, dict):
            chunk.metadata["tempID"] = index

    prompt = ChatPromptTemplate.from_messages(prompt_final)
    try:
        print("\n\nFinal Query to LLM:", str(updated_query).encode('ascii', 'ignore').decode('ascii'))
    except:
        pass

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
        span.set_attribute("response_length", len(final_response))    # ✅ Apply guardrails
    validated = validate_output(final_response, guardrail_level)
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    final_response = validated["answer"]

    # ✅ Handle sources
    try:
        print("LLM Answer (truncated):", final_response[:500].encode('ascii', 'ignore').decode('ascii'))
    except:
        pass
    try:
        # Strip markdown code fences if the LLM wrapped JSON in ```json ... ```
        cleaned = final_response.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        # Try to find the JSON object if there's surrounding text
        if not (cleaned.startswith("{") and cleaned.endswith("}")):
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                cleaned = cleaned[start:end]
            else:
                # If no matching brackets found, it's definitely not raw JSON as requested
                raise ValueError("No JSON object found in LLM response")

        final_response_obj = json.loads(cleaned)
        
        # Handle cases where response might be missing keys
        if not isinstance(final_response_obj, dict):
             # If it parsed but is not a dict (e.g. list or string), treat as raw response
             final_response_obj = {"response": str(final_response_obj), "used_chunks": []}
        
        try:
            print("LLM Response (truncated):", final_response_obj.get("response", "")[:100].encode('ascii', 'ignore').decode('ascii'))
        except:
            pass
        used_chunk_indices = final_response_obj.get("used_chunks", [])
        
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️ Warning: LLM validation failed to return valid JSON: {e}")
        print(f"⚠️ Raw LLM Output (first 500 chars): {final_response[:500]}...")
        
        # Heuristic: If it looks like JSON but is missing a closing brace (likely truncation)
        if final_response.strip().startswith("{") and not final_response.strip().endswith("}"):
            print("⚠️ Detected likely JSON truncation (missing closing brace)")
            # Try to fix by appending '}' and re-parsing
            try:
                fixed_response = final_response.strip() + '}'
                # If used_chunks was open, try to close it too
                if '"used_chunks": [' in fixed_response and ']' not in fixed_response.split('"used_chunks": [')[-1]:
                     fixed_response = final_response.strip() + ']}'
                
                final_response_obj = json.loads(fixed_response)
                print("✅ Successfully recovered JSON by adding closing braces.")
                used_chunk_indices = final_response_obj.get("used_chunks", [])
            except:
                final_response_obj = {"response": final_response}
                used_chunk_indices = []
        else:
            final_response_obj = {"response": final_response}
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
            # For video chunks, use timestamp range as "page"; for docs, use page_number
            chunk_type = metadata.get("chunk_type", "")
            if chunk_type in ("transcript", "caption", "fallback"):
                start_ts = metadata.get("start_timestamp", "?")
                end_ts = metadata.get("end_timestamp", "?")
                page = f"{start_ts}s-{end_ts}s ({chunk_type})"
            else:
                page = metadata.get("page_number", "N/A")
            unique_pairs.add((source, page))

    unique_list = [{"source": s, "page_number": p} for s, p in unique_pairs]

    # Convert to JSON string
    source_json_string = json.dumps(unique_list, indent=2)
    print("source_json_string:", source_json_string)

    # Capture raw context text for evaluation (RAGAS)
    # Use ALL retrieved chunks for evaluation context, not just the ones LLM claimed to use
    # This ensures RAGAS always has context even if LLM citation is broken
    all_context_text_list = [chunk.page_content for chunk in returned_chunks]
    all_context_text_json = json.dumps(all_context_text_list)
    
    # Also keep the "used" chunks context for comparison/debugging
    used_context_text_list = [chunk.page_content for chunk in used_chunks]
    used_context_text_json = json.dumps(used_context_text_list)
    
    print(f"[DEBUG] Retrieved {len(returned_chunks)} chunks, LLM used {len(used_chunks)} chunks")
    print(f"[DEBUG] all_context_text has {len(all_context_text_list)} items")
    print(f"[DEBUG] used_context_text has {len(used_context_text_list)} items")
    
    answer_text = final_response_obj["response"]
    if isinstance(answer_text, dict) or isinstance(answer_text, list):
        answer_text = json.dumps(answer_text)
    
    return {"answer": str(answer_text).strip(),
            "images": "[]",
            "citations": source_json_string if source_json_string else "[]",
            "context_text": all_context_text_json}  # Use ALL chunks for evaluation


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
        if hasattr(embeddingModel, "embed_image"):
            queries_embedded = embeddingModel.embed_image([temp_file.name])
        else:
            queries_embedded = embeddingModel.embed_documents(["Image query fallback"])
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

    import json
    return {"answer": "",
            "images": json.dumps(images_b64),
            "citations": "[]"}

