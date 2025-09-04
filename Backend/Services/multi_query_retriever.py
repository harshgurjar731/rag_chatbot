# from langchain.vectorstores import FAISS, Chroma
# from langchain.retrievers.multi_query import MultiQueryRetriever
# from langchain.embeddings import HuggingFaceEmbeddings
# from langchain.llms import HuggingFaceHub  # use OpenAI if you're using OpenAI models
# import os
# from pathlib import Path
# from langchain_core.output_parsers import StrOutputParser
# from langchain.prompts import ChatPromptTemplate
# from langchain.load import dumps, loads
# from operator import itemgetter 
# from langchain_core.runnables import RunnablePassthrough
# from langchain_community.chat_models import ChatOpenAI  # or ChatHuggingFace if you're using HuggingFace models

# def get_multiquery_retriever(query: str, db: FAISS|Chroma, llm_model_name: str):

#     "   Create a MultiQueryRetriever using the provided vector store."

#     # Choose your LLM for multi-query generation
#     # For open source, replace with 
#    # ✅ Use open-source LLM via HuggingFaceHub (Mistral model)
#     GROQ_API_KEY = "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"
#     if not llm_model_name:
#         raise ValueError("LLM model name must be provided")
#     llm = ChatOpenAI(
#     openai_api_base="https://api.groq.com/openai/v1",
#     openai_api_key=GROQ_API_KEY,
#     model=llm_model_name,  # or use "llama3-70b-8192", "gemma-7b-it", etc.
#     temperature=0.0,
#     max_tokens=256
#     )
#     # Define the prompt template for generating multi-queries
 
#     # Multi Query: Different Perspectives
#     template = """You are an AI language model assistant. Your task is to generate five 
#     different versions of the given user question to retrieve relevant documents from a vector 
#     database. By generating multiple perspectives on the user question, your goal is to help
#     the user overcome some of the limitations of the distance-based similarity search. 
#     Provide these alternative questions separated by newlines. Original question: {question}"""


#     prompt_perspectives = ChatPromptTemplate.from_template(template)

#     generate_queries = (
#         prompt_perspectives 
#         | llm 
#         | StrOutputParser() 
#         | (lambda x: x.split("\n"))
#     )

#     retriever = MultiQueryRetriever.from_llm(retriever=db.as_retriever(search_kwargs={"k": 2}), llm=llm)

#     # Retrieve
#     question = query

#     generate_queries_output = generate_queries.invoke({"question": question})
#     print("Generated Queries:", generate_queries_output)
#     retrieval_chain = generate_queries | retriever.map() | get_unique_union
#     docs = retrieval_chain.invoke({"question":question})
#     len(docs)
#     print("Retrieved Documents:", len(docs))
#     # RAG
#     rag_template = """Answer the following question based on this context:

#     {context}

#     Question: {question}
#     """
#     prompt = ChatPromptTemplate.from_template(rag_template)

#     # Combine the retrieval chain with the prompt and LLM
#     # Note: Ensure the context is passed correctly to the prompt
#     # The context will be the retrieved documents
#     final_rag_chain = (
#         {"context": retrieval_chain, 
#         "question": itemgetter("question")} 
#         | prompt
#         | llm
#         | StrOutputParser()
#     )

#     final_rag_chain_output = final_rag_chain.invoke({"question":question})
#     print("Final RAG Chain Output:", final_rag_chain_output)
#     return final_rag_chain_output
    

# def get_unique_union(documents: list[list]):
#     """ Unique union of retrieved docs """
#     # Flatten list of lists, and convert each Document to string
#     flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
#     # Get unique documents
#     unique_docs = list(set(flattened_docs))
#     # Return
#     return [loads(doc) for doc in unique_docs]




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
# ✅ Import our guardrail utilities
from Services.guardrail import validate_output  

def get_multiquery_retriever(query: str, db: FAISS | Chroma, llm_model_name: str,temperature:float,token_size:float = 256,guardrail_level: str="none"):
    """RAG pipeline with source link extraction."""

    # GROQ_API_KEY = "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"
    GROQ_API_KEY = "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"


    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    llm = ChatOpenAI(
        openai_api_base="https://api.groq.com/openai/v1",
        openai_api_key=GROQ_API_KEY,
        model=llm_model_name,
        temperature=temperature,
        max_tokens=token_size
    )

    # Multi-query prompt
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
        llm=llm
    )

    # ✅ Setup Guardrails depending on level
    if guardrail_level == "none":
        guard = None  # no validation
    elif guardrail_level == "basic":
        guard = Guard().use(ToxicLanguage(threshold=0.9))  # lenient
    elif guardrail_level == "strict":
        guard = Guard().use(ToxicLanguage(threshold=0.5))  # strict
    elif guardrail_level == "custom":
        guard = Guard().use(
            ToxicLanguage(threshold=0.7, validation_method="sentence")
        )
    else:
        guard = None

    question = query
    generate_queries_output = generate_queries.invoke({"question": question})
    print("Generated Queries:", generate_queries_output)

    retrieval_chain = generate_queries | retriever.map() | get_unique_union
    docs = retrieval_chain.invoke({"question": question})
    print(f"Retrieved Documents: {len(docs)}")

    # ✅ Extract unique sources
    source_links = list({doc.metadata.get("source", "No source found") for doc in docs})
    print("Sources Used:")
    for src in source_links:
        print(" -", src)

    # RAG prompt
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

   # ✅ Apply guardrails (toxicity, PII etc.)
    validated = validate_output(final_answer, guardrail_level)

    # If guard blocked, return directly
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    final_answer = validated["answer"]
    return {
        "answer": final_answer,
        "sources": source_links
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
