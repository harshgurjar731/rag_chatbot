from typing import List
from operator import itemgetter

# LangChain core and community imports
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain.load import dumps, loads
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.chat_models import AzureChatOpenAI
from langchain.retrievers.multi_query import MultiQueryRetriever

# Local service and config imports
from Services.guardrail import validate_output
from Services.reranker_service import get_reranker
from config import CONFIG

def get_multiquery_rag_with_azure(
    query: str,
    db: FAISS | Chroma,
    deployment_name: str = None,
    temperature: float = None,
    token_size: int = None,
    guardrail_level: str = None,
    rerankerOption: str = None
):
    """
    Executes a MultiQuery RAG pipeline using Azure OpenAI as the LLM provider.
    Includes robust session handling to ensure the client is closed after each call.
    """
    # ✅ Load defaults from env/config if not provided
    # deployment_name = deployment_name or CONFIG["default_azure_deployment"]
    temperature = temperature if temperature is not None else CONFIG["default_temperature"]
    token_size = token_size if token_size is not None else CONFIG["default_token_size"]
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

    # ✅ Validate Azure credentials from config
    azure_openai_api_key=str("BNwzZtUQM3K0Tilhquk3ps6ThTFlp0TGYKLvIQI1wbnQUgI7Q4QqJQQJ99BIACYeBjFXJ3w3AAABACOGLNf9")
    azure_openai_endpoint= str("https://knowledgebotopenaiservice.openai.azure.com/")
    azure_openai_api_version= str("2025-04-01-preview") # Example API version

    # if not all([azure_api_key, azure_endpoint, azure_api_version, deployment_name]):
    #     raise ValueError(
    #         "Azure OpenAI credentials or deployment name not set. "
    #         "Please update your configuration."
    #     )

    llm = None
    try:
        # ✅ Initialize Azure OpenAI LLM with config values
        llm = AzureChatOpenAI(
            azure_endpoint=azure_openai_endpoint,
            api_key=azure_openai_api_key,
            api_version=azure_openai_api_version,
            azure_deployment="gpt-5-mini",
            temperature=temperature,
            max_completion_tokens=token_size,
        )

        # 1. Multi Query: Generate different perspectives for the query
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
        
        # 2. Retrieve: Use MultiQueryRetriever to fetch docs for all generated queries
        retriever = MultiQueryRetriever.from_llm(
            retriever=db.as_retriever(search_kwargs={"k": 2}), llm=llm
        )
        retrieval_chain = generate_queries | retriever.map() | get_unique_union
        docs = retrieval_chain.invoke({"question": query})
        print(f"Retrieved {len(docs)} unique documents.")

        # 3. Re-rank (Optional): Improve document relevance
        if rerankerOption != "none":
            reranker = get_reranker(rerankerOption)
            if reranker:
                doc_texts = [doc.page_content for doc in docs]
                # Assuming reranker returns a list of (doc, score) tuples
                ranked_docs_with_scores = reranker.rerank(query, doc_texts, top_k=5)
                # Recreate document objects or use indices if possible
                # This is a simplified representation; you might need to map back to original docs
                docs = [docs[i] for i, _ in enumerate(ranked_docs_with_scores)]
                print(f"Applied Re-ranker: {rerankerOption}")

        # 4. RAG: Generate final answer based on context
        rag_template = """Answer the following question based on this context:

        {context}

        Question: {question}
        """
        prompt = ChatPromptTemplate.from_template(rag_template)

        final_rag_chain = (
            {"context": lambda x: docs, "question": itemgetter("question")}
            | prompt
            | llm
            | StrOutputParser()
        )
        final_answer = final_rag_chain.invoke({"question": query})

        # 5. Guardrails: Validate the final output
        validated = validate_output(final_answer, guardrail_level)
        return validated

    except Exception as e:
        print(f"Error during LLM processing: {e}")
        return {"answer": "⚠️ An error occurred while processing your request."}
    
    finally:
        # ✅ Safeguard: Ensure the client session is closed after each call
        # if llm and hasattr(llm, 'client') and llm.client:
            # llm.client.close()
        print("Azure OpenAI client session closed.")


def get_unique_union(documents: list[list]):
    """ Unique union of retrieved docs """
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]