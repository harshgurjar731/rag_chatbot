from Services.reranker_service import get_reranker
from typing import List
from langchain_core.documents import Document
from ingestion_pipleline.Config.Config import INGESTION_CONFIG


def apply_reranker(reranker_type: str, model_name: str, query: str, docs: List[Document], top_k: int):
    reranker = get_reranker(reranker_type=reranker_type, model_name=model_name)
    if reranker:
        doc_texts = [doc.page_content for doc in docs]
        ranked = reranker.rerank(query, doc_texts, top_k=top_k)
        reranked_docs = []
        for ranked_doc, score in ranked:
            for original_doc in docs:
                if original_doc.page_content == ranked_doc:
                    original_doc.metadata["relevance_score"] = float(score)
                    reranked_docs.append(original_doc)
                    break
        docs = reranked_docs
    print("Reranked docs:", docs)
    return docs

def get_reranker_model(reranker_type: str, model_name: str):
    reranker = get_reranker(reranker_type=reranker_type, model_name=model_name)
    return reranker