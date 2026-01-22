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

#     # ✅ Apply guardrails
#     validated = validate_output(final_answer, guardrail_level)
#     if "⚠️ Response blocked" in validated["answer"]:
#         return validated

#     final_answer = validated["answer"]

#     # ✅ Handle sources
#     if include_sources and "Sources:" in final_answer:
#         parts = final_answer.split("Sources:")
#         answer_text = parts[0].strip()
#         sources_text = parts[1].strip() if len(parts) > 1 else ""
#         return {
#             "answer": answer_text + "\n\nSources: " + str(sources_text.split("\n") if sources_text else [])
#         }

#     return {"answer": final_answer.strip()}


from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config import CONFIG
from utils.llm_factory import LLMFactory  # ✅ Import our dynamic LLMFactory


def get_llm_answer(
    query: str,
    llm_model_name: str = None,
    llm_model_provider: str = None,
    temperature: float = None,
    token_size: int = 256,
    include_sources: bool = False,
    guardrail_level: str = "none"
):
    """General purpose chatbot without using any file/vector store data."""

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    # ✅ Initialize LLM using our dynamic factory (Groq / Azure handled automatically)
    llm_factory = LLMFactory(
        model_name=llm_model_name,
        temperature=temperature,
        token_size=token_size
    )
    llm = llm_factory.get_llm()

    # ✅ Prompt template
    chatbot_template = """
    You are a helpful and friendly AI assistant.
    Answer the following question clearly and concisely.
    """ + (
        """
        After the answer, provide a section called "Sources" listing any references,
        even if they are hypothetical or inferred.
        """ if include_sources else ""
    ) + """
    
    Question: {question}
    """

    prompt = ChatPromptTemplate.from_template(chatbot_template)

    # ✅ Chain: prompt → LLM → output parser
    chatbot_chain = (
        {"question": lambda x: x["question"]}
        | prompt
        | llm
        | StrOutputParser()
    )

    # Raw LLM output
    final_answer = chatbot_chain.invoke({"question": query})

    # ✅ Apply guardrails (Removed)
    # validated = validate_output(final_answer, guardrail_level)
    # if "⚠️ Response blocked" in validated["answer"]:
    #     return validated

    # final_answer = validated["answer"]
    pass

    # ✅ Handle sources
    if include_sources and "Sources:" in final_answer:
        parts = final_answer.split("Sources:")
        answer_text = parts[0].strip()
        sources_text = parts[1].strip() if len(parts) > 1 else ""
        return {
            "answer": answer_text + "\n\nSources: " + str(sources_text.split("\n") if sources_text else [])
        }

    return {"answer": final_answer.strip()}
