from langchain.vectorstores import FAISS, Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.llms import HuggingFaceHub
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain.load import dumps, loads
from operator import itemgetter
from langchain_community.chat_models import ChatOpenAI
from guardrails import Guard
from guardrails.hub import ToxicLanguage
from Services.guardrail import validate_output  # ✅ Guardrail utility
from Services.reranker_service import get_reranker  # ✅ Import re-ranker factory


def get_stepback_retriever_with_sources(
    query: str,
    db: FAISS | Chroma,
    llm_model_name: str,
    temperature: float,
    token_size: float = 256,
    guardrail_level: str = "none",
    rerankerOption: str = "none",  # ✅ new param
):
    """Step-Back RAG pipeline with guardrails, source tracking & optional re-ranking."""

    # 🔑 Groq API setup
    GROQ_API_KEY = "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"

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    # ✅ LLM setup
    llm = ChatOpenAI(
        openai_api_base="https://api.groq.com/openai/v1",
        openai_api_key=GROQ_API_KEY,
        model=llm_model_name,
        temperature=temperature,
        max_tokens=token_size,
    )

    # ✅ Step-back prompt
    stepback_template = """You are an AI assistant. Reformulate the following user question into
    a broader 'step-back' version that captures general background knowledge needed to answer it.

    Question: {question}

    Provide only the step-back reformulated question as output.
    """
    stepback_prompt = ChatPromptTemplate.from_template(stepback_template)

    generate_stepback_query = (
        stepback_prompt
        | llm
        | StrOutputParser()
    )

    # Generate step-back query
    stepback_query = generate_stepback_query.invoke({"question": query})
    print("Step-Back Reformulated Query:", stepback_query)

    # ✅ Setup retriever
    retriever = db.as_retriever(search_kwargs={"k": 3})

    docs_main = retriever.get_relevant_documents(query)
    docs_stepback = retriever.get_relevant_documents(stepback_query)

    # ✅ Merge unique docs
    combined_docs = get_unique_union([docs_main, docs_stepback])
    print("Retrieved Documents (combined):", len(combined_docs))

    # ✅ Apply re-ranker if enabled
    if rerankerOption != "none":
        reranker = get_reranker(rerankerOption)
        if reranker:
            doc_texts = [doc.page_content for doc in combined_docs]
            ranked = reranker.rerank(query, doc_texts, top_k=5)
            # Replace docs with reranked ones while preserving metadata
            reranked_docs = []
            for ranked_doc, _ in ranked:
                for original_doc in combined_docs:
                    if original_doc.page_content == ranked_doc:
                        reranked_docs.append(original_doc)
                        break
            combined_docs = reranked_docs
            print(f"Applied Re-ranker: {rerankerOption}, Final Docs: {len(combined_docs)}")

    # ✅ Extract unique sources
    source_links = list({doc.metadata.get("source", "No source found") for doc in combined_docs})
    print("Sources Used:")
    for src in source_links:
        print(" -", src)

    # ✅ Guardrails setup
    if guardrail_level == "none":
        guard = None
    elif guardrail_level == "basic":
        guard = Guard().use(ToxicLanguage(threshold=0.9))  # lenient
    elif guardrail_level == "strict":
        guard = Guard().use(ToxicLanguage(threshold=0.5))  # strict
    elif guardrail_level == "custom":
        guard = Guard().use(ToxicLanguage(threshold=0.7, validation_method="sentence"))
    else:
        guard = None

    # ✅ RAG template
    rag_template = """Answer the following question using the provided context.
    At the end of your answer, include: Sources: <link1>, <link2>

    Context:
    {context}

    Question: {question}
    """
    rag_prompt = ChatPromptTemplate.from_template(rag_template)

    rag_chain = (
        {
            "context": lambda x: "\n\n".join([d.page_content for d in combined_docs]),
            "question": itemgetter("question"),
        }
        | rag_prompt
        | llm
        | StrOutputParser()
    )

    # Final answer
    final_answer = rag_chain.invoke({"question": query})

    # ✅ Apply guardrails
    validated = validate_output(final_answer, guardrail_level)

    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    return {
        "answer": validated["answer"],
        "sources": source_links
    }


# ----------- HELPER: UNIQUE DOCS ----------- #
def get_unique_union(documents: list[list]):
    """Unique union of retrieved docs."""
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]
