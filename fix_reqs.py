import os

base_dir = r"c:\Users\MrYashGupta\Desktop\NewRagDemo\rag_chatbot"
services = ['Backend', 'worker_pool', 'ingestion_pool', 'evaluation_pool', 'video_processing_pool']

for service in services:
    req_path = os.path.join(base_dir, service, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace(r'\n', '\n')
        with open(req_path, 'w', encoding='utf-8') as f:
            f.write(content)
print("Fixed files.")
