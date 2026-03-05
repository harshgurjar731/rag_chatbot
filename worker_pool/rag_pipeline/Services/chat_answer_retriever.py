# from langchain.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from langchain_community.chat_models import ChatOpenAI

# from Services.guardrail import validate_output  
# from config import CONFIG


# def get_llm_answer(
#     query: str,
#     llm_model_name: str,
#     temperature: float,
#     token_size: int = 256,
#     include_sources: bool = False,
#     guardrail_level: str = "none"
# ):
#     """General purpose chatbot without using any file/vector store data."""

#     groq_api_key = CONFIG["groq_api_key"]
#     groq_api_base = CONFIG["groq_api_base"]

#     if not groq_api_key:
#         raise ValueError("Groq API key not set. Please update your .env file.")

#     if not llm_model_name:
#         raise ValueError("LLM model name must be provided")

#     # ✅ Initialize LLM with config values
#     llm = ChatOpenAI(
#         openai_api_base=groq_api_base,
#         openai_api_key=groq_api_key,
#         model=llm_model_name,
#         temperature=temperature,
#         max_tokens=token_size
#     )

#     # ✅ Prompt template
#     chatbot_template = """
#     You are a helpful and friendly AI assistant.
#     Answer the following question clearly and concisely.
#     """ + (
#         """
#         After the answer, provide a section called "Sources" listing any references,
#         even if they are hypothetical or inferred.
#         """ if include_sources else ""
#     ) + """
    
#     Question: {question}
#     """

#     prompt = ChatPromptTemplate.from_template(chatbot_template)

#     # ✅ Chain: prompt → LLM → output parser
#     chatbot_chain = (
#         {"question": lambda x: x["question"]}
#         | prompt
#         | llm
#         | StrOutputParser()
#     )

#     # Raw LLM output
#     final_answer = chatbot_chain.invoke({"question": query})

#     final_answer = chatbot_chain.invoke({"question": query})

#     # ✅ Handle sources
#     if include_sources and "Sources:" in final_answer:
#         parts = final_answer.split("Sources:")
#         answer_text = parts[0].strip()
#         sources_text = parts[1].strip() if len(parts) > 1 else ""
#         return {
#             "answer": answer_text + "\n\nSources: " + str(sources_text.split("\n") if sources_text else [])
#         }

#     return {"answer": final_answer.strip()}


"""
This module provides the service for obtaining direct LLM answers without retrieval.

It handles the creation of the LLM chain, optional output validation via guardrails,
and source attribution if requested.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from Services.guardrail import validate_output
from config import CONFIG
from utils.llm_factory import LLMFactory  # ✅ Import our dynamic LLMFactory
from rag_pipeline.LLMs.llm_model_protocol import create_llm_model
from rag_pipeline.Config.rag_prompts import RAG_PROMPTS
from rag_pipeline.utility.Utils import get_final_prompt

def get_llm_answer(
    query: str,
    llm_model_name: str = None,
    llm_model_provider: str = None,
    temperature: float = None,
    token_size: int = 256,
    include_sources: bool = False,
    guardrail_level: str = "none"
):
    """
    Get an answer from the LLM based on the query, without using an external knowledge base.

    This function configures the LLM, constructs the prompt, invokes the model,
    optionally validates the output using guardrails, and formats the response.

    Args:
        query (str): The user's question.
        llm_model_name (str): The name of the LLM model to use.
        llm_model_provider (str): The provider of the LLM model (e.g., "groq", "azureopenai").
        temperature (float): The sampling temperature.
        token_size (int, optional): The maximum number of tokens to generate. Defaults to 256.
        include_sources (bool, optional): Whether to parse and include sources in the response. Defaults to False.
        guardrail_level (str, optional): The level of guardrails to apply (e.g., "none"). Defaults to "none".

    Returns:
        dict: A dictionary containing the answer, and optionally images and citations placeholders.
              Structure: {"answer": str, "images": list, "citations": str}

    Raises:
        ValueError: If `llm_model_name` or `llm_model_provider` is missing.
    """
    if not llm_model_name or not llm_model_provider:
        raise ValueError("LLM model & provider name must be provided")

    llm = create_llm_model(
        provider=llm_model_provider,
        model_name=llm_model_name,
        temperature=temperature,
        max_tokens=token_size
    )

    prompt_template = get_final_prompt(prompt=RAG_PROMPTS["chat_template"], use_knowledge_base=False, include_sources= include_sources)
    prompt = ChatPromptTemplate.from_template(prompt_template)

    # ✅ Chain: prompt → LLM → output parser
    chatbot_chain = (
        {"question": lambda x: x["question"]}
        | prompt
        | llm
        | StrOutputParser()
    )

    # Raw LLM output
    final_answer = chatbot_chain.invoke({"question": query})

    # ✅ Apply guardrails
    validated = validate_output(final_answer, guardrail_level)
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    final_answer = validated["answer"]

    # ✅ Handle sources
    if include_sources and "Sources:" in final_answer:
        parts = final_answer.split("Sources:")
        answer_text = parts[0].strip()
        sources_text = parts[1].strip() if len(parts) > 1 else ""
        return {
            "answer": answer_text + "\n\nSources: " + str(sources_text.split("\n") if sources_text else []),
            "images": "[]",
            "citations": "[]"
        }

    return {
        "answer": final_answer.strip(),
        "images": "[]",
        "citations": "[]"
    }
