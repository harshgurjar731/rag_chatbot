from typing import List
from langchain.vectorstores import FAISS, Chroma
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.llms import HuggingFaceHub  # use OpenAI if you're using OpenAI models
import os
from pathlib import Path
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain.load import dumps, loads
from operator import itemgetter 
from langchain_core.runnables import RunnablePassthrough
from langchain_community.chat_models import ChatOpenAI
from guardrails import Guard
from guardrails.hub import ToxicLanguage
from Services.guardrail import validate_output  
from Services.reranker_service import get_reranker   # ✅ Import reranker utility


def get_multiquery_retriever_without_sources(
    query: str,
    db: FAISS | Chroma,
    llm_model_name: str,
    temperature: float,
    token_size: float = 256,
    guardrail_level: str = "none",
    rerankerOption: str = "none"
):
    """Create a MultiQueryRetriever pipeline with optional re-ranking."""

    GROQ_API_KEY = "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"

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    llm = ChatOpenAI(
        openai_api_base="https://api.groq.com/openai/v1",
        openai_api_key=GROQ_API_KEY,
        model=llm_model_name,
        temperature=temperature,
        max_tokens=token_size,
    )

    # Multi Query: Different Perspectives
    template = """You are an AI language model assistant. Your task is to generate five 
    different versions of the given user question to retrieve relevant documents from a vector 
    database. By generating multiple perspectives on the user question, your goal is to help
    the user overcome some of the limitations of the distance-based similarity search. 
    Provide these alternative questions separated by newlines. Original question: {question}"""

    prompt_perspectives = ChatPromptTemplate.from_template(template)

    generate_queries = (
        prompt_perspectives
        | llm
        | StrOutputParser()
        | (lambda x: x.split("\n"))
    )

    retriever = MultiQueryRetriever.from_llm(
        retriever=db.as_retriever(search_kwargs={"k": 2}), llm=llm
    )

    # Retrieve
    question = query
    generate_queries_output = generate_queries.invoke({"question": question})
    print("Generated Queries:", generate_queries_output)

    retrieval_chain = generate_queries | retriever.map() | get_unique_union
    docs = retrieval_chain.invoke({"question": question})
    print("Retrieved Documents:", len(docs))

    # ✅ Apply re-ranker (if selected)
    if rerankerOption != "none":
        reranker = get_reranker(rerankerOption)
        if reranker:
            doc_texts = [doc.page_content for doc in docs]
            ranked = reranker.rerank(question, doc_texts, top_k=5)
            docs = [doc for doc, _ in ranked]
            print("Applied Re-ranker:", rerankerOption)

    # RAG
    rag_template = """Answer the following question based on this context:

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

    # ✅ Apply guardrails
    validated = validate_output(final_answer, guardrail_level)

    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    final_answer = validated["answer"]
    print("Final RAG Chain Output:", final_answer)

    return {"answer": final_answer}


def get_unique_union(documents: list[list]):
    """ Unique union of retrieved docs """
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]
