import re  # ❇️ 1. NEW IMPORT
from typing import List
from langchain.vectorstores import FAISS, Chroma
from langchain.retrievers import MultiQueryRetriever, ContextualCompressionRetriever
from langchain.schema import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter

# Assuming these imports exist from your project structure
from Services.guardrail import validate_output
from Services.reranker_service import get_reranker
from config import CONFIG


def get_multiquery_retriever(
    query: str,
    db: FAISS | Chroma,
    llm: BaseChatModel,
    guardrail_level: str = None,
    reranker_option: str = None,
):
    """
    RAG pipeline with multi-query retrieval, optional re-ranking, and
    detailed source information including chunks and metadata for citation.
    """
    # Load defaults from config if not provided
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    reranker_option = reranker_option or CONFIG["default_reranker_option"]

    # --- 1. Multi-Query Generation ---
    generate_queries_prompt = ChatPromptTemplate.from_template(
        "You are an AI assistant. Generate five different versions of the given user "
        "question to retrieve relevant documents.\n"
        "Provide these alternative questions separated by newlines.\n"
        "Original question: {question}"
    )
    generate_queries = (
        generate_queries_prompt
        | llm
        | StrOutputParser()
        | (lambda x: x.split("\n"))
    )

    # --- 2. Retrieval with Optional Re-ranking ---
    base_retriever = db.as_retriever(search_kwargs={"k": 10})
    multiquery_retriever = MultiQueryRetriever.from_llm(
        retriever=base_retriever,
        llm=llm,
    )

    # Conditionally add the re-ranking step
    if reranker_option != "none":
        compressor = get_reranker(reranker_option)
        retriever_chain = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=multiquery_retriever,
        )
    else:
        retriever_chain = multiquery_retriever

    # Invoke the retrieval chain to get the most relevant documents
    docs = retriever_chain.invoke(query)

    # --- 3. Context Formatting & Citation Mapping ---
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

    context_string, citation_map = format_docs_for_context(docs)

    # --- 4. Final RAG Chain for Answer Generation ---
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

    # This chain takes the formatted context and the original query to generate the final answer.
    final_rag_chain = (
        rag_prompt
        | llm
        | StrOutputParser()
    )

    final_answer = final_rag_chain.invoke({"context": context_string, "question": query})

    # --- 5. Post-processing (Guardrails and Source Extraction) ---
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
        "chunks_used": docs, # Note: This still shows all *retrieved* docs
    }


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