import os
import sys
from dotenv import load_dotenv

# Add ingestion_pool to sys.path to find ingestion_pipleline
sys.path.append(os.path.join(os.getcwd(), "ingestion_pool"))

from ingestion_pipleline.Config.Config import INGESTION_CONFIG
from langchain_mistralai import MistralAIEmbeddings

def test_mistral_embeddings():
    api_key = INGESTION_CONFIG.get("mistral_api_key")
    print(f"Using API Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")
    
    if not api_key:
        print("Error: No API key found")
        return

    try:
        embeddings = MistralAIEmbeddings(
            api_key=api_key,
            model="mistral-embed"
        )
        print("MistralAIEmbeddings object created")
        
        test_text = "This is a test document."
        query_result = embeddings.embed_query(test_text)
        print(f"Successfully embedded query. Dimension: {len(query_result)}")
        
        doc_result = embeddings.embed_documents([test_text])
        print(f"Successfully embedded document. Dimension: {len(doc_result[0])}")
        
    except Exception as e:
        print(f"Error during embedding: {e}")

if __name__ == "__main__":
    test_mistral_embeddings()
