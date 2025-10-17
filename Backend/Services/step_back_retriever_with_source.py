from operator import itemgetter
from typing import List

from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS, Chroma
from langchain.load import dumps, loads

from config import CONFIG
from Services.guardrail import validate_output
from Services.reranker_service import get_reranker

def get_stepback_retriever_with_sources(
    query: str,
    db: FAISS | Chroma,
    llm: BaseChatModel,
    guardrail_level: str = None,
    reranker_option: str = None,
):
    """Step-Back RAG pipeline with guardrails, source tracking & optional re-ranking."""
    # Load defaults from config
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    reranker_option = reranker_option or CONFIG["default_reranker_option"]

    # --- 1. Generate Step-Back Query ---
    stepback_template = """You are an AI assistant. Reformulate the following user question into
    a broader 'step-back' version that captures general background knowledge needed to answer it.

    Question: {question}

    Provide only the step-back reformulated question as output.
    """
    stepback_prompt = ChatPromptTemplate.from_template(stepback_template)
    generate_stepback_query = stepback_prompt | llm | StrOutputParser()
    stepback_query = generate_stepback_query.invoke({"question": query})
    print("Step-Back Reformulated Query:", stepback_query)

    # --- 2. Retrieve Documents ---
    retriever = db.as_retriever(search_kwargs={"k": 3})
    docs_main = retriever.invoke(query)
    docs_stepback = retriever.invoke(stepback_query)

    # Merge documents from original and step-back queries
    combined_docs = get_unique_union([docs_main, docs_stepback])
    print("Retrieved Documents (combined):", len(combined_docs))

    # --- 3. Conditionally Re-rank ---
    if reranker_option != "none":
        reranker = get_reranker(reranker_option)
        if reranker:
            content_to_doc_map = {doc.page_content: doc for doc in combined_docs}
            doc_texts = [doc.page_content for doc in combined_docs]

            ranked_results = reranker.rank(
                query=query,
                docs=doc_texts,
                top_k=CONFIG.get("default_reranker_top_k", 5)
            )

            reranked_docs = [content_to_doc_map[result["text"]] for result in ranked_results if result["text"] in content_to_doc_map]
            combined_docs = reranked_docs
            print(f"Applied Re-ranker: {reranker_option}, Final Docs: {len(combined_docs)}")

    # --- 4. Context Formatting & Citation Mapping (ADDED LOGIC) ---
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

    context_string, citation_map = format_docs_for_context(combined_docs)

    # --- 5. Generate Final Answer ---
    rag_template = """Answer the following question using the provided context.

    Context:
    {context}

    Question: {question}
    """
    rag_prompt = ChatPromptTemplate.from_template(rag_template)

    rag_chain = (
        rag_prompt
        | llm
        | StrOutputParser()
    )

    final_answer = rag_chain.invoke({"context": context_string, "question": query})

    # --- 6. Apply Guardrails and Format Output (UPDATED LOGIC) ---
    validated = validate_output(final_answer, guardrail_level)
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    document_pages_list = extract_sources_and_pages(citation_map)
    source_links = list({doc["source"] for doc in document_pages_list})

    return {
        "answer": validated["answer"],
        "sources": source_links,
        "document_pages_dict": document_pages_list,
        "citation_map": citation_map,
        "chunks_used": combined_docs,
    }


def get_unique_union(documents: list[list]):
    """Unique union of retrieved docs."""
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]


# Helper function for citation processing (ADDED)
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