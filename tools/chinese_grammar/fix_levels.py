import json
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
APPROVED_FILE = BASE_DIR / "grammar_approved.json"

def fix_levels():
    if not APPROVED_FILE.exists():
        print("❌ File not found.")
        return

    with open(APPROVED_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated_count = 0
    
    print(f"🔍 Scanning {len(data)} items...")

    for item in data:
        # TARGET: All items from PDF extraction
        # (Assuming your new B2 items all have IDs starting with "pdf_")
        if str(item.get('id', '')).startswith('pdf_'):
            
            # EXCEPTION: If you want to keep "形容词+极了" (pdf_0) as B1, uncomment this:
            # if item['id'] == 'pdf_0': continue 

            # Apply B2 Level
            if item.get('level') != 'B2':
                item['level'] = 'B2'
                updated_count += 1

    if updated_count > 0:
        with open(APPROVED_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ patched {updated_count} items to Level B2.")
    else:
        print("🎉 No changes needed. Items are already B2.")

if __name__ == "__main__":
    fix_levels()
