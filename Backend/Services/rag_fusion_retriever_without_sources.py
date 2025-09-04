from langchain.vectorstores import FAISS, Chroma
from langchain.llms import HuggingFaceHub  
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain.load import dumps, loads
from operator import itemgetter 
from langchain_community.chat_models import ChatOpenAI  
from Services.guardrail import validate_output  


def get_ragfusion_retriever_without_sources(
    query: str, 
    db: FAISS | Chroma, 
    llm_model_name: str, 
    temperature: float, 
    token_size: float = 256, 
    guardrail_level: str = "none"
):
    """RAG Fusion Retrieval chain using Reciprocal Rank Fusion (no sources)."""

    # 🔑 Groq API key
    GROQ_API_KEY = "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"

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    # ✅ Setup LLM
    llm = ChatOpenAI(
        openai_api_base="https://api.groq.com/openai/v1",
        openai_api_key=GROQ_API_KEY,
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
        fusion_prompt
        | llm
        | StrOutputParser()
        | (lambda x: x.split("\n"))
    )

    candidate_queries = generate_queries.invoke({"question": query})
    retriever = db.as_retriever(search_kwargs={"k": 5})

    all_retrieved = []
    for cq in candidate_queries:
        try:
            docs = retriever.get_relevant_documents(cq)
            all_retrieved.append(docs)
        except Exception as e:
            print(f"Retriever failed for query: {cq}, error: {e}")

    fused_docs = reciprocal_rank_fusion(all_retrieved)

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

    return {"answer": validated["answer"]}


# ----------- HELPER: Reciprocal Rank Fusion ----------- #
def reciprocal_rank_fusion(all_docs: list[list], k: int = 60):
    """Reciprocal Rank Fusion (RRF) to merge ranked document lists."""
    from collections import defaultdict

    scores = defaultdict(float)
    for docs in all_docs:
        for rank, doc in enumerate(docs):
            doc_id = dumps(doc)
            scores[doc_id] += 1 / (rank + k)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [loads(doc_id) for doc_id, _ in ranked]
