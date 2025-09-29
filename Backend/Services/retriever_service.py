# services/retriever_service.py

from fastapi import HTTPException
from langchain.vectorstores import FAISS, Chroma
from langchain.embeddings import HuggingFaceEmbeddings

from config import CONFIG
from Services.multi_query_retriever import get_multiquery_retriever
from Services.multi_query_retriever_without_sources import get_multiquery_retriever_without_sources
from Services.general_retriever import get_llm_answer
from Services.step_back_retriever_with_source import get_stepback_retriever_with_sources
from Services.step_back_retriever_without_source import get_stepback_retriever_without_sources
from Services.rag_fusion_retriever_with_source import get_ragfusion_retriever_with_sources
from Services.rag_fusion_retriever_without_sources import get_ragfusion_retriever_without_sources
import uuid



# In your `multi_query_retriever_without_sources.py`
from langchain.chains import RetrievalQA
# ... (your existing imports)

class MultiQueryRetrieverService:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.llm = OpenAI()  # Assuming this is configured
        self.retriever = self.vector_store.as_retriever()
        
        # This is where the chain is built
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.retriever,
        )

    def process_query(self, query):
        # When this method is called, Phoenix will automatically log the trace
        response = self.qa_chain.invoke({"query": query})
        return response



















# -----------------------------
# Load embeddings
# -----------------------------
def load_embeddings(file_id: int, vector_db: str = None, model_name: str = None):
    """Load FAISS/Chroma embeddings for a given file ID."""

    vector_db = vector_db or CONFIG["default_vector_db"]
    model_name = model_name or CONFIG["default_embedding_model"]

    embedding = HuggingFaceEmbeddings(model_name=model_name)

    if vector_db == "faiss":
        db = FAISS.load_local(
            f"vectorstores/faiss_file_{file_id}",
            embedding,
            allow_dangerous_deserialization=True,
        )
        return db

    elif vector_db == "chroma":
        db = Chroma(
            persist_directory=f"vectorstores/chroma_file_{file_id}",
            embedding_function=embedding,
        )
        return db

    else:
        raise HTTPException(status_code=400, detail="Unsupported vector DB")


# -----------------------------
# Document Retrieval
# -----------------------------
def retrieve_documents(
    query: str,
    query_optimizer: str = None,
    embedding_model_name: str = None,
    llm_model_name: str = None,
    vector_db: str = None,
    file_id: list = None,
    temperature: float = None,
    token_size: int = None,
    sources: bool = True,
    guardrailOption: str = None,
    rerankerOption: str = None,
):
    """Main entry for retrieving documents with selected retriever pipeline."""

    # ✅ Load defaults from config if not provided
    query_optimizer = query_optimizer or CONFIG["default_query_optimizer"]
    embedding_model_name = embedding_model_name or CONFIG["default_embedding_model"]
    llm_model_name = llm_model_name or CONFIG["default_llm_model"]
    vector_db = vector_db or CONFIG["default_vector_db"]
    temperature = temperature if temperature is not None else CONFIG["default_temperature"]
    token_size = token_size or CONFIG["default_token_size"]
    guardrailOption = guardrailOption or CONFIG["default_guardrail_option"]
    rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

    file_id = file_id or [0]
    embedding = HuggingFaceEmbeddings(model_name=embedding_model_name)

    # -----------------------------
    # Case 1: No files -> plain LLM answer
    # -----------------------------
    if file_id == [0]:
        return get_llm_answer(
            query, llm_model_name, temperature, token_size, sources, guardrailOption
        )

    # -----------------------------
    # Case 2: Merge embeddings from all files
    # -----------------------------
    db = None
    for f_id in file_id:
        new_db = load_embeddings(f_id, vector_db, embedding_model_name)
        if db is None:
            db = new_db
        else:
            db.merge_from(new_db)

    # -----------------------------
    # Case 3: Choose retriever pipeline
    # -----------------------------
    if query_optimizer == "Multi Query":
        if sources:
            result = get_multiquery_retriever(
                query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
            )
        else:
            result = get_multiquery_retriever_without_sources(
                query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
            )

    elif query_optimizer == "Step Back":
        if sources:
            result = get_stepback_retriever_with_sources(
                query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
            )
        else:
            result = get_stepback_retriever_without_sources(
                query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
            )

    elif query_optimizer == "Rag Fusion":
        if sources:
            result = get_ragfusion_retriever_with_sources(
                query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
            )
        else:
            result = get_ragfusion_retriever_without_sources(
                query, db, llm_model_name, temperature, token_size, guardrailOption, rerankerOption
            )

    else:
        retriever = db.as_retriever()
        result = retriever.get_relevant_documents(query)
    result["traceId"]=str(uuid.uuid4())
    # result.append("traceId",str(uuid.uuid4()))
    return result
