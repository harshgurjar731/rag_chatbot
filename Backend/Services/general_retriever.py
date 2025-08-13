from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_models import ChatOpenAI


def get_llm_answer(query: str, llm_model_name: str, temperature: float):
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
        max_tokens=512
    )

    # Simple prompt for direct answering
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

    final_answer = chatbot_chain.invoke({"question": query})

    return {
        "answer": final_answer,
        "sources": []  # No sources since no RAG
    }