# from langchain.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from langchain_community.chat_models import ChatOpenAI


# def get_llm_answer(query: str, llm_model_name: str, temperature: float,token_size: float = 256):
#     """General purpose chatbot without using any file/vector store data."""

#     GROQ_API_KEY = "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"

#     if not llm_model_name:
#         raise ValueError("LLM model name must be provided")

#     # Initialize LLM
#     llm = ChatOpenAI(
#         openai_api_base="https://api.groq.com/openai/v1",
#         openai_api_key=GROQ_API_KEY,
#         model=llm_model_name,
#         temperature=temperature,
#         max_tokens=token_size
#     )

#     # Simple prompt for direct answering
#     chatbot_template = """
#     You are a helpful and friendly AI assistant.
#     Answer the following question clearly and concisely.

#     Question: {question}
#     """
#     prompt = ChatPromptTemplate.from_template(chatbot_template)

#     # Chain: prompt → LLM → output parser
#     chatbot_chain = (
#         {"question": lambda x: x["question"]}
#         | prompt
#         | llm
#         | StrOutputParser()
#     )

#     final_answer = chatbot_chain.invoke({"question": query})

#     return {
#         "answer": final_answer,
#         "sources": []  # No sources since no RAG
#     }


from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_models import ChatOpenAI
from guardrails import Guard
from guardrails.hub import ToxicLanguage
# import os

# # Disable OpenTelemetry + Guardrails telemetry
# os.environ["OTEL_SDK_DISABLED"] = "true"
# os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "none"
# os.environ["GUARDRAILS_DISABLE_TELEMETRY"] = "1"

def get_llm_answer(
    query: str,
    llm_model_name: str,
    temperature: float,
    token_size: int = 256,
    include_sources: bool = False,
    guardrail_level: str="none"
):
    """General purpose chatbot without using any file/vector store data."""

    GROQ_API_KEY = "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"

    if not llm_model_name:
        raise ValueError("LLM model name must be provided")

    # Initialize LLM
    llm = ChatOpenAI(
        openai_api_base="https://api.groq.com/openai/v1",
        openai_api_key=GROQ_API_KEY,
        model=llm_model_name,
        temperature=temperature,
        max_tokens=token_size
    )

    # Prompt template (different depending on sources requirement)
    if include_sources:
        chatbot_template = """
        You are a helpful and friendly AI assistant.
        Answer the following question clearly and concisely.
        After the answer, provide a section called "Sources" listing any references,
        even if they are hypothetical or inferred.

        Question: {question}
        """
    else:
        chatbot_template = """
        You are a helpful and friendly AI assistant.
        Answer the following question clearly and concisely.

        Question: {question}
        """
    
    # ✅ Setup Guardrails depending on level
    if guardrail_level == "none":
        guard = None  # no validation
    elif guardrail_level == "basic":
        guard = Guard().use(ToxicLanguage(threshold=0.9))  # lenient
    elif guardrail_level == "strict":
        guard = Guard().use(ToxicLanguage(threshold=0.5))  # strict
    elif guardrail_level == "custom":
        guard = Guard().use(
            ToxicLanguage(threshold=0.7, validation_method="sentence")
        )
    else:
        guard = None

    


    prompt = ChatPromptTemplate.from_template(chatbot_template)

    # Chain: prompt → LLM → output parser
    chatbot_chain = (
        {"question": lambda x: x["question"]}
        | prompt
        | llm
        | StrOutputParser()
    )

    final_answer = chatbot_chain.invoke({"question": query})

    if guard:
        try:
            validated = guard.validate(final_answer)

            # if not validated.validation_passed:
            #     return {"answer": "⚠️ Response blocked by guardrails: " + str(validated.errors)}

            final_answer = validated.validated_output.strip()
        except Exception as e:
            return {"answer": f"⚠️ Response blocked by guardrail: {str(e)}"}


    # If sources included, split answer into text + sources
    if include_sources and "Sources:" in final_answer:
        parts = final_answer.split("Sources:")
        answer_text = parts[0].strip()
        sources_text = parts[1].strip() if len(parts) > 1 else ""
        return {
            "answer": answer_text + "\n\n Sources: " +str(sources_text.split("\n") if sources_text else [])
        }

    return {
        "answer": final_answer.strip()  # Empty if not requested
    }
