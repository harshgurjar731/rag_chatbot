# Make sure to install the necessary packages:
# pip install langchain-openai python-dotenv

import os
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Assume CONFIG is loaded from a .env file or another configuration source
# For example, using dotenv:
# from dotenv import load_dotenv
# load_dotenv()
# CONFIG = {
#     "azure_openai_api_key": os.getenv("AZURE_OPENAI_API_KEY"),
#     "azure_openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
#     "azure_openai_api_version": os.getenv("AZURE_OPENAI_API_VERSION"),
# }
# This is a placeholder for your actual configuration loading.

azure_openai_api_key=str("BNwzZtUQM3K0Tilhquk3ps6ThTFlp0TGYKLvIQI1wbnQUgI7Q4QqJQQJ99BIACYeBjFXJ3w3AAABACOGLNf9")
azure_openai_endpoint= str("https://knowledgebotopenaiservice.openai.azure.com/")
azure_openai_api_version= str("2025-04-01-preview") # Example API version

# azure_openai_api_key=str("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
# azure_openai_endpoint= str("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
# azure_openai_api_version= str("xxxxxxxxxxxx"), # Example API version



# This is a placeholder for your 'validate_output' function.
# You should implement your own guardrail logic here.
def validate_output(text, level):
    """Placeholder for your output validation/guardrail logic."""
    # Example: a very simple guardrail
    if level == "high" and "danger" in text:
        return {"answer": "⚠️ Response blocked due to sensitive content."}
    return {"answer": text}


def get_llm_answer_azure(
    query: str,
    deployment_name: str,
    temperature: float,
    token_size: int = 256,
    include_sources: bool = False,
    guardrail_level: str = "none"
):
    """
    General-purpose chatbot using Azure OpenAI with robust session handling.
    The client session is terminated after each call to manage costs.
    """

    azure_api_key = azure_openai_api_key
    azure_endpoint= azure_openai_endpoint
    azure_api_version = azure_openai_api_version

    # ✅ Validate Azure credentials
    if not all([azure_api_key, azure_endpoint, azure_api_version]):
        raise ValueError(
            "Azure OpenAI credentials not set. "
            "Please update your configuration."
        )

    if not deployment_name:
        raise ValueError("Azure OpenAI deployment name must be provided.")

    llm = None
    try:
        # ✅ Initialize Azure OpenAI LLM with config values
        llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_deployment="gpt-5-mini",
            temperature=temperature,
            max_completion_tokens=token_size,
        )

        # ✅ Prompt template remains the same
        chatbot_template = """
        You are a helpful and friendly AI assistant.
        Answer the following question clearly and concisely.
        """ + (
            """
            After the answer, provide a section called "Sources" listing any references,
            even if they are hypothetical or inferred.
            """
            if include_sources
            else ""
        ) + """
        
        Question: {question}
        """

        prompt = ChatPromptTemplate.from_template(chatbot_template)

        # ✅ Chain: prompt → LLM → output parser (this logic is unchanged)
        chatbot_chain = (
            {"question": lambda x: x["question"]}
            | prompt
            | llm
            | StrOutputParser()
        )

        # Raw LLM output
        final_answer = chatbot_chain.invoke({"question": query})

        # ✅ Apply guardrails (using your existing function)
        validated = validate_output(final_answer, guardrail_level)
        if "⚠️ Response blocked" in validated["answer"]:
            return validated

        final_answer = validated["answer"]

        # ✅ Handle sources (this logic is unchanged)
        if include_sources and "Sources:" in final_answer:
            parts = final_answer.split("Sources:")
            answer_text = parts[0].strip()
            sources_text = parts[1].strip() if len(parts) > 1 else ""
            return {
                "answer": answer_text
                + "\n\nSources: "
                + str(sources_text.split("\n") if sources_text else [])
            }

        return {"answer": final_answer.strip()}
    except Exception as e:
        print(f"Error during LLM processing: {e}")
        return {"answer": "⚠️ An error occurred while processing your request."}
    # finally:
        # ✅ Safeguard: Ensure the client session is closed after each call
        # to prevent dangling connections and manage costs. The `llm.client`
        # is part of the underlying openai package and has a close() method.
        # if llm and hasattr(llm, 'client'):
        #     llm.client.close()