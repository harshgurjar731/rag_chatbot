"""
Service for re-ranking retrieved documents.

This module provides implementations for Cross-Encoder, Bi-Encoder, and LLM-based
re-rankers to improve search result relevance.
"""
from typing import List, Tuple
from sentence_transformers import CrossEncoder, SentenceTransformer, util
from langchain_community.chat_models import ChatOpenAI
import torch
import json

from config import CONFIG


# -----------------------------
# Cross-encoder Re-ranker
# -----------------------------
class CrossEncoderReranker:
    """
    Reranker using a Cross-Encoder model.
    """
    def __init__(self, model_name: str = CONFIG["cross_encoder_model"]):
        """
        Initializes the CrossEncoderReranker.

        Args:
            model_name (str): Name of the Cross-Encoder model.
        """
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, docs: List[str], top_k: int = CONFIG["default_reranker_top_k"]) -> List[Tuple[str, float]]:
        """
        Reranks documents based on the query using the Cross-Encoder model.

        Args:
            query (str): The search query.
            docs (List[str]): List of document strings to rerank.
            top_k (int): Number of top results to return.

        Returns:
            List[Tuple[str, float]]: List of (document, score) tuples.
        """
        pairs = [[query, doc] for doc in docs]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


# -----------------------------
# Bi-encoder Re-ranker
# -----------------------------
class BiEncoderReranker:
    """
    Reranker using a Bi-Encoder model.
    """
    def __init__(self, model_name: str = CONFIG["bi_encoder_model"]):
        """
        Initializes the BiEncoderReranker.

        Args:
            model_name (str): Name of the Bi-Encoder model.
        """
        self.model = SentenceTransformer(model_name)

    def rerank(self, query: str, docs: List[str], top_k: int = CONFIG["default_reranker_top_k"]) -> List[Tuple[str, float]]:
        """
        Reranks documents based on the query using the Bi-Encoder model (Cosine Similarity).

        Args:
            query (str): The search query.
            docs (List[str]): List of document strings to rerank.
            top_k (int): Number of top results to return.

        Returns:
            List[Tuple[str, float]]: List of (document, score) tuples.
        """
        query_emb = self.model.encode(query, convert_to_tensor=True)
        doc_embs = self.model.encode(docs, convert_to_tensor=True)
        scores = util.pytorch_cos_sim(query_emb, doc_embs)[0]
        ranked = sorted(zip(docs, scores.cpu().tolist()), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


# -----------------------------
# LLM-based Re-ranker (Groq API)
# -----------------------------
class LLMReranker:
    def __init__(
        self,
        model_name: str = CONFIG["llm_reranker_model"],
        api_key: str = CONFIG["groq_api_key"],
    ):
        """
        LLM-based reranker that uses Groq's hosted models via OpenAI-compatible API.
        """
        self.api_key = api_key
        self.model_name = model_name

        # ✅ Use Groq's OpenAI-compatible endpoint
        self.llm = ChatOpenAI(
            openai_api_base=CONFIG["groq_api_base"],
            openai_api_key=self.api_key,
            model=self.model_name,
            temperature=0.0,  # ranking should be deterministic
            max_tokens=CONFIG["llm_reranker_max_tokens"],
        )

    def rerank(self, query: str, docs: List[str], top_k: int = CONFIG["default_reranker_top_k"]) -> List[Tuple[str, float]]:
        """
        Rerank documents using an LLM by asking it to score relevance.
        Returns top_k documents with scores.
        """
        prompt = f"""
        You are a helpful assistant. Rank the following documents by how relevant they are to the query.
        Query: "{query}"

        Documents:
        {chr(10).join([f"{i+1}. {doc}" for i, doc in enumerate(docs)])}

        Return the ranking as a JSON list of objects with "doc" and "score" (1.0 = highly relevant).
        """

        try:
            response = self.llm.invoke(prompt)  # ✅ LangChain-style call
            ranked = json.loads(response.content)

            results = [(item["doc"], float(item.get("score", 0.5))) for item in ranked]
            return results[:top_k]
        except Exception as e:
            print("LLMReranker failed:", e)
            return [(doc, 0.5) for doc in docs[:top_k]]


# -----------------------------
# Factory Function
# -----------------------------
def get_reranker(reranker_type: str, model_name: str = ""):
    """
    Factory to load the desired re-ranker.
    reranker_type: "cross-encoder" | "bi-encoder" | "llm-reranker"
    """
    if reranker_type == "cross-encoder":
        if (model_name != ""): 
            return CrossEncoderReranker(model_name=model_name)
        return CrossEncoderReranker()
    elif reranker_type == "bi-encoder":
        if (model_name != ""): 
            return BiEncoderReranker(model_name=model_name)
        return BiEncoderReranker()
    elif reranker_type == "llm-reranker":
        if (model_name != ""): 
            return LLMReranker(model_name=model_name)
        return LLMReranker()
    else:
        return None
