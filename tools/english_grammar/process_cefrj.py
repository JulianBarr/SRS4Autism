import os
import csv
import json
import time
import sys
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIG ---
BASE_DIR = Path(__file__).parent
CSV_FILENAME = "cefrj-grammar-profile-20180315.csv"
CSV_PATH = BASE_DIR / CSV_FILENAME
OUTPUT_PATH = BASE_DIR / "english_grammar_staging.json"

# Rate Limiting
SLEEP_SEC = 2  # Standard wait
ERROR_WAIT = 20 # Wait time when 429 happens

LEVEL_MAP = {
    "A1.1": "A1", "A1.2": "A1", "A1.3": "A1",
    "A2.1": "A2", "A2.2": "A2",
    "B1.1": "B1", "B1.2": "B1",
    "B2.1": "B2", "B2.2": "B2"
}

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    print("❌ GOOGLE_API_KEY not found in .env")
    sys.exit(1)

# Configure Model
try:
    genai.configure(api_key=API_KEY)
    # Using 1.5-flash as it is often more stable for free tier than 2.0-flash
    model = genai.GenerativeModel('gemini-2.5-pro')
except:
    model = None
    print("⚠️  LLM not initialized.")

def clean_level(raw_level):
    if not raw_level: return "Unknown"
    base = raw_level.split(',')[0].strip()
    return LEVEL_MAP.get(base, base.split('.')[0] if '.' in base else base)

def enrich_item_with_retry(row):
    """Enriches item with retry logic for 429 errors."""
    item = row.get('Grammatical Item', '')
    notes = row.get('Notes', '')
    
    if not model: return None

    prompt = f"""
    You are a bilingual linguistic engine (English/Chinese).
    Task: Convert this CEFR-J English grammar point into a structured bilingual card.
    
    Input: "{item}"
    Context: "{notes}"
    
    JSON Output Required:
    {{
        "grammar_point_en": "{item}",
        "grammar_point_cn": "Standard Chinese Term (e.g. 一般现在时)",
        "summary_en": "Simple explanation in English.",
        "summary_cn": "Simple explanation in Chinese.",
        "anchor_example": "A perfect example sentence."
    }}
    """
    
    # RETRY LOOP
    max_retries = 5
    for attempt in range(max_retries):
        try:
            res = model.generate_content(prompt)
            text = res.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Resource exhausted" in error_str:
                print(f"   ⏳ Quota hit. Waiting {ERROR_WAIT}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(ERROR_WAIT)
            else:
                print(f"   ⚠️ Error enriching '{item}': {e}")
                return None
    
    print(f"   ❌ Failed '{item}' after {max_retries} retries.")
    return None

def main():
    if not CSV_PATH.exists():
        print(f"❌ Cannot find CSV at: {CSV_PATH}")
        return

    print(f"📖 Reading: {CSV_PATH.name}")
    # UTF-8-SIG to handle Excel BOM
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    print(f"📊 Found {len(rows)} rows. Starting processing...")
    
    data = []
    # Resume capability
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
    existing_ids = {x['id'] for x in data}
    
    count = 0
    for i, row in enumerate(rows):
        gid = row.get('ID', str(i))
        uid = f"en_cefrj_{gid}"
        
        if uid in existing_ids: continue
        
        print(f"[{i+1}/{len(rows)}] Processing: {row.get('Grammatical Item')}")
        
        # CALL WITH RETRY
        enriched = enrich_item_with_retry(row)
        
        if enriched:
            enriched['id'] = uid
            enriched['level'] = clean_level(row.get('CEFR-J Level'))
            enriched['source_id'] = gid
            data.append(enriched)
            count += 1
            
            # Save frequently
            if count % 5 == 0:
                with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print("   💾 Saved progress...")
            
            time.sleep(SLEEP_SEC)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Done! Generated {len(data)} items in {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
