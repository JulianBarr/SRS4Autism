import json
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
NEW_FILE = BASE_DIR / "grammar_staging_b2.json"  # The fresh B2 data
MAIN_STAGING = BASE_DIR / "grammar_staging.json"  # The file your App reads

def merge():
    if not NEW_FILE.exists():
        print(f"❌ New file not found: {NEW_FILE}")
        return

    # 1. Load New Data
    with open(NEW_FILE, 'r', encoding='utf-8') as f:
        new_items = json.load(f)
    
    # 2. Load Existing Staging (if any)
    existing_items = []
    if MAIN_STAGING.exists():
        with open(MAIN_STAGING, 'r', encoding='utf-8') as f:
            existing_items = json.load(f)
    
    # 3. Combine (Avoid duplicates by ID if possible, but simple append works for new batches)
    # Create a set of existing IDs to prevent duplicates
    existing_ids = {item['id'] for item in existing_items if 'id' in item}
    
    added_count = 0
    for item in new_items:
        if item.get('id') not in existing_ids:
            existing_items.append(item)
            added_count += 1
            
    # 4. Save back to Main Staging
    with open(MAIN_STAGING, 'w', encoding='utf-8') as f:
        json.dump(existing_items, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Merged! Added {added_count} new items to {MAIN_STAGING.name}")
    print(f"📊 Total items pending curation: {len(existing_items)}")

if __name__ == "__main__":
    merge()
