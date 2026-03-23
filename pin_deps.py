import os
import re

def parse_root_reqs(root_req_path):
    pkg_versions = {}
    with open(root_req_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-'): continue
            # Split by ==, >=, <=, etc.
            match = re.match(r'^([^=><~\[]+)(.*)$', line)
            if match:
                pkg_name = match.group(1).strip().lower()
                version_spec = match.group(2).strip()
                # we want the exact line from root just matched by base package name to keep any brackets or exact version
                pkg_versions[pkg_name] = line
    return pkg_versions

def update_service_reqs(req_path, pkg_versions):
    if not os.path.exists(req_path): return
    updated_lines = []
    with open(req_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('-'):
            updated_lines.append(line)
            continue
            
        # Extract base package name
        match = re.match(r'^([^=><~\[]+)', stripped)
        if match:
            pkg_name = match.group(1).strip().lower()
            if pkg_name in pkg_versions:
                # Use the exact versioned line from root
                updated_lines.append(pkg_versions[pkg_name] + '\\n')
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)
            
    with open(req_path, 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)

def main():
    base_dir = r"c:\Users\MrYashGupta\Desktop\NewRagDemo\rag_chatbot"
    root_req_path = os.path.join(base_dir, "requirements.txt")
    pkg_versions = parse_root_reqs(root_req_path)
    
    # Also add some manual mappings if they are aliased or differently named in root
    pkg_versions['qdrant_client'] = pkg_versions.get('qdrant-client', 'qdrant-client==1.16.2')
    pkg_versions['faiss'] = pkg_versions.get('faiss-cpu', 'faiss-cpu==1.13.2')
    
    services = ['Backend', 'worker_pool', 'ingestion_pool', 'evaluation_pool', 'video_processing_pool']
    
    for service in services:
        req_path = os.path.join(base_dir, service, "requirements.txt")
        update_service_reqs(req_path, pkg_versions)
        print(f"Updated versions in {service}/requirements.txt")
        
if __name__ == '__main__':
    main()
