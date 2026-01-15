"""
Unified RAG Pipeline Service.

This module provides the core logic for the RAG chatbot, integrating various
retrieval strategies (MultiQuery, RAG Fusion, StepBack) and generation capabilities.
"""
# services/unified_rag_pipeline.py

from typing import List
from operator import itemgetter
from collections import defaultdict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_models import ChatOpenAI
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS, Chroma
from langchain_core.load import dumps, loads

from Services.guardrail import validate_output
from Services.reranker_service import get_reranker
from utils.llm_factory import LLMFactory
from config import CONFIG


class UnifiedRAGPipeline:
    """
    A unified pipeline for Retrieval-Augmented Generation (RAG).
    
    This class orchestrates the entire RAG process including:
    - Query optimization (MultiQuery, RAG Fusion, StepBack)
    - Document retrieval from vector stores (FAISS/Chroma)
    - Reranking of retrieved documents
    - Context construction and citation handling
    - Answer generation using LLM
    - Guardrail validation
    """
    def __init__(
        self,
        db: FAISS | Chroma,
        llm_model_name: str = None,
        temperature: float = None,
        token_size: int = None,
        guardrail_level: str = None,
        rerankerOption: str = None,
    ):
        """
        Initializes the UnifiedRAGPipeline.

        Args:
            db (FAISS | Chroma): The vector database instance.
            llm_model_name (str): Name of the LLM model to use.
            temperature (float): Sampling temperature for the LLM.
            token_size (int): Max tokens for response.
            guardrail_level (str): Guardrail configuration level.
            rerankerOption (str): Reranker strategy to use.
        """
        self.db = db
        self.llm_model_name = llm_model_name or CONFIG["default_llm_model"]
        self.temperature = temperature if temperature is not None else CONFIG["default_temperature"]
        self.token_size = token_size if token_size is not None else CONFIG["default_token_size"]
        self.guardrail_level = guardrail_level or CONFIG["default_guardrail_option"]
        self.rerankerOption = rerankerOption or CONFIG["default_reranker_option"]

        if not self.llm_model_name:
            raise ValueError("LLM model name must be provided")

        # Initialize LLM via factory
        llm_factory = LLMFactory(
            model_name=self.llm_model_name,
            temperature=self.temperature,
            token_size=self.token_size
        )
        self.llm = llm_factory.get_llm()

    # ------------------ MAIN ENTRY ------------------ #
    # ------------------ MAIN ENTRY ------------------ #
    def run(
        self,
        query: str,
        include_sources: bool = True,
        mode: str = "multiquery",  # Options: multiquery | ragfusion | stepback | none
        top_k: int = None,
        rrf_k: int = None,
    ):
        """
        Executes the RAG pipeline for a given query.

        Args:
            query (str): The user's question.
            include_sources (bool): Whether to include source citations in the output.
            mode (str): Retrieval mode ('multiquery', 'ragfusion', 'stepback', 'none').
            top_k (int, optional): Number of documents to retrieve.
            rrf_k (int, optional): RRF constant for RAG Fusion.

        Returns:
            dict: The result containing the answer, sources, and other metadata.
        """
        # Retrieve documents based on mode
        if mode == "stepback":
            docs = self._stepback_retrieval(query)
        elif mode == "ragfusion":
            docs = self._ragfusion_retrieval(query, top_k=top_k, rrf_k=rrf_k)
        elif mode == "none":
            docs = self._none_query_retrieval(query)
        else:  # default multiquery
            docs = self._multiquery_retrieval(query)

        # Apply reranker if enabled
        docs = self._apply_reranker(query, docs)

        # Format documents for context and citation
        context_string, citation_map, document_pages_list, source_links = self._format_docs_for_citations(
            docs, include_sources
        )

        # ------------------ RAG Prompt ------------------ #
        rag_template = (
            "Answer the following question based on this context.\n\n{context}\n\nQuestion: {question}. Don't include chunk references in your answer. Strictly remove the bracketed chunk citations and chunk word and chunk no."
        )

        prompt = ChatPromptTemplate.from_template(rag_template)
        final_rag_chain = (
            {"context": lambda x: context_string, "question": itemgetter("question")}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        final_answer = final_rag_chain.invoke({"question": query})

        # Apply guardrails
        validated = validate_output(final_answer, self.guardrail_level)
        if "⚠️ Response blocked" in validated["answer"]:
            return validated

        # Prepare final response based on include_sources
        if include_sources:
            result = {
                "answer": validated["answer"],
                "sources": source_links,
                "document_pages_dict": document_pages_list,
                "citation_map": citation_map,
                "chunks_used": docs,
            }
        else:
            result = {
                "answer": validated["answer"],
                "sources": [],
                "document_pages_dict": [],
                "citation_map": {},
                "chunks_used": docs,
            }

        return result

    # # ------------------ PRIVATE HELPERS ------------------ #
    # def _none_query_retrieval(self, query: str):
    #     base_retriever = self.db.as_retriever(search_kwargs={"k": CONFIG.get("default_none_query_top_k", 10)})
    #     retriever_chain = (
    #         ContextualCompressionRetriever(base_compressor=get_reranker(self.rerankerOption), base_retriever=base_retriever)
    #         if self.rerankerOption != "none" else base_retriever
    #     )
    #     docs = retriever_chain.invoke(query)
    #     return docs

    # ------------------ PRIVATE HELPERS ------------------ #
    def _none_query_retrieval(self, query: str):
        # Base retriever from vector database
        base_retriever = self.db.as_retriever(
            search_kwargs={"k": CONFIG.get("default_none_query_top_k", 10)}
        )

        # If reranker option is disabled, use direct retriever
        if self.rerankerOption == "none":
            return base_retriever.invoke(query)

        # Otherwise wrap retriever in a compression pipeline
        compressor = ContextualCompressionRetriever(
            transformers=[get_reranker(self.rerankerOption)]
        )

        # Pipe compressor → retriever using LCEL syntax
        retriever_chain = compressor | base_retriever

        docs = retriever_chain.invoke(query)
        return docs

    def _multiquery_retrieval(self, query: str):
        template = """You are an AI assistant. Generate five different versions of the given user question to retrieve relevant documents.
        Provide these alternative questions separated by newlines.
        Original question: {question}"""
        prompt_perspectives = ChatPromptTemplate.from_template(template)
        generate_queries = prompt_perspectives | self.llm | StrOutputParser() | (lambda x: x.split("\n"))
        candidate_queries = generate_queries.invoke({"question": query})

        all_docs = []
        retriever = self.db.as_retriever(search_kwargs={"k": CONFIG.get("default_multiquery_top_k", 5)})
        for cq in candidate_queries:
            try:
                docs = retriever.get_relevant_documents(cq)
                all_docs.append(docs)
            except Exception as e:
                print(f"Retriever failed for query: {cq}, error: {e}")
        return self._get_unique_union(all_docs)

    def _ragfusion_retrieval(self, query: str, top_k: int = None, rrf_k: int = None):
        fusion_template = """Generate five diverse rephrasings of the following user query. Separate each by a newline.
        Original question: {question}"""
        fusion_prompt = ChatPromptTemplate.from_template(fusion_template)
        generate_queries = fusion_prompt | self.llm | StrOutputParser() | (lambda x: x.split("\n"))
        candidate_queries = generate_queries.invoke({"question": query})

        retriever = self.db.as_retriever(search_kwargs={"k": top_k or CONFIG.get("default_ragfusion_top_k", 5)})
        all_retrieved = []
        for cq in candidate_queries:
            try:
                docs = retriever.get_relevant_documents(cq)
                all_retrieved.append(docs)
            except Exception as e:
                print(f"Retriever failed for query: {cq}, error: {e}")

        return self._reciprocal_rank_fusion(all_retrieved, k=rrf_k or CONFIG.get("default_ragfusion_rrf_k", 60))

    def _stepback_retrieval(self, query: str):
        stepback_template = """You are an AI assistant. Reformulate the following user question into
        a broader 'step-back' version that captures general background knowledge needed to answer it.

        Question: {question}

        Provide only the step-back reformulated question as output.
        """
        stepback_prompt = ChatPromptTemplate.from_template(stepback_template)
        generate_stepback_query = stepback_prompt | self.llm | StrOutputParser()
        stepback_query = generate_stepback_query.invoke({"question": query})

        retriever = self.db.as_retriever(search_kwargs={"k": CONFIG.get("default_stepback_top_k", 3)})
        docs_main = retriever.get_relevant_documents(query)
        docs_stepback = retriever.get_relevant_documents(stepback_query)
        combined_docs = self._get_unique_union([docs_main, docs_stepback])
        return combined_docs

    def _apply_reranker(self, query: str, docs: list):
        if self.rerankerOption != "none":
            reranker = get_reranker(self.rerankerOption)
            if reranker:
                doc_texts = [doc.page_content for doc in docs]
                ranked = reranker.rerank(query, doc_texts, top_k=CONFIG["default_reranker_top_k"])
                reranked_docs = []
                for ranked_doc, _ in ranked:
                    for original_doc in docs:
                        if original_doc.page_content == ranked_doc:
                            reranked_docs.append(original_doc)
                            break
                docs = reranked_docs
        return docs

    # ------------------ UTILITY HELPERS ------------------ #
    @staticmethod
    def _get_unique_union(documents: list[list]):
        flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
        unique_docs = list(set(flattened_docs))
        return [loads(doc) for doc in unique_docs]

    @staticmethod
    def _reciprocal_rank_fusion(all_docs: list[list], k: int = 60):
        scores = defaultdict(float)
        for docs in all_docs:
            for rank, doc in enumerate(docs):
                doc_id = dumps(doc)
                scores[doc_id] += 1 / (rank + k)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [loads(doc_id) for doc_id, _ in ranked]

    @staticmethod
    def _format_docs_for_citations(docs: List[Document], include_sources: bool = True):
        context_string = ""
        citation_map = {}
        document_pages_list = []
        source_links = []

        for i, doc in enumerate(docs):
            citation_id = i + 1
            source = doc.metadata.get("source", "No source found")
            page = doc.metadata.get("page_number", "N/A")
            context_string += f"[Chunk {citation_id}] Source: {source}, Page: {page}\nContent: {doc.page_content}\n\n"
            citation_map[str(citation_id)] = doc.metadata

        if include_sources:
            document_pages = defaultdict(set)
            for meta in citation_map.values():
                src = meta.get("source")
                page_num = meta.get("page_number")
                if src and page_num is not None:
                    document_pages[src].add(page_num)
            for src, pages in document_pages.items():
                document_pages_list.append({"source": src, "pages": sorted(list(pages))})
                source_links.append(src)

        return context_string, citation_map, document_pages_list, source_links
