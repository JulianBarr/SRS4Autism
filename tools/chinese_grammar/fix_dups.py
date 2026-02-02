import json
from pathlib import Path

# Paths
STAGING_FILE = Path(__file__).parent / "grammar_staging.json"
APPROVED_FILE = Path(__file__).parent / "grammar_approved.json"

def deduplicate_file(filepath):
    if not filepath.exists():
        print(f"⚠️ {filepath.name} not found.")
        return

    print(f"🧹 Cleaning {filepath.name}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Dictionary automatically overwrites duplicates, keeping the last one
    # We use 'id' as the unique key. 
    # If IDs are missing/broken, we use 'grammar_point_cn' as fallback key.
    unique_map = {}
    for item in data:
        key = item.get('id') or item.get('grammar_point_cn')
        unique_map[key] = item
    
    clean_data = list(unique_map.values())
    
    # Save back
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Removed {len(data) - len(clean_data)} duplicates. Remaining: {len(clean_data)}")

if __name__ == "__main__":
    deduplicate_file(STAGING_FILE)
    deduplicate_file(APPROVED_FILE)
