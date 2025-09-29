# services/step_back_retriever_without_source.py

from operator import itemgetter
from langchain.vectorstores import FAISS, Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain.load import dumps, loads
from langchain_community.chat_models import ChatOpenAI
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFaceHub
from guardrails import Guard
from guardrails.hub import ToxicLanguage

from config import CONFIG
from Services.guardrail import validate_output   # ✅ Guardrail utility
from Services.reranker_service import get_reranker   # ✅ Re-ranker factory


def get_stepback_retriever_without_sources(
    query: str,
    db: FAISS | Chroma,
    llm_model_name: str = None,
    temperature: float = None,
    token_size: int = None,
    guardrail_level: str = None,
    rerankerOption: str = None,
):
    """Step-Back RAG pipeline without sources, with guardrails & optional re-ranking."""

    # ✅ Load defaults from config if not provided
    llm_model_name = llm_model_name or CONFIG["default_llm_model"]
    temperature = temperature if temperature is not None else CONFIG["default_temperature"]
    token_size = token_size or CONFIG["default_token_size"]
    guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
    rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

    # 🔑 Groq API setup (from env/config)
    GROQ_API_KEY = CONFIG["groq_api_key"]
    GROQ_API_BASE = CONFIG["groq_api_base"]

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    # ✅ Setup LLM
    llm = ChatOpenAI(
        openai_api_base=GROQ_API_BASE,
        openai_api_key=GROQ_API_KEY,
        model=llm_model_name,
        temperature=temperature,
        max_tokens=token_size,
    )

    # Step-back query prompt
    stepback_template = """You are an AI assistant. Reformulate the following user question into
    a broader 'step-back' version that captures general background knowledge needed to answer it.

    Question: {question}

    Provide only the step-back reformulated question as output.
    """
    stepback_prompt = ChatPromptTemplate.from_template(stepback_template)

    generate_stepback_query = stepback_prompt | llm | StrOutputParser()

    # Generate the step-back query
    stepback_query = generate_stepback_query.invoke({"question": query})
    print("Step-Back Reformulated Query:", stepback_query)

    # Retriever from vector store
    retriever = db.as_retriever(search_kwargs={"k": 3})

    # Retrieve docs for original and step-back queries
    docs_main = retriever.get_relevant_documents(query)
    docs_stepback = retriever.get_relevant_documents(stepback_query)

    # Merge unique docs
    combined_docs = get_unique_union([docs_main, docs_stepback])
    print("Retrieved Documents (combined):", len(combined_docs))

    # ✅ Apply re-ranker if enabled
    if rerankerOption != "none":
        reranker = get_reranker(rerankerOption)
        if reranker:
            doc_texts = [doc.page_content for doc in combined_docs]
            ranked = reranker.rerank(
                query,
                doc_texts,
                top_k=CONFIG["default_reranker_top_k"]  # ✅ driven from env
            )
            # Replace docs with reranked ones while preserving metadata
            reranked_docs = []
            for ranked_doc, _ in ranked:
                for original_doc in combined_docs:
                    if original_doc.page_content == ranked_doc:
                        reranked_docs.append(original_doc)
                        break
            combined_docs = reranked_docs
            print(f"Applied Re-ranker: {rerankerOption}, Final Docs: {len(combined_docs)}")

    # RAG prompt
    rag_template = """Answer the following question using the provided context:

    {context}

    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(rag_template)

    # RAG chain
    final_rag_chain = (
        {
            "context": lambda x: "\n\n".join([d.page_content for d in combined_docs]),
            "question": itemgetter("question"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    # Final answer
    final_answer = final_rag_chain.invoke({"question": query})

    # ✅ Apply guardrails via shared validator
    validated = validate_output(final_answer, guardrail_level)

    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    final_answer = validated["answer"]
    print("Final Step-Back RAG Output:", final_answer)

    return {"answer": final_answer}


# ----------- HELPER ----------- #
def get_unique_union(documents: list[list]):
    """Unique union of retrieved docs"""
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]
