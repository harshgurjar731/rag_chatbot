# # rag_app/backend/utils/llm_factory.py

from langchain_openai import ChatOpenAI
from langchain_openai import AzureChatOpenAI
from config import CONFIG
from langchain_openai import AzureOpenAI


class LLMFactory:
    """Factory class for creating LLM clients dynamically based on model and provider."""

    def __init__(self, model_name: str = None, temperature: float = None, token_size: int = None):
        self.model_name = model_name or CONFIG["default_llm_model"]
        self.temperature = temperature if temperature is not None else CONFIG["default_temperature"]
        self.token_size = token_size if token_size is not None else CONFIG["default_token_size"]

        # Determine platform dynamically
        self.platform = self._detect_platform()

    # ------------------------
    # Platform Detection
    # ------------------------
    def _detect_platform(self) -> str:
        """Detect whether the model belongs to Azure or Groq."""
        model_lower = self.model_name.lower()

        # Match against supported models from config
        if any(m.lower() in model_lower for m in CONFIG["azure_supported_models"]):
            return "azure"

        elif any(m.lower() in model_lower for m in CONFIG["groq_supported_models"]):
            return "groq"

        else:
            raise ValueError(f"Unrecognized model platform for model '{self.model_name}'")

    # ------------------------
    # Client Creation
    # ------------------------
    def get_llm(self):
        """Return the appropriate LLM client based on detected platform."""
        if self.platform == "groq":
            return self._create_groq_llm()
        elif self.platform == "azure":
            return self._create_azure_llm()
        else:
            raise ValueError(f"Unsupported platform: {self.platform}")

    # ------------------------
    # Groq Client
    # ------------------------
    def _create_groq_llm(self):
        groq_api_key = CONFIG.get("groq_api_key")
        groq_api_base = CONFIG.get("groq_api_base")

        if not groq_api_key:
            raise ValueError("Missing GROQ_API_KEY in config or environment")

        return ChatOpenAI(
            openai_api_base=groq_api_base,
            openai_api_key=groq_api_key,
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.token_size,
        )

    # ------------------------
    # Azure Client
    # # ------------------------
    # def _create_azure_llm(self):
    #     azure_api_key = CONFIG.get("azure_api_key", "")
    #     azure_api_base = CONFIG.get("azure_api_base", "")
    #     azure_api_version = CONFIG.get("azure_api_version", "")

    #     if not azure_api_key or not azure_api_base:
    #         raise ValueError("Azure credentials not found in config or environment")

    #     return ChatOpenAI(
    #         openai_api_type="azure",
    #         openai_api_key=azure_api_key,
    #         openai_api_base=azure_api_base,
    #         openai_api_version=azure_api_version,
    #         model=self.model_name,
    #         temperature=self.temperature,
    #         max_tokens=self.token_size,
    #     )
    
    def _create_azure_llm(self):
        azure_api_key = CONFIG.get("azure_api_key", "")
        azure_endpoint = CONFIG.get("azure_api_base", "")
        azure_api_version = CONFIG.get("azure_api_version", "")
        token_size = self.token_size

        if not azure_api_key or not azure_endpoint:
            raise ValueError("Azure credentials not found in config or environment")

        llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_deployment=self.model_name,  # or use self.model_name if dynamic
            temperature=self.temperature,
            # max_completion_tokens=token_size,

        )

    #     llm = AzureOpenAI(
    # azure_endpoint=azure_endpoint,
    # api_key=azure_api_key,
    # api_version="2025-01-01-preview",)
        return llm




# rag_app/backend/utils/llm_factory.py
# rag_app/backend/utils/llm_factory.py

# import os
# from typing import List
# from openai import AzureOpenAI
# from langchain_core.language_models.chat_models import BaseChatModel
# from langchain.schema import AIMessage, HumanMessage, ChatMessage
# from config import CONFIG


