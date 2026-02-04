import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
APPROVED_FILE = BASE_DIR / "grammar_approved.json"

def revert():
    if not APPROVED_FILE.exists(): return
    
    with open(APPROVED_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    for item in data:
        # 现有的 pdf_ 数据原本都是 B1
        if str(item.get('id', '')).startswith('pdf_'):
            item['level'] = 'B1'
            count += 1
            
    with open(APPROVED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Reverted {count} items back to Level B1.")

if __name__ == "__main__":
    revert()
