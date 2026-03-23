import sys
import os

# Add worker_pool to path
sys.path.append(os.path.join(os.getcwd(), "worker_pool"))

from rag_pipeline.LLMs.llm_model_protocol import create_llm_model
from langchain_mistralai import ChatMistralAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI

def check():
    print("[*] Checking create_llm_model for 'mistral'...")
    try:
        # Mock env for mistral api key
        os.environ["MISTRAL_API_KEY"] = "mock-key"
        
        llm = create_llm_model("mistral", "mistral-large-latest", 0.1, 256)
        print(f"Result type: {type(llm)}")
        
        if isinstance(llm, ChatMistralAI):
            print("CORRECT: It is ChatMistralAI")
        elif isinstance(llm, AzureChatOpenAI):
            print("WRONG: It is AzureChatOpenAI")
        elif isinstance(llm, ChatOpenAI):
            print("WRONG: It is ChatOpenAI")
        else:
            print(f"UNKNOWN type: {type(llm)}")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check()
