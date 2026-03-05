import os
import requests

keys_to_test = [
    "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", # current
    "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", # former in worker_pool/.env
    "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", # commented in worker_pool/.env
    "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", # commented in worker_pool/.env
]

def test_key(key):
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return True, "Valid"
        else:
            return False, f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

for key in keys_to_test:
    valid, msg = test_key(key)
    print(f"Key {key[:10]}...: {'VALID' if valid else 'INVALID'} ({msg})")
