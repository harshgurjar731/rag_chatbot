from typing import List
from langchain.vectorstores import FAISS, Chroma
from langchain.retrievers import MultiQueryRetriever, ContextualCompressionRetriever
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain.schema import Document
from operator import itemgetter

# Assuming these imports exist from your project structure
from Services.guardrail import validate_output
from Services.reranker_service import get_reranker
from config import CONFIG

def get_multiquery_retriever_without_sources(
    query: str,
    db: FAISS | Chroma,
    llm: BaseChatModel,  # ✅ CHANGED: Accept the configured LLM object
    guardrail_level: str = None,
    reranker_option: str = None, # ✅ CHANGED: Switched to snake_case
):
    """
    Creates a RAG pipeline using a MultiQueryRetriever and optional re-ranking,
    returning only the final answer without source details.
    """
    # ✅ Load defaults from config if not provided
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    reranker_option = reranker_option or CONFIG["default_reranker_option"]

    # ❌ REMOVED: All hardcoded LLM instantiation logic (for both Groq and Azure).
    # The 'llm' object is now passed in, fully configured by the LLMFactory.

    # --- 1. Setup Retriever with Optional Re-ranking ---
    # The MultiQueryRetriever uses the LLM to generate different questions
    base_retriever = db.as_retriever(search_kwargs={"k": 10})
    multiquery_retriever = MultiQueryRetriever.from_llm(
        retriever=base_retriever,
        llm=llm
    )

    # Conditionally wrap the retriever with a re-ranker
    if reranker_option != "none":
        compressor = get_reranker(reranker_option)
        retriever_chain = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=multiquery_retriever,
        )
    else:
        retriever_chain = multiquery_retriever

    # --- 2. Define the RAG Chain ---
    # Helper function to format the retrieved documents into a single string
    def format_docs(docs: List[Document]) -> str:
        return "\n\n".join(doc.page_content for doc in docs)

    rag_prompt = ChatPromptTemplate.from_template(
        "Answer the following question based on this context:\n\n"
        "Context:\n{context}\n\nQuestion: {question}"
    )

    # This is the full LCEL (LangChain Expression Language) chain
    final_rag_chain = (
        {
            "context": retriever_chain | format_docs, # Retrieve and format docs
            "question": RunnablePassthrough()         # Pass the original query through
        }
        | rag_prompt
        | llm
        | StrOutputParser()
    )

    # --- 3. Invoke Chain and Apply Post-processing ---
    final_answer = final_rag_chain.invoke(query)

    # Apply guardrails to the final answer
    validated = validate_output(final_answer, guardrail_level)
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    return {"answer": validated["answer"]}

# ❌ REMOVED: The get_unique_union function is no longer necessary,
# as the ContextualCompressionRetriever and standard retriever handling
# effectively manage document uniqueness.