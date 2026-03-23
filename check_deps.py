import os
import re
from pathlib import Path

# Mapping of top-level import to PyPI package name (add specific ones here)
IMPORT_TO_PACKAGE = {
    'langchain_core': 'langchain-core',
    'langchain_community': 'langchain-community',
    'langchain_openai': 'langchain-openai',
    'langchain_mistralai': 'langchain-mistralai',
    'langchain_chroma': 'langchain-chroma',
    'langchain_qdrant': 'langchain-qdrant',
    'langchain_nvidia_ai_endpoints': 'langchain-nvidia-ai-endpoints',
    'langchain_huggingface': 'langchain-huggingface',
    'qdrant_client': 'qdrant-client',
    'faiss': 'faiss-cpu',
    'chromadb': 'chromadb',
    'nemoguardrails': 'nemoguardrails',
    'arize_phoenix': 'arize-phoenix',
    'openinference': 'openinference-instrumentation',
    'psycopg2': 'psycopg2-binary',
    'sqlmodel': 'sqlmodel',
    'pydantic': 'pydantic',
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
    'redis': 'redis',
    'requests': 'requests',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'scikit_learn': 'scikit-learn',
    'skol': 'scikit-learn',
    'sklearn': 'scikit-learn',
    'llama_index': 'llama-index-core',
    'llama_parse': 'llama-parse',
    'llama_cloud': 'llama-cloud',
    'llama_cloud_services': 'llama-cloud-services',
    'sentence_transformers': 'sentence-transformers',
    'transformers': 'transformers',
    'huggingface_hub': 'huggingface-hub',
    'cv2': 'opencv-python-headless',
    'PIL': 'pillow',
    'fitz': 'PyMuPDF',
    'camelot': 'camelot-py',
    'pytesseract': 'pytesseract',
    'unstructured': 'unstructured',
    'beautifulsoup4': 'beautifulsoup4',
    'bs4': 'beautifulsoup4',
    'networkx': 'networkx',
    'pytest': 'pytest',
}

def get_root_requirements(root_req_path):
    root_pkgs = set()
    if not os.path.exists(root_req_path): return root_pkgs
    with open(root_req_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-'): continue
            pkg = re.split(r'[=><]', line)[0].strip().lower()
            root_pkgs.add(pkg)
    return root_pkgs

def get_service_requirements(req_path):
    pkgs = set()
    if not os.path.exists(req_path): return pkgs
    with open(req_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-'): continue
            # Handle extras e.g. passlib[bcrypt]
            pkg = re.split(r'[\[=><]', line)[0].strip().lower()
            pkgs.add(pkg)
    return pkgs

def scan_imports_in_dir(dir_path):
    imports = set()
    for root, _, files in os.walk(dir_path):
        # skip venv
        if 'venv' in root or '.venv' in root: continue
        for file in files:
            if file.endswith('.py'):
                with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        # simple regex for `import X` or `from X import`
                        m1 = re.match(r'^import\s+([a-zA-Z0-9_\.]+)', line)
                        m2 = re.match(r'^from\s+([a-zA-Z0-9_\.]+)\s+import', line)
                        if m1:
                            top_level = m1.group(1).split('.')[0]
                            imports.add(top_level)
                        if m2:
                            top_level = m2.group(1).split('.')[0]
                            imports.add(top_level)
    return imports

std_libs = {'os', 'sys', 'time', 'json', 're', 'logging', 'typing', 'tempfile', 'shutil', 'datetime', 'pathlib', 'math', 'collections', 'uuid', 'io', 'base64', 'asyncio', 'traceback', 'socket', 'subprocess', 'mimetypes', 'enum'}

def main():
    base_dir = r"c:\Users\MrYashGupta\Desktop\NewRagDemo\rag_chatbot"
    root_req_path = os.path.join(base_dir, "requirements.txt")
    root_reqs = get_root_requirements(root_req_path)
    
    services = ['Backend', 'worker_pool', 'ingestion_pool', 'evaluation_pool', 'video_processing_pool']
    
    for service in services:
        print(f"\\n=== Checking {service} ===")
        service_dir = os.path.join(base_dir, service)
        req_path = os.path.join(service_dir, "requirements.txt")
        
        service_reqs = get_service_requirements(req_path)
        imports = scan_imports_in_dir(service_dir)
        
        missing = []
        for imp in imports:
            if imp in std_libs: continue
            
            # Map import top-level package to PyPI package name
            pkg = IMPORT_TO_PACKAGE.get(imp, imp).lower()
            # If the import itself is a known local module, skip
            if pkg in ['models', 'utils', 'database', 'routers', 'services', 'config', 'rag_pipeline', 'main', 'dependencies', 'auth', 'schemas']: continue
            
            # If the package is missing in service reqs but exists in root reqs, it was forgotten!
            if pkg not in service_reqs:
                # Need to check if it's in root reqs or IMPORT_TO_PACKAGE dict explicitly to avoid local module noise
                if pkg in root_reqs or imp in IMPORT_TO_PACKAGE:
                    missing.append(pkg)
        
        if missing:
            print(f"Missing packages to add to {service}/requirements.txt: {set(missing)}")
        else:
            print(f"No obvious missing packages.")

if __name__ == '__main__':
    main()
