import re  # ❇️ 1. NEW IMPORT
from typing import List
from operator import itemgetter
from collections import defaultdict

from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS, Chroma
from langchain.load import dumps, loads

# Assuming these imports exist from your project structure
from Services.guardrail import validate_output
from Services.reranker_service import get_reranker
from config import CONFIG

def get_ragfusion_retriever_with_sources(
    query: str,
    db: FAISS | Chroma,
    llm: BaseChatModel,
    guardrail_level: str = None,
    reranker_option: str = None,
):
    """RAG Fusion Retrieval chain using Reciprocal Rank Fusion (with optional re-ranking)."""
    # Load defaults from config
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    reranker_option = reranker_option or CONFIG["default_reranker_option"]

    # --- 1. Generate Multiple Queries ---
    fusion_prompt = ChatPromptTemplate.from_template(
        "Generate five diverse rephrasings of the following user query. "
        "Separate each by a newline.\n"
        "Original question: {question}"
    )
    generate_queries = (
        fusion_prompt | llm | StrOutputParser() | (lambda x: x.split("\n"))
    )
    candidate_queries = generate_queries.invoke({"question": query})

    # --- 2. Retrieve Documents for Each Query ---
    retriever = db.as_retriever(search_kwargs={"k": CONFIG.get("default_ragfusion_top_k", 10)})
    all_retrieved = [retriever.invoke(cq) for cq in candidate_queries]

    # --- 3. Fuse and Re-rank Documents ---
    fused_docs = reciprocal_rank_fusion(all_retrieved, k=CONFIG.get("default_ragfusion_rrf_k", 60))

    # Conditionally apply a re-ranker
    if reranker_option != "none":
        reranker = get_reranker(reranker_option)
        if reranker:
            content_to_doc_map = {doc.page_content: doc for doc in fused_docs}
            doc_texts = [doc.page_content for doc in fused_docs]
            
            ranked_results = reranker.rank(query=query, docs=doc_texts, top_k=5)
            
            reranked_docs = [content_to_doc_map[result["text"]] for result in ranked_results if result["text"] in content_to_doc_map]
            fused_docs = reranked_docs
            print(f"Applied Re-ranker: {reranker_option}, Final Docs: {len(fused_docs)}")

    # --- 4. Context Formatting & Citation Mapping ---
    def format_docs_for_context(docs: List[Document]):
        """Formats docs and creates a map for citations."""
        context_string = ""
        citation_map = {}
        for i, doc in enumerate(docs):
            citation_id = i + 1
            source = doc.metadata.get('source', 'N/A')
            page = doc.metadata.get('page_number', 'N/A')
            context_string += f"[Chunk {citation_id}] Source: {source}, Page: {page}\nContent: {doc.page_content}\n\n"
            citation_map[str(citation_id)] = doc.metadata
        return context_string, citation_map

    context_string, citation_map = format_docs_for_context(fused_docs)

    # --- 5. Generate Final Answer ---
    # ❇️ 2. UPDATED PROMPT
    rag_prompt = ChatPromptTemplate.from_template(
        "You are an AI assistant. Answer the user's question based *only* on the context provided.\n"
        "Follow these rules:\n"
        "1. State the answer clearly.\n"
        "2. After the answer, cite the specific [Chunk ID] you used. For example: 'The sky is blue [Chunk 1].'\n"
        "3. If you use information from multiple chunks, cite all of them. For example: 'The sky is blue [Chunk 1] and the grass is green [Chunk 3].'\n"
        "4. If no chunk provides the answer, say 'I cannot answer this question based on the provided context.'\n\n"
        "Context:\n{context}\n\nQuestion: {question}"
    )

    final_rag_chain = (
        rag_prompt
        | llm
        | StrOutputParser()
    )

    final_answer = final_rag_chain.invoke({"context": context_string, "question": query})

    # --- 6. Post-processing (Guardrails and Source Extraction) ---
    # ❇️ 4. UPDATED POST-PROCESSING LOGIC
    validated = validate_output(final_answer, guardrail_level)
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    # Parse the answer to find *only* the cited chunks
    filtered_citation_map = parse_citations_from_answer(
        validated["answer"],
        citation_map
    )

    # Pass the *filtered* map to your existing function
    document_pages_list = extract_sources_and_pages(filtered_citation_map)
    source_links = list({doc["source"] for doc in document_pages_list})

    return {
        "answer": validated["answer"],
        "sources": source_links,
        "document_pages_dict": document_pages_list,
        "citation_map": filtered_citation_map, # Return the filtered map
        "chunks_used": fused_docs, # Note: This still shows all *retrieved* docs
    }

def reciprocal_rank_fusion(all_docs: list[list], k: int = 60):
    """Reciprocal Rank Fusion (RRF) to merge ranked document lists."""
    scores = defaultdict(float)
    for docs in all_docs:
        for rank, doc in enumerate(docs):
            doc_id = dumps(doc)
            scores[doc_id] += 1 / (rank + k)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [loads(doc_id) for doc_id, _ in ranked]


# ❇️ 3. NEW HELPER FUNCTION
def parse_citations_from_answer(answer: str, citation_map: dict) -> dict:
    """
    Parses [Chunk ID] tags from the LLM's answer and creates a
    new, filtered citation_map containing only the cited sources.
    """
    # Find all unique chunk IDs cited in the answer
    chunk_ids_found = re.findall(r"\[Chunk (\d+)\]", answer)
    unique_chunk_ids = sorted(list(set(chunk_ids_found)))

    # Build the filtered map
    filtered_map = {}
    for chunk_id in unique_chunk_ids:
        if chunk_id in citation_map:
            filtered_map[chunk_id] = citation_map[chunk_id]
        else:
            # This case should rarely happen if the prompt is good
            print(f"Warning: LLM cited a chunk ID ({chunk_id}) not in the citation_map.")

    # If no citations were found, return the full map as a fallback
    if not filtered_map:
        return citation_map

    return filtered_map


# Helper function for citation processing
def extract_sources_and_pages(citation_map: dict) -> list[dict]:
    """
    Prepares a list of dictionaries, mapping unique documents to a list of unique pages.
    """
    document_pages = {}
    for citation_metadata in citation_map.values():
        source = citation_metadata.get("source")
        page_number = citation_metadata.get("page_number")

        if source and page_number is not None:
            if source not in document_pages:
                document_pages[source] = set()
            document_pages[source].add(page_number)

    result_list = []
    for source, pages in document_pages.items():
        result_list.append({"source": source, "pages": sorted(list(pages))})

    return result_list