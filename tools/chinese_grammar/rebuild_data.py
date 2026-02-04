import json
from pathlib import Path

# Paths to the "Source of Truth" files
BASE_DIR = Path(__file__).parent
# 1. The Base Wiki Data (A1/A2) - likely in grammar_staging or the old KG file
#    We will try grammar_staging.json first, but filter strictly for numeric IDs.
SOURCE_A1_A2 = BASE_DIR / "grammar_staging.json" 
# 2. The Intermediate Book (B1)
SOURCE_B1 = BASE_DIR / "grammar_staging_pdf.json"
# 3. The Upper Intermediate Book (B2)
SOURCE_B2 = BASE_DIR / "grammar_staging_b2.json"

OUTPUT_FILE = BASE_DIR / "grammar_approved.json"

def load_json(path):
    if not path.exists():
        print(f"⚠️ Warning: {path.name} not found. Skipping.")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def rebuild():
    final_list = []
    seen_ids = set()
    
    print("🏭 STARTING FACTORY RESET...")

    # --- PHASE 1: A1 & A2 (Numeric IDs) ---
    # We strip these from the base staging file
    raw_a1_a2 = load_json(SOURCE_A1_A2)
    count_a = 0
    for item in raw_a1_a2:
        # Strict Filter: Only keep items with numeric IDs (e.g., "1", "237")
        # This filters out any previous 'pdf_' pollution in this file.
        pid = str(item.get('id', ''))
        if pid.isdigit():
            # Clean up: Remove any pre-existing 'level' to let export script handle A1/A2 logic
            if 'level' in item: del item['level']
            
            if pid not in seen_ids:
                final_list.append(item)
                seen_ids.add(pid)
                count_a += 1
    print(f"   👉 Loaded {count_a} Base items (A1/A2) from {SOURCE_A1_A2.name}")

    # --- PHASE 2: B1 (Intermediate PDF) ---
    raw_b1 = load_json(SOURCE_B1)
    count_b1 = 0
    for i, item in enumerate(raw_b1):
        # Force Clean ID and Level
        new_id = f"pdf_{i}"
        item['id'] = new_id
        item['level'] = "B1" # HARD ENFORCE
        
        if new_id not in seen_ids:
            final_list.append(item)
            seen_ids.add(new_id)
            count_b1 += 1
    print(f"   👉 Loaded {count_b1} Intermediate items (B1) from {SOURCE_B1.name}")

    # --- PHASE 3: B2 (Upper Intermediate PDF) ---
    raw_b2 = load_json(SOURCE_B2)
    count_b2 = 0
    for i, item in enumerate(raw_b2):
        # Force Clean ID and Level
        new_id = f"pdf_b2_{i}"
        item['id'] = new_id
        item['level'] = "B2" # HARD ENFORCE
        
        if new_id not in seen_ids:
            final_list.append(item)
            seen_ids.add(new_id)
            count_b2 += 1
    print(f"   👉 Loaded {count_b2} Upper-Int items (B2) from {SOURCE_B2.name}")

    # --- SAVE ---
    print("-" * 40)
    print(f"✅ Rebuild Complete. Total Items: {len(final_list)}")
    print(f"   (A1/A2: {count_a} | B1: {count_b1} | B2: {count_b2})")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)
    print(f"💾 Overwritten: {OUTPUT_FILE}")

if __name__ == "__main__":
    rebuild()
