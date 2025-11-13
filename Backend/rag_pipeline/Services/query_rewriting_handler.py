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
        llm: ChatOpenAI|AzureChatOpenAI|None) -> List[str]:
    if (rewritingType.lower() == "multiquery" or rewritingType.lower() == "ragfusion"):
        return multiquery_generator(query=query, llm= llm)
    elif (rewritingType.lower() == "stepback"):
        return stepback_query_generator(
            query=query,
            llm=llm
        )
    else: 
        return [query]

def handle_chunk_union(
        rewritingType: str,
        retrieved_chunks: List[str]) -> List[str]:
    if (rewritingType.lower() == "multiquery" or rewritingType.lower() == "stepback"):
        return _get_unique_union(retrieved_chunks)
    elif (rewritingType.lower() == "ragfusion"):
        return _reciprocal_rank_fusion(retrieved_chunks, RAG_CONFIG["default_ragfusion_rrf_k"])
    

def multiquery_generator(
        query: str, 
        llm: ChatOpenAI|AzureChatOpenAI|None) -> List[str]:

    template = RAG_PROMPTS["query_rewriting_multi_prompt"]
    prompt_perspectives = ChatPromptTemplate.from_template(template)
    generate_queries = prompt_perspectives | llm | StrOutputParser() | (lambda x: x.split("\n"))
    candidate_queries = generate_queries.invoke({"question": query})
    return [query for query in candidate_queries if query != ""]

def stepback_query_generator(
        query: str, 
        llm: ChatOpenAI|AzureChatOpenAI|None) -> List[str]:
    
    stepback_template = RAG_PROMPTS["query_rewriting_stepback_prompt"]
    stepback_prompt = ChatPromptTemplate.from_template(stepback_template)
    generate_stepback_query = stepback_prompt | llm | StrOutputParser()
    stepback_query = generate_stepback_query.invoke({"question": query})
    return [query, stepback_query]

def history_based_query_generator(
        query: str,
        llm: ChatOpenAI|AzureChatOpenAI|None,
        message_history: List[tuple[str, str]]) -> str:
    query_rewriter_prompt = RAG_PROMPTS["query_rewriting_history_based"]
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [("system", query_rewriter_prompt), MessagesPlaceholder("chat_history"), ("user", "{input}"),]
    )
    q_prompt = contextualize_q_prompt | llm | StrOutputParser()
    retriever_query = q_prompt.invoke({"input": query, "chat_history": message_history})
    return retriever_query

def _get_unique_union(documents: list[list]):
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]

def _reciprocal_rank_fusion(all_docs: list[list], k: int = 60):
    scores = defaultdict(float)
    for docs in all_docs:
        for rank, doc in enumerate(docs):
            doc_id = dumps(doc)
            scores[doc_id] += 1 / (rank + k)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [loads(doc_id) for doc_id, _ in ranked]
