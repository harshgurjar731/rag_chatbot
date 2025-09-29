from typing import List
from langchain.vectorstores import FAISS, Chroma
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.llms import HuggingFaceHub  # optional if HuggingFace models are used
from pathlib import Path
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain.load import dumps, loads
from operator import itemgetter
from langchain_core.runnables import RunnablePassthrough
from langchain_community.chat_models import ChatOpenAI
from Services.guardrail import validate_output
from Services.reranker_service import get_reranker
from config import CONFIG   # ✅ env-driven config
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFaceHub

def get_multiquery_retriever(
    query: str,
    db: FAISS | Chroma,
    llm_model_name: str = None,
    temperature: float = None,
    token_size: int = None,
    guardrail_level: str = None,
    rerankerOption: str = None,
):
    """RAG pipeline with source link extraction and optional re-ranking."""

    # ✅ Load defaults from config if not provided
    llm_model_name = llm_model_name or CONFIG["default_llm_model"]
    temperature = temperature if temperature is not None else CONFIG["default_temperature"]
    token_size = token_size if token_size is not None else CONFIG["default_token_size"]
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

    GROQ_API_KEY = CONFIG.get("groq_api_key")
    GROQ_API_BASE = CONFIG.get("groq_api_base")

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    # ✅ LLM init from env
    llm = ChatOpenAI(
        openai_api_base=GROQ_API_BASE,
        openai_api_key=GROQ_API_KEY,
        model=llm_model_name,
        temperature=temperature,
        max_tokens=token_size,
    )

    # Multi-query prompt (unchanged)
    template = """You are an AI assistant. Generate five 
    different versions of the given user question to retrieve relevant documents.
    Provide these alternative questions separated by newlines.
    Original question: {question}"""
    prompt_perspectives = ChatPromptTemplate.from_template(template)

    generate_queries = (
        prompt_perspectives
        | llm
        | StrOutputParser()
        | (lambda x: x.split("\n"))
    )

    retriever = MultiQueryRetriever.from_llm(
        retriever=db.as_retriever(search_kwargs={"k": 2}),
        llm=llm,
    )

    # Generate queries
    question = query
    generate_queries_output = generate_queries.invoke({"question": question})
    print("Generated Queries:", generate_queries_output)

    # Retrieve docs
    retrieval_chain = generate_queries | retriever.map() | get_unique_union
    docs = retrieval_chain.invoke({"question": question})

    print(f"Retrieved Documents: {len(docs)}")

    # ✅ Apply Re-ranker from env if enabled
    if rerankerOption != "none":
        reranker = get_reranker(rerankerOption)
        if reranker:
            doc_texts = [doc.page_content for doc in docs]
            ranked = reranker.rerank(query, doc_texts, top_k=5)
            docs = [doc for doc, _ in ranked]
            print("Applied Re-ranker:", rerankerOption)

    # ✅ Extract unique sources
    source_links = list({doc.metadata.get("source", "No source found") for doc in docs})
    print("Sources Used:")
    for src in source_links:
        print(" -", src)

    # RAG prompt (unchanged)
    rag_template = """Answer the following question based on this context.
    At the end of your answer, include: Sources: <link1>, <link2>

    {context}

    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(rag_template)

    final_rag_chain = (
        {"context": retrieval_chain, "question": itemgetter("question")}
        | prompt
        | llm
        | StrOutputParser()
    )

    final_answer = final_rag_chain.invoke({"question": question})

    # ✅ Apply guardrails (driven by env default if not passed)
    validated = validate_output(final_answer, guardrail_level)

    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    return {
        "answer": validated["answer"],
        "sources": source_links,
    }


# ----------- STEP 2: UNIQUE DOCS HELPER -----------
def get_unique_union(documents: list[list]):
    """Unique union of retrieved docs."""
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]


def format_docs_with_sources(docs):
    """Formats documents with their sources for the model."""
    formatted = []
    for doc in docs:
        src = doc.metadata.get("source", "No source found")
        formatted.append(f"[Source: {src}] {doc.page_content}")
    return "\n\n".join(formatted)
