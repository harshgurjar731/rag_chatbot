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
    llm: BaseChatModel,  # ✅ CHANGED: Pass the configured LLM object directly
    guardrail_level: str = None,
    reranker_option: str = None, # ✅ CHANGED: Switched to snake_case for consistency
):
    """
    RAG pipeline with multi-query retrieval, optional re-ranking, and
    detailed source information including chunks and metadata for citation.
    """
    # ✅ Load defaults from config if not provided
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    reranker_option = reranker_option or CONFIG["default_reranker_option"]

    # ❌ REMOVED: No longer need to load model names, keys, or instantiate the LLM here.
    # The 'llm' object is now passed in, fully configured.

    # --- 1. Multi-Query Generation ---
    # The LLM passed into the function is used here to generate query variations.
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
        llm=llm, # The LLM is also used here to parse the queries
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
    rag_prompt = ChatPromptTemplate.from_template(
        "Answer the following question based on this context.\n\n"
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
    validated = validate_output(final_answer, guardrail_level)
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    document_pages_list = extract_sources_and_pages(citation_map)
    source_links = list({doc["source"] for doc in document_pages_list})

    return {
        "answer": validated["answer"],
        "sources": source_links,
        "document_pages_dict": document_pages_list, # Renamed for clarity in the next step
        "citation_map": citation_map,
        "chunks_used": docs,
    }

# This helper function is well-written and correct. No changes were needed.
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