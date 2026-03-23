from typing import Protocol, List, Optional
import os
import mimetypes
from langchain_openai import ChatOpenAI
from langchain_openai import AzureChatOpenAI
from langchain_mistralai import ChatMistralAI
# from ingestion_pipleline.Config.Config import INGESTION_CONFIG # Commenting out as likely not needed for this service and path might be tricky
from rag_pipeline.Config.rag_config import RAG_CONFIG

class LLMModelsProtocol(Protocol):
    def get_llm(self, model_name: str, temperature: float, max_tokens: int):
        ...

class MistralLLMModel(LLMModelsProtocol):
    def get_llm(self, model_name: str, temperature: float, max_tokens: int):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found in environment")
        
        return ChatMistralAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key
        )

class GroqLLMModel(LLMModelsProtocol):
    def get_llm(self, model_name: str, temperature: float, max_tokens: int):
        # Only works if you are using Groq’s OpenAI-compatible API endpoint
        groq_api_key = RAG_CONFIG["GROQ_API_KEY"]
        groq_api_base = RAG_CONFIG["GROQ_API_BASE"]

        if not groq_api_key:
            raise ValueError("Missing GROQ_API_KEY in config or environment")

        return ChatOpenAI(
            openai_api_base=groq_api_base,
            openai_api_key=groq_api_key,
            model=model_name,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )


class AzureOpenAILLMModel(LLMModelsProtocol):
    def get_llm(self, model_name: str, temperature: float, max_tokens: int):
        
        azure_api_key = RAG_CONFIG["AZURE_OPENAI_API_KEY"]
        azure_endpoint = RAG_CONFIG["AZURE_OPENAI_ENDPOINT"]
        azure_api_version = RAG_CONFIG["AZURE_OPENAI_API_VERSION"]

        if not azure_api_key or not azure_endpoint:
            raise ValueError("Azure credentials not found in config or environment")

        return AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_deployment="gpt-4o-mini",  # or use self.model_name if dynamic
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )

def create_llm_model(provider: str, model_name: str, temperature: float, max_tokens: int):
    # Normalize provider string
    p = provider.lower()
    if p == "groq":
        print("Creating Groq LLM")
        return GroqLLMModel().get_llm(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    elif p == "mistral":
        print("Creating Mistral LLM")
        return MistralLLMModel().get_llm(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    elif p == "azureopenai" or p == "azure-openai" or p == "azure": # Added 'azure' for robustness
        print("Creating Azure OpenAI LLM")
        return AzureOpenAILLMModel().get_llm(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        # Fallback or error? User code raised error. 
        # But we previously had a generic ChatOpenAI fallback.
        # Let's try to support generic OpenAI if needed, or just raise as user requested.
        # If RAG_CONFIG has something else, this might break.
        # Assuming user knows what they are doing with providers.
        raise ValueError(f"CRITICAL: Unsupported LLM Provider: '{provider}'")

class IntentDetectionService:
    def __init__(self):
        self.llm = self._initialize_llm()

    def _initialize_llm(self):
        provider = RAG_CONFIG.get("default_llm_provider", "groq")
        model_name = RAG_CONFIG.get("default_llm_model", "llama-3.3-70b-versatile")
        # Use low temperature for deterministic classification
        temperature = 0.0
        max_tokens = 256
        
        try:
            return create_llm_model(provider, model_name, temperature, max_tokens)
        except ValueError as e:
            print(f"Error initializing LLM for IntentDetection: {e}")
            # Fallback for resiliency if Groq/Azure fails or config is weird? 
            # Or just let it fail. 
            # Given previous implementation had a fallback, let's minimally try a standard ChatOpenAI if it fails?
            # User request seemed strict. Let's return None or let it raise. 
            # I will let it raise so it's visible in logs.
            raise e

    async def detect_intent(self, query: str, intents: List[dict]) -> Optional[List[dict]]:
        if not intents or len(intents) == 0:
            return None

        # Format intents for the prompt
        intents_str_list = []
        for i in intents:
             title = i.get('title', 'N/A')
             desc = i.get('description', 'N/A')
             file_path = i.get('file_path')
             
             metadata_str = "N/A"
             if file_path and os.path.exists(file_path):
                 try:
                     size_bytes = os.path.getsize(file_path)
                     # Convert to legible size
                     for unit in ['B', 'KB', 'MB', 'GB']:
                         if size_bytes < 1024:
                             size_str = f"{size_bytes:.2f} {unit}"
                             break
                         size_bytes /= 1024
                     else:
                         size_str = f"{size_bytes:.2f} TB"
                     
                     mime_type, _ = mimetypes.guess_type(file_path)
                     filename = os.path.basename(file_path)
                     metadata_str = f"Filename: {filename}, Size: {size_str}, Type: {mime_type or 'Unknown'}"
                 except Exception as e:
                     metadata_str = f"Error reading metadata: {str(e)}"
                     
             intents_str_list.append(f"- Title: {title}\n  Description: {desc}\n  Source Metadata: {metadata_str}")

        intents_str = "\n\n".join(intents_str_list)

        system_prompt = f"""You are an intelligent intent classifier and a witty assistant.
Your task is to analyze the user's query and identify if it matches one of the provided intents.

Available Intents:
{intents_str}

Instructions:
1. Compare the query (meaning and context) with the Title, Description, and Source Metadata of each intent.
2. If the query clearly matches one or more intents, return a JSON array containing an object for each matched intent with:
   - "title": The exact Title of the matched intent.
   - "witty_hook": A short, curious, or witty one-liner based on the intent description AND the source metadata (e.g. don't mention the file type or size ) to encourage the user to click the source link. using emojis is allowed.
3. If the query does not match any intent, return the string "None" (or a JSON array with [{{"title": "None"}}]).
4. Do not provide any explanation, only the JSON array."""

        human_prompt = f"Query: {query}"

        try:
            messages = [
                ("system", system_prompt),
                ("human", human_prompt)
            ]
            
            # Since we are using LangChain Chat models, we can invoke them directly
            # For async execution, use ainvoke
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()

            # Clean quotes if present
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '')
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            
            if content.lower() == "none":
                return None
            
            import json
            try:
                result = json.loads(content)
                if isinstance(result, dict) and result.get("title") == "None":
                    return None
                if isinstance(result, list):
                    if len(result) > 0 and result[0].get("title") == "None":
                        return None
                    return result
                if isinstance(result, dict):
                    return [result]
                return None
            except json.JSONDecodeError:
                # Fallback if LLM returns just the title?
                print(f"Failed to parse JSON from intent service: {content}")
                return [{"title": content, "witty_hook": "Check this out!"}]

        except Exception as e:
            print(f"Error in intent detection: {e}")
            return None
