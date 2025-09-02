from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_models import ChatOpenAI

# ✅ Import our guardrail utilities
from Services.guardrail import validate_output  
def get_llm_answer(
    query: str,
    llm_model_name: str,
    temperature: float,
    token_size: int = 256,
    include_sources: bool = False,
    guardrail_level: str = "none"
):
    """General purpose chatbot without using any file/vector store data."""

    # GROQ_API_KEY = "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"
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

    # Prompt template (depends on whether sources are included)
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

    prompt = ChatPromptTemplate.from_template(chatbot_template)

    # Chain: prompt → LLM → output parser
    chatbot_chain = (
        {"question": lambda x: x["question"]}
        | prompt
        | llm
        | StrOutputParser()
    )

    # Raw LLM output
    final_answer = chatbot_chain.invoke({"question": query})

    # ✅ Apply guardrails (toxicity, PII etc.)
    validated = validate_output(final_answer, guardrail_level)

    # If guard blocked, return directly
    if "⚠️ Response blocked" in validated["answer"]:
        return validated

    final_answer = validated["answer"]

    # Handle sources if included
    if include_sources and "Sources:" in final_answer:
        parts = final_answer.split("Sources:")
        answer_text = parts[0].strip()
        sources_text = parts[1].strip() if len(parts) > 1 else ""
        return {
            "answer": answer_text + "\n\nSources: " + str(sources_text.split("\n") if sources_text else [])
        }

    return {"answer": final_answer.strip()}
