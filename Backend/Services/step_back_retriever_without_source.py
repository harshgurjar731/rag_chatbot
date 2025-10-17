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

def get_stepback_retriever_without_sources(
    query: str,
    db: FAISS | Chroma,
    llm: BaseChatModel,  # ✅ CHANGED: Accept the configured LLM object
    guardrail_level: str = None,
    reranker_option: str = None, # ✅ CHANGED: Switched to snake_case
):
    """Step-Back RAG pipeline without sources, with guardrails & optional re-ranking."""
    # ✅ Load defaults from config
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    reranker_option = reranker_option or CONFIG["default_reranker_option"]

    # ❌ REMOVED: All hardcoded LLM instantiation logic is gone.
    # The 'llm' object is passed in, fully configured by your LLMFactory.

    # --- 1. Generate Step-Back Query ---
    stepback_prompt = ChatPromptTemplate.from_template(
        "You are an AI assistant. Reformulate the following user question into "
        "a broader 'step-back' version that captures general background knowledge needed to answer it.\n\n"
        "Question: {question}\n\n"
        "Provide only the step-back reformulated question as output."
    )
    generate_stepback_query = stepback_prompt | llm | StrOutputParser()
    stepback_query = generate_stepback_query.invoke({"question": query})
    print("Step-Back Reformulated Query:", stepback_query)

    # --- 2. Retrieve and Merge Documents ---
    retriever = db.as_retriever(search_kwargs={"k": 3})
    docs_main = retriever.invoke(query)
    docs_stepback = retriever.invoke(stepback_query)

    combined_docs = get_unique_union([docs_main, docs_stepback])
    print("Retrieved Documents (combined):", len(combined_docs))

    # --- 3. Conditionally Re-rank ---
    if reranker_option != "none":
        reranker = get_reranker(reranker_option)
        if reranker:
            # ✅ OPTIMIZED: Use a dictionary for efficient lookup.
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

    # --- 4. Generate Final Answer ---
    rag_prompt = ChatPromptTemplate.from_template(
        "Answer the following question using the provided context:\n\n"
        "Context:\n{context}\n\nQuestion: {question}"
    )
    final_rag_chain = (
        rag_prompt
        | llm
        | StrOutputParser()
    )
    
    context_string = "\n\n".join([d.page_content for d in combined_docs])
    final_answer = final_rag_chain.invoke({"context": context_string, "question": query})

    # --- 5. Apply Guardrails ---
    validated = validate_output(final_answer, guardrail_level)
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    return {"answer": validated["answer"]}


# This helper function is correct and necessary for the step-back logic.
def get_unique_union(documents: list[list]):
    """Unique union of retrieved docs."""
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]