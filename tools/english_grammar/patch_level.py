import csv
import json
import re
from pathlib import Path

# --- CONFIG ---
BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "cefrj-grammar-profile-20180315.csv"
JSON_PATH = BASE_DIR / "english_grammar_staging.json"

# Map to standard CEFR
LEVEL_MAP = {
    "A1.1": "A1", "A1.2": "A1", "A1.3": "A1",
    "A2.1": "A2", "A2.2": "A2",
    "B1.1": "B1", "B1.2": "B1",
    "B2.1": "B2", "B2.2": "B2"
}

def normalize_level(raw):
    if not raw or raw.strip() == "":
        return None
    # Handle messy formats like "A2-B2 ,C2" or "A1.1"
    # 1. Take first part before comma or slash
    first_part = re.split(r'[,/]', raw)[0].strip()
    # 2. Take first part before hyphen (e.g. A2-B2 -> A2)
    base = first_part.split('-')[0].strip()
    # 3. Handle sub-levels (A1.1 -> A1)
    if "." in base:
        base = base.split('.')[0]
    
    return LEVEL_MAP.get(base, base) # Return mapped or raw (e.g. "A1")

def patch():
    if not JSON_PATH.exists() or not CSV_PATH.exists():
        print("❌ Files not found.")
        return

    # 1. Load Data
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        csv_rows = list(csv.DictReader(f))
        # Create lookup dict by ID
        csv_map = {row['ID']: row for row in csv_rows}

    patched_count = 0
    
    print(f"🔍 Scanning {len(json_data)} items for missing levels...")

    # 2. Patch
    for item in json_data:
        current_level = item.get('level', 'Unknown')
        
        # Only fix if unknown or missing
        if current_level == "Unknown" or not current_level:
            source_id = item.get('source_id')
            if source_id and source_id in csv_map:
                row = csv_map[source_id]
                
                # FALLBACK STRATEGY
                new_level = normalize_level(row.get('CEFR-J Level'))
                
                if not new_level:
                    new_level = normalize_level(row.get('EGP')) # Cambridge EGP
                if not new_level:
                    new_level = normalize_level(row.get('GSELO')) # Global Scale
                if not new_level:
                    new_level = normalize_level(row.get('Core Inventory'))
                
                if new_level:
                    item['level'] = new_level
                    patched_count += 1
                    # print(f"   Fixed {item['grammar_point_en']}: {new_level}")

    # 3. Save
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Patched {patched_count} items. Levels updated in {JSON_PATH.name}")

if __name__ == "__main__":
    patch()