# # ==========================================================
# # Custom LangChain Wrapper for AzureOpenAI Chat Completions
# # ==========================================================
# from langchain.schema import ChatResult, ChatGeneration

# class AzureOpenAIChatWrapper(BaseChatModel):
#     model_config = {
#         "arbitrary_types_allowed": True
#     }

#     def __init__(self, client, model, temperature, max_tokens):
#         super().__init__(client=client, model=model, temperature=temperature, max_tokens=max_tokens)

#     # def __init__(self, client: AzureOpenAI, model: str, temperature: float, max_tokens: int):
#     #     self.client = client
#     #     self.model = model
#     #     self.temperature = temperature
#     #     self.max_tokens = max_tokens

#     # Convert LangChain messages to Azure format
#     def _convert_messages(self, messages):
#         converted = []
#         for m in messages:
#             converted.append({
#                 "role": m.type if hasattr(m, "type") else m.role,
#                 "content": [{"type": "text", "text": m.content}]
#             })
#         return converted

#     # REQUIRED: implement _generate
#     def _generate(self, messages, **kwargs) -> ChatResult:
#         azure_messages = self._convert_messages(messages)

#         completion = self.client.chat.completions.create(
#             model=self.model,
#             messages=azure_messages,
#             temperature=self.temperature,
#             max_tokens=self.max_tokens,
#         )

#         text = completion.choices[0].message["content"]

#         # Wrap in LangChain ChatGeneration + ChatResult
#         generation = ChatGeneration(message=AIMessage(content=text))
#         return ChatResult(generations=[generation])

#     # OPTIONAL: implement invoke() for convenience
#     def invoke(self, messages, **kwargs):
#         result = self._generate(messages)
#         return result.generations[0].message.content

#     @property
#     def _llm_type(self):
#         return "azure-openai-chat-wrapper"
# # ==========================================================
# #                     LLM Factory
# # ==========================================================
# class LLMFactory:

#     def __init__(self, model_name=None, temperature=None, token_size=None):
#         self.model_name = model_name or CONFIG["default_llm_model"]
#         self.temperature = temperature if temperature is not None else CONFIG["default_temperature"]
#         self.token_size = token_size if token_size is not None else CONFIG["default_token_size"]
#         self.platform = self._detect_platform()

#     def _detect_platform(self):
#         name = self.model_name.lower()
#         if any(m.lower() in name for m in CONFIG["azure_supported_models"]):
#             return "azure"
#         if any(m.lower() in name for m in CONFIG["groq_supported_models"]):
#             return "groq"
#         raise ValueError(f"Unknown model platform for: {self.model_name}")

#     def get_llm(self):
#         if self.platform == "azure":
#             return self._create_azure_llm()
#         if self.platform == "groq":
#             return self._create_groq_llm()
#         raise ValueError(f"Unsupported platform: {self.platform}")

#     # ======================================================
#     # Azure LLM — using your provided AzureOpenAI code
#     # ======================================================
#     def _create_azure_llm(self):
#         azure_endpoint = CONFIG.get("azure_api_base")
#         api_key = CONFIG.get("azure_api_key")
#         api_version = CONFIG.get("azure_api_version", "2025-01-01-preview")

#         client = AzureOpenAI(
#             azure_endpoint=azure_endpoint,
#             api_key=api_key,
#             api_version=api_version,
#         )

#         return AzureOpenAIChatWrapper(
#             client=client,
#             model=self.model_name,
#             temperature=self.temperature,
#             max_tokens=self.token_size,
#         )

#     # ======================================================
#     # Groq LLM
#     # ======================================================
#     def _create_groq_llm(self):
#         from langchain_openai import ChatOpenAI

#         return ChatOpenAI(
#             openai_api_key=CONFIG.get("groq_api_key"),
#             openai_api_base=CONFIG.get("groq_api_base"),
#             model=self.model_name,
#             temperature=self.temperature,
#             max_tokens=self.token_size,
#         )
