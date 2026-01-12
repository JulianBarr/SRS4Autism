import json
import urllib.parse
from pathlib import Path
import shutil
import re

# Configuration
FILES_TO_FIX = [
    # (Path, Type)
    ("data/content_db/chinese_word_similarity.json", "json"),
    ("knowledge_graph/world_model_complete.ttl", "ttl")
]

def fix_json(file_path):
    print(f"🔧 Processing JSON: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Helper to decode a single string
    def decode_str(s):
        return urllib.parse.unquote(s) if isinstance(s, str) else s

    # Handle the specific structure of similarity graph
    # Structure: {"similarities": { "KEY": [ {"neighbor_id": "VAL"...} ] } }
    
    root = data
    if "similarities" in data:
        root = data["similarities"]
    
    fixed_root = {}
    count = 0
    
    # If the file is a flat dict, root is data. If nested, root is data['similarities']
    # We iterate properly either way
    source_items = root.items() if isinstance(root, dict) else []
    
    for key, neighbors in source_items:
        # 1. Fix the Key
        new_key = decode_str(key)
        
        # 2. Fix the Neighbors list
        new_neighbors = []
        if isinstance(neighbors, list):
            for n in neighbors:
                if isinstance(n, dict):
                    # Fix specific fields known to be encoded
                    new_n = n.copy()
                    if "neighbor_id" in new_n:
                        new_n["neighbor_id"] = decode_str(new_n["neighbor_id"])
                    if "neighbor_label" in new_n:
                         # Labels might be encoded too, safe to unquote
                        new_n["neighbor_label"] = decode_str(new_n["neighbor_label"])
                    new_neighbors.append(new_n)
                else:
                    new_neighbors.append(n)
        
        fixed_root[new_key] = new_neighbors
        count += 1

    # Reconstruct
    if "similarities" in data:
        data["similarities"] = fixed_root
    else:
        data = fixed_root

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ Decoded {count} keys/entries.")

def fix_ttl(file_path):
    print(f"🔧 Processing TTL: {file_path}")
    
    # Read line by line to be memory safe-ish, but for <100MB reading all is fine
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # We want to unquote mostly URIs. 
    # Global unquote is usually safe for Turtle unless you have literal % signs for math.
    # To be safer, we can target the pattern %XX
    
    # Method A: Global Unquote (Fastest, effective for your specific issue)
    # This turns <.../word-%E4%BD%A0> into <.../word-你>
    decoded_content = urllib.parse.unquote(content)
    
    # Check if we actually changed anything
    if content == decoded_content:
        print("   ℹ️  No encoding found. File unchanged.")
        return

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(decoded_content)
        
    print("   ✅ File decoded and saved.")

def main():
    root = Path(".")
    
    for relative_path, file_type in FILES_TO_FIX:
        full_path = root / relative_path
        
        if not full_path.exists():
            print(f"⚠️  Skipping missing file: {full_path}")
            continue
            
        # Backup
        backup_path = full_path.with_suffix(full_path.suffix + ".bak")
        shutil.copy2(full_path, backup_path)
        print(f"💾 Backed up to {backup_path.name}")
        
        try:
            if file_type == "json":
                fix_json(full_path)
            elif file_type == "ttl":
                fix_ttl(full_path)
        except Exception as e:
            print(f"❌ Error fixing {full_path.name}: {e}")
            # Restore backup on failure
            shutil.copy2(backup_path, full_path)
            print("   Restored backup.")

if __name__ == "__main__":
    main()
