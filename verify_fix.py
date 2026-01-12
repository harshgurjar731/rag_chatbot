import urllib.request
import json
import urllib.error

url = "http://localhost:8000/rag/query/1?chatbot_id=1&use_knowledge_base=true&llm_model_provider=groq&llm_model_name=llama-3.3-70b-versatile&temperature=0.4&max_token=512&reranker_type=none&query_rewriting_type=None&guardrail_type=None&use_citation=true&datastore_id=3&query=hello&is_vision_search=false"

data = {
    "messages": [{"role": "user", "content": "hello"}],
    "selected_documents": [],
    "search_image": ""
}

headers = {'Content-Type': 'application/json'}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        print(f"Response: {response.read().decode('utf-8')}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(f"Error Content: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
