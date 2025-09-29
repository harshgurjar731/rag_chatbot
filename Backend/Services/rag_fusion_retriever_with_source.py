from langchain.vectorstores import FAISS, Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain.load import dumps, loads
from operator import itemgetter
from langchain_community.chat_models import ChatOpenAI

from Services.guardrail import validate_output
from Services.reranker_service import get_reranker
from config import CONFIG
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFaceHub

def get_ragfusion_retriever_with_sources(
    query: str,
    db: FAISS | Chroma,
    llm_model_name: str = CONFIG["default_llm_model"],
    temperature: float = CONFIG["default_temperature"],
    token_size: float = CONFIG["default_token_size"],
    guardrail_level: str = CONFIG["default_guardrail_option"],
    rerankerOption: str = CONFIG["default_reranker_option"],
):
    """RAG Fusion Retrieval chain using Reciprocal Rank Fusion (with optional re-ranking)."""

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    # ✅ Setup LLM from env/config
    llm = ChatOpenAI(
        openai_api_base=CONFIG["groq_api_base"],
        openai_api_key=CONFIG["groq_api_key"],
        model=llm_model_name,
        temperature=temperature,
        max_tokens=token_size,
    )

    # Generate multiple queries
    fusion_template = """Generate five diverse rephrasings of the following user query. 
    Separate each by a newline.
    Original question: {question}"""
    fusion_prompt = ChatPromptTemplate.from_template(fusion_template)

    generate_queries = (
        fusion_prompt | llm | StrOutputParser() | (lambda x: x.split("\n"))
    )

    candidate_queries = generate_queries.invoke({"question": query})
    retriever = db.as_retriever(
        search_kwargs={"k": CONFIG["default_ragfusion_top_k"]}
    )

    all_retrieved = []
    for cq in candidate_queries:
        try:
            docs = retriever.get_relevant_documents(cq)
            all_retrieved.append(docs)
        except Exception as e:
            print(f"Retriever failed for query: {cq}, error: {e}")

    # ✅ Reciprocal Rank Fusion (env-driven k)
    fused_docs = reciprocal_rank_fusion(all_retrieved, k=CONFIG["default_ragfusion_rrf_k"])
    print("Fused Docs Retrieved:", len(fused_docs))

    # ✅ Apply re-ranker (if selected)
    if rerankerOption != "none":
        reranker = get_reranker(rerankerOption)
        if reranker:
            doc_texts = [doc.page_content for doc in fused_docs]
            ranked = reranker.rerank(query, doc_texts, top_k=5)
            reranked_docs = []
            for ranked_doc, _ in ranked:
                for original_doc in fused_docs:
                    if original_doc.page_content == ranked_doc:
                        reranked_docs.append(original_doc)
                        break
            fused_docs = reranked_docs
            print(f"Applied Re-ranker: {rerankerOption}, Final Docs: {len(fused_docs)}")

    # RAG prompt
    rag_template = """Answer the following question using the provided context:

    {context}

    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(rag_template)

    final_rag_chain = (
        {
            "context": lambda x: "\n\n".join([d.page_content for d in fused_docs]),
            "question": itemgetter("question"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    final_answer = final_rag_chain.invoke({"question": query})

    # ✅ Apply guardrails
    validated = validate_output(final_answer, guardrail_level)

    return {
        "answer": validated["answer"],
        "sources": [doc.metadata for doc in fused_docs],
    }


# ----------- HELPER: Reciprocal Rank Fusion ----------- #
def reciprocal_rank_fusion(all_docs: list[list], k: int = CONFIG["default_ragfusion_rrf_k"]):
    """Reciprocal Rank Fusion (RRF) to merge ranked document lists."""
    from collections import defaultdict

    scores = defaultdict(float)
    for docs in all_docs:
        for rank, doc in enumerate(docs):
            doc_id = dumps(doc)
            scores[doc_id] += 1 / (rank + k)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [loads(doc_id) for doc_id, _ in ranked]
