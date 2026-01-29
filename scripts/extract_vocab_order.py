#!/usr/bin/env python3
"""
Extract sort order from legacy Anki APKG file.
This script extracts the English words from the original Anki deck to preserve the learning order.
"""

import sqlite3
import zipfile
import json
import re
import os
import sys
import tempfile
from pathlib import Path
from html import unescape

# Configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "content_db"
APKG_PATH = DATA_DIR / "English__Vocabulary__2. Level 2.apkg"
OUTPUT_PATH = DATA_DIR / "vocab_order.json"

def clean_anki_field(text):
    """Clean HTML and Anki formatting from text."""
    if not text:
        return ""
    # Decode HTML entities
    text = unescape(text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove Anki cloze/image tags
    text = re.sub(r'\[.*?\]', '', text)
    # Replace non-breaking spaces
    text = text.replace('\xa0', ' ')
    # Remove "Please update..." stub text
    if "please update" in text.lower():
        return ""
    return text.strip().lower()

def extract_order():
    if not APKG_PATH.exists():
        print(f"Error: APKG file not found at {APKG_PATH}")
        sys.exit(1)

    print(f"Processing {APKG_PATH}...")
    
    order_map = {}
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(APKG_PATH, 'r') as z:
                # Find database file
                db_files = ['collection.anki21', 'collection.anki2']
                db_path = None
                
                for db_file in db_files:
                    if db_file in z.namelist():
                        z.extract(db_file, tmpdir)
                        db_path = Path(tmpdir) / db_file
                        print(f"Found database: {db_file}")
                        break
                
                if not db_path or not db_path.exists():
                    print("Error: No database found in APKG")
                    sys.exit(1)
                
                # Read database
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Get model field names
                cursor.execute("SELECT models FROM col LIMIT 1")
                row = cursor.fetchone()
                if not row or not row[0]:
                    print("Error: Could not read models")
                    conn.close()
                    sys.exit(1)
                
                models_json = json.loads(row[0])
                model_fields = {}
                
                for model_id_str, model_data in models_json.items():
                    fields = [fld.get('name', '') for fld in model_data.get('flds', [])]
                    model_fields[int(model_id_str)] = fields
                
                # Get notes ordered by ID (to maintain creation/deck order)
                cursor.execute("SELECT id, mid, flds FROM notes ORDER BY id")
                rows = cursor.fetchall()
                
                print(f"Found {len(rows)} notes")
                
                order_index = 0
                for note_id, mid, flds_str in rows:
                    fields = flds_str.split('\x1f')
                    field_names = model_fields.get(mid, [])
                    
                    english_word = None
                    
                    # Strategy: Look for "Back" field or use first field
                    # Note: In some decks, the word is in the Back, in others Front.
                    
                    # 1. Try to find field named 'Back'
                    for i, field_name in enumerate(field_names):
                        if field_name.lower() == 'back' and i < len(fields):
                            val = clean_anki_field(fields[i])
                            if val and len(val) < 100: # Sanity check length
                                english_word = val
                                break
                    
                    # 2. Fallback: Check 2nd field (index 1) - common for Back
                    if not english_word and len(fields) > 1:
                        val = clean_anki_field(fields[1])
                        if val and len(val) < 100:
                            english_word = val
                            
                    # 3. Fallback: Check 1st field (index 0)
                    if not english_word and len(fields) > 0:
                        val = clean_anki_field(fields[0])
                        if val and len(val) < 100:
                            english_word = val

                    if english_word:
                        # Skip filenames that might have leaked into fields
                        if re.match(r'.+\.(jpg|png|mp3|wav)$', english_word):
                            continue
                            
                        if english_word not in order_map:
                            order_map[english_word] = order_index
                            order_index += 1
                
                conn.close()
                
        # Save to JSON
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(order_map, f, ensure_ascii=False, indent=2)
            
        print(f"Successfully saved order for {len(order_map)} words to {OUTPUT_PATH}")
        
        # Validation: Print first 5
        print("First 5 entries:")
        first_5 = list(order_map.items())[:5]
        for k, v in first_5:
            print(f"  {k}: {v}")

    except Exception as e:
        print(f"Error extracting order: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    extract_order()

