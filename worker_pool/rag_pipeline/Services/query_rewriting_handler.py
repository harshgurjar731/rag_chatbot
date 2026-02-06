"""
This module handles query rewriting and chunk fusion strategies for the RAG pipeline.

It includes functions for MultiQuery, StepBack, and History-Based query expansion/rewriting,
as well as methods for combining retrieved chunks (Union, RRF).
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_models import ChatOpenAI
from typing import List,  Tuple
from rag_pipeline.LLMs.llm_model_protocol import ChatOpenAI, AzureChatOpenAI
from rag_pipeline.Config.rag_config import RAG_CONFIG
from rag_pipeline.Config.rag_prompts import RAG_PROMPTS
from langchain_core.load import dumps, loads
from collections import defaultdict

def handle_query_rewriting(
        rewritingType: str, 
        query: str, 
        llm: ChatOpenAI | AzureChatOpenAI | None) -> List[str]:
    """
    Generate multiple query variations based on the specified rewriting strategy.

    Args:
        rewritingType (str): The type of rewriting to apply (e.g., "multiquery", "ragfusion", "stepback").
        query (str): The original user query.
        llm (ChatOpenAI | AzureChatOpenAI | None): The LLM to use for generation.

    Returns:
        List[str]: A list of rewritten queries (chunked or stepback variations).
    """
    rt = (rewritingType or "").lower()
    if (rt == "multiquery" or rt == "ragfusion"):
        return multiquery_generator(query=query, llm= llm)
    elif (rt == "stepback"):
        return stepback_query_generator(
            query=query,
            llm=llm
        )
    else: 
        return [query]

def handle_chunk_union(
        rewritingType: str,
        retrieved_chunks: List[str]) -> List[str]:
    """
    Combine and deduplicate chunks retrieved from multiple queries.

    Args:
        rewritingType (str): The strategy used for retrieval ("multiquery", "stepback", "ragfusion").
        retrieved_chunks (List[str]): A list of lists of documents/chunks.

    Returns:
        List[str]: A flattened, unique, and optionally re-ranked list of chunks.
    """
    rt = (rewritingType or "").lower()
    if (rt == "multiquery" or rt == "stepback"):
        return _get_unique_union(retrieved_chunks)
    elif (rt == "ragfusion"):
        return _reciprocal_rank_fusion(retrieved_chunks, RAG_CONFIG["default_ragfusion_rrf_k"])
    

def multiquery_generator(
        query: str, 
        llm: ChatOpenAI | AzureChatOpenAI | None) -> List[str]:
    """
    Generate multiple perspectives of the same query (Multi-Query Expansion).

    Args:
        query (str): The original query.
        llm: The language model.

    Returns:
        List[str]: A list of generated queries.
    """
    template = RAG_PROMPTS["query_rewriting_multi_prompt"]
    prompt_perspectives = ChatPromptTemplate.from_template(template)
    generate_queries = prompt_perspectives | llm | StrOutputParser() | (lambda x: x.split("\n"))
    candidate_queries = generate_queries.invoke({"question": query})
    return [query for query in candidate_queries if query != ""]

def stepback_query_generator(
        query: str, 
        llm: ChatOpenAI | AzureChatOpenAI | None) -> List[str]:
    """
    Generate a step-back (more abstract) query to broaden the search context.

    Args:
        query (str): The original query.
        llm: The language model.

    Returns:
        List[str]: A list containing the original query and the step-back query.
    """
    stepback_template = RAG_PROMPTS["query_rewriting_stepback_prompt"]
    stepback_prompt = ChatPromptTemplate.from_template(stepback_template)
    generate_stepback_query = stepback_prompt | llm | StrOutputParser()
    stepback_query = generate_stepback_query.invoke({"question": query})
    return [query, stepback_query]

def history_based_query_generator(
        query: str,
        llm: ChatOpenAI | AzureChatOpenAI | None,
        message_history: List[tuple[str, str]]) -> str:
    """
    Reformulate the query to be standalone by incorporating context from message history.

    Args:
        query (str): The latest user query.
        llm: The language model.
        message_history (List[tuple[str, str]]): The conversation history.

    Returns:
        str: The reformullated, standalone query.
    """
    query_rewriter_prompt = RAG_PROMPTS["query_rewriting_history_based"]
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [("system", query_rewriter_prompt), MessagesPlaceholder("chat_history"), ("user", "{input}"),]
    )
    q_prompt = contextualize_q_prompt | llm | StrOutputParser()
    retriever_query = q_prompt.invoke({"input": query, "chat_history": message_history})
    return retriever_query

def _get_unique_union(documents: list[list]):
    """
    Flatten a list of document lists and remove duplicates.
    """
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]

def _reciprocal_rank_fusion(all_docs: list[list], k: int = 60):
    """
    Apply Reciprocal Rank Fusion (RRF) to combine results from multiple document lists.

    Args:
        all_docs (list[list]): List of document lists.
        k (int): RRF constant.

    Returns:
        list: A sorted list of unique documents based on RRF scores.
    """
    scores = defaultdict(float)
    for docs in all_docs:
        for rank, doc in enumerate(docs):
            doc_id = dumps(doc)
            scores[doc_id] += 1 / (rank + k)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [loads(doc_id) for doc_id, _ in ranked]
