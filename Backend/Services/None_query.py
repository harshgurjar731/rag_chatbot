# services/None_query.py (or your equivalent file)

from typing import List
from operator import itemgetter

from langchain.prompts import ChatPromptTemplate
from langchain.retrievers import ContextualCompressionRetriever
from langchain.schema import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.document_compressors import FlashrankRerank

# Assuming these imports exist from your project structure
from Services.guardrail import validate_output
from Services.reranker_service import get_reranker # You may need to create this helper
from config import CONFIG


# Renamed function to reflect that it's no longer using multi-query
def get_rag_response(
    query: str,
    db: FAISS | Chroma,
    llm: BaseChatModel,
    guardrail_level: str = None,
    reranker_option: str = None,
):
    """
    RAG pipeline using direct query retrieval, optional re-ranking, and
    detailed source information including chunks and metadata for citation.
    """
    # Load defaults from config if not provided
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    reranker_option = reranker_option or CONFIG["default_reranker_option"]

    # --- 1. Setup Retriever with Optional Re-ranking ---
    base_retriever = db.as_retriever(search_kwargs={"k": 10})

    if reranker_option != "none":
        compressor = get_reranker(reranker_option)
        retriever_chain = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=base_retriever,
        )
    else:
        retriever_chain = base_retriever

    docs = retriever_chain.invoke(query)

    # --- 2. Format Context and Create Citation Map ---
    def format_docs_for_context(docs: List[Document]):
        context_string = ""
        citation_map = {}
        for i, doc in enumerate(docs):
            citation_id = i + 1
            source = doc.metadata.get('source', 'N/A')
            page_number = doc.metadata.get('page_number', 'N/A')
            context_string += f"[Chunk {citation_id}] Source: {source}, Page: {page_number}\nContent: {doc.page_content}\n\n"
            citation_map[str(citation_id)] = doc.metadata
        return context_string, citation_map

    context_string, citation_map = format_docs_for_context(docs)

    # --- 3. Generate Final Answer ---
    rag_prompt = ChatPromptTemplate.from_template(
        "Answer the following question based on this context.\n\n"
        "Context:\n{context}\n\nQuestion: {question}"
    )
    final_rag_chain = (rag_prompt | llm | StrOutputParser())
    final_answer = final_rag_chain.invoke({"context": context_string, "question": query})

    # --- 4. Post-processing and Formatting Output ---
    validated = validate_output(final_answer, guardrail_level)
    
    # ✅ Ensure a dictionary is ALWAYS returned
    if "⚠️ Response blocked" in validated["answer"]:
        return validated # This returns a dictionary like {"answer": "Blocked..."}

    document_pages_list = extract_sources_and_pages(citation_map)
    source_links = list({doc["source"] for doc in document_pages_list})

    # The main success path also returns a dictionary
    return {
        "answer": validated["answer"],
        "sources": source_links,
        "citation_map": citation_map,
        "chunks_used": docs,
        "document_pages_dict": document_pages_list,
    }

# Ensure these helper functions are also in the file
def extract_sources_and_pages(citation_map: dict) -> list[dict]:
    """Prepares a list of dictionaries, mapping unique documents to a list of unique pages."""
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

def get_reranker(reranker_option: str):
    """Factory function to get the correct reranker based on the option."""
    if reranker_option.lower() == "flashrank":
        from langchain_community.document_compressors import FlashrankRerank
        return FlashrankRerank()
    return None