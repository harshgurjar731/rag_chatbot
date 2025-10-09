from typing import List
from langchain.vectorstores import FAISS, Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.llms import HuggingFaceHub # optional if HuggingFace models are used
from pathlib import Path
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain.load import dumps, loads
from operator import itemgetter
from langchain_core.runnables import RunnablePassthrough
from langchain_community.chat_models import ChatOpenAI
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import DocumentCompressorPipeline
from langchain_community.document_compressors import FlashrankRerank
from langchain.schema import Document
import json

# Assuming these imports exist from your original code and project structure
from Services.guardrail import validate_output
# from Services.reranker_service import get_reranker # This is now defined below
from config import CONFIG

# Renamed function to reflect that it's no longer using multi-query
def get_rag_response(
    query: str,
    db: FAISS | Chroma,
    llm_model_name: str = None,
    temperature: float = None,
    token_size: int = None,
    guardrail_level: str = None,
    rerankerOption: str = None,
):
    """
    RAG pipeline using direct query retrieval, optional re-ranking, and
    detailed source information including chunks and metadata for citation.
    """

    # Load defaults from config if not provided (no change here)
    llm_model_name = llm_model_name or CONFIG["default_llm_model"]
    temperature = temperature if temperature is not None else CONFIG["default_temperature"]
    token_size = token_size if token_size is not None else CONFIG["default_token_size"]
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

    GROQ_API_KEY = CONFIG.get("groq_api_key")
    GROQ_API_BASE = CONFIG.get("groq_api_base")

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    # LLM init from env (no change here)
    llm = ChatOpenAI(
        openai_api_base=GROQ_API_BASE,
        openai_api_key=GROQ_API_KEY,
        model=llm_model_name,
        temperature=temperature,
        max_tokens=token_size,
    )

    # Base retriever for direct search
    base_retriever = db.as_retriever(search_kwargs={"k": 10})

    # Conditionally add re-ranking to the simplified pipeline
    if rerankerOption != "none":
        compressor = get_reranker(rerankerOption)
        if compressor:
            # The compression retriever now wraps the simple base_retriever
            retriever_chain = ContextualCompressionRetriever(
                base_compressor=compressor,
                base_retriever=base_retriever,
            )
        else:
            # Fallback to the base retriever if the compressor isn't found
            retriever_chain = base_retriever
    else:
        # If no re-ranking, the chain is just the simple retriever
        retriever_chain = base_retriever

    # The retriever_chain directly searches with the user's query.
    docs = retriever_chain.invoke(query)

    print(f"Retrieved Documents after re-ranking: {len(docs)}")

    # Format documents to include content and metadata for citation (no change here)
    def format_docs_for_context(docs: List[Document]):
        """Formats documents with a citation ID for the final chain."""
        context_string = ""
        citation_map = {}
        
        for i, doc in enumerate(docs):
            citation_id = i + 1
            # Ensure metadata values exist
            source = doc.metadata.get('source', 'N/A')
            page_number = doc.metadata.get('page_number', 'N/A')
            context_string += f"[Chunk {citation_id}] Source: {source}, Page: {page_number}\nContent: {doc.page_content}\n\n"
            citation_map[str(citation_id)] = doc.metadata
            
        return context_string, citation_map

    context_string, citation_map = format_docs_for_context(docs)

    # RAG prompt for the final answer generation (no change here)
    rag_template = """Answer the following question based on this context.

    Context:
    {context}

    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(rag_template)

    final_rag_chain = (
        {"context": RunnablePassthrough(), "question": itemgetter("question")}
        | prompt
        | llm
        | StrOutputParser()
    )

    final_answer = final_rag_chain.invoke({"context": context_string, "question": query})

    # Apply guardrails (no change here)
    validated = validate_output(final_answer, guardrail_level)

    if "⚠️ Response blocked" in validated["answer"]:
        return validated
    
    # Extract source links and prepare citation data (no change here)
    source_links = list({doc.metadata.get("source", "No source found") for doc in docs})

    # ✅ THIS NOW USES THE CORRECTED HELPER FUNCTION
    document_pages_dict = extract_sources_and_pages(citation_map)
    
    print(f"Sources used: {source_links}")
    print(f"Document Pages Dict: {document_pages_dict}")

    return {
        "answer": validated["answer"],
        "sources": source_links,
        "citation_map": citation_map,
        "chunks_used": docs, 
        "document_pages_dict": document_pages_dict
    }

# ----------------- ✅ UPDATED HELPER FUNCTION -----------------
def extract_sources_and_pages(citation_map: dict) -> list[dict]:
    """
    Prepares a list of dictionaries, mapping unique documents to a list of unique pages.

    Args:
        citation_map (dict): A dictionary where keys are citation IDs and values are
                             the metadata of the corresponding document chunk.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary maps a unique
                    document source (file path) to a sorted list of unique page numbers.
                    Example: [{"source": "path/to/doc.pdf", "pages": [1, 5, 10]}]
    """
    document_pages_dict = {}
    for citation_metadata in citation_map.values():
        source = citation_metadata.get("source")
        page_number = citation_metadata.get("page_number")
        
        # Ensure both source and page_number exist to create a valid citation
        if source and page_number is not None:
            if source not in document_pages_dict:
                document_pages_dict[source] = set()
            document_pages_dict[source].add(page_number)
    
    # Convert sets to sorted lists
    for source in document_pages_dict:
        document_pages_dict[source] = sorted(list(document_pages_dict[source]))
        
    # --- Convert the dictionary to the desired list of dictionaries format ---
    result_list = []
    for source, pages in document_pages_dict.items():
        result_list.append({"source": source, "pages": pages})
        
    return result_list


def get_reranker(reranker_option: str):
    """Factory function to get the correct reranker based on the option."""
    if reranker_option.lower() == "flashrank":
        # Ensure 'flashrank' is installed: pip install flashrank
        return FlashrankRerank() # model_name defaults are usually sufficient
    # Add other rerankers here if needed
    return None