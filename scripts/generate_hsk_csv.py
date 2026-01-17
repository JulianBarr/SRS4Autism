import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HSK_JSON_PATH = Path('/Users/maxent/src/complete-hsk-vocabulary/complete.json')
OUTPUT_CSV = PROJECT_ROOT / "data" / "content_db" / "hsk_vocabulary.csv"

def parse_level(level_list):
    """
    Extracts the numeric level from the level list.
    Prioritizes 'new' levels.
    """
    new_level = None
    old_level = None
    
    for level in level_list:
        if level.startswith('new-'):
            val = level.replace('new-', '')
            if val == '7+':
                val = '7' # Treat 7+ as 7 for now, or maybe 7
            new_level = val
        elif level.startswith('old-'):
            old_level = level.replace('old-', '')
            
    if new_level:
        return new_level
    return old_level

def main():
    print(f"📖 Reading {HSK_JSON_PATH}...")
    try:
        with open(HSK_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {HSK_JSON_PATH} not found.")
        return

    print(f"Found {len(data)} entries.")
    
    csv_data = []
    for entry in data:
        simplified = entry.get('simplified')
        levels = entry.get('level')
        
        if simplified and levels:
            level_num = parse_level(levels)
            if level_num:
                csv_data.append({'word': simplified, 'hsk_level': level_num})

    print(f"✍️ Writing {len(csv_data)} entries to {OUTPUT_CSV}...")
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['word', 'hsk_level'])
        writer.writeheader()
        writer.writerows(csv_data)
        
    print("✅ Done.")

if __name__ == "__main__":
    main()

