
import os

path = 'requirement.txt'
content = ""
try:
    with open(path, 'r', encoding='utf-16') as f:
        content = f.read()
except Exception as e:
    print(f"UTF-16 read failed: {e}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e2:
        print(f"UTF-8 read failed: {e2}")

if content:
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    
    # Check if packages exist (simple check)
    has_mistral = any('mistralai' in l for l in lines)
    has_phoenix = any('arize-phoenix' in l for l in lines)
    
    if not has_mistral:
        lines.append('mistralai')
        print("Added mistralai")
    
    if not has_phoenix:
        lines.append('arize-phoenix')
        print("Added arize-phoenix")
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print("Fixed requirement.txt")
else:
    print("Could not read requirement.txt")
