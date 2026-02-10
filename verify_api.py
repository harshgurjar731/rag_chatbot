import urllib.request
import json

try:
    print("Fetching http://localhost:8000/rag/getAssistants ...")
    with urllib.request.urlopen("http://localhost:8000/rag/getAssistants") as response:
        if response.status == 200:
            data = json.loads(response.read().decode())
            print(json.dumps(data, indent=2))
            
            # Check if qna_count exists
            if data:
                print(f"\nFound {len(data)} assistants.")
                for assistant in data:
                    if "qna_count" in assistant:
                        print(f"✅ Assistant '{assistant.get('name')}' has qna_count: {assistant['qna_count']}")
                    else:
                        print(f"❌ Assistant '{assistant.get('name')}' is MISSING qna_count")
            else:
                print("\nNo assistants found to verify.")
        else:
            print(f"Failed with status code: {response.status}")

except Exception as e:
    print(f"Error: {e}")
