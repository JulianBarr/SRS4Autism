print("--- Script loaded. Initialization starting... ---", flush=True)

import sqlite3
import os
import json
import unicodedata
import sys
from collections import defaultdict

# ==========================================
# 1. ROBUST CONFIGURATION
# ==========================================
def find_database():
    """Attempts to find the database file in current or parent directories."""
    candidates = [
        os.path.join(os.getcwd(), "data", "srs4autism.db"),             # Run from root
        os.path.join(os.getcwd(), "..", "data", "srs4autism.db"),       # Run from scripts/
        os.path.join(os.path.dirname(__file__), "..", "data", "srs4autism.db"), # Relative to script
        os.path.join("data", "srs4autism.db"),                          # Simple relative
    ]
    
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
            
    return None

DB_PATH = find_database()

# Strict Curriculum Sequence
CURRICULUM_SEQUENCE = [
    # STAGE 1: Basics
    'a', 'o', 'e', 'i', 'u', 'ü', 
    'b', 'p', 'm', 'f',            
    # STAGE 2
    'd', 't', 'n', 'l',
    'ai', 'ei', 'ao', 'ou',
    # STAGE 3
    'g', 'k', 'h',
    'an', 'en', 'in', 'un',
    # STAGE 4
    'z', 'c', 's', 
    'zh', 'ch', 'sh', 'r',
    'ang', 'eng', 'ing', 'ong', 'er',
    # STAGE 5
    'j', 'q', 'x', 'y', 'w',
    'ia', 'ie', 'iao', 'iu', 'ian', 'iang', 'iong', 
    'ua', 'uo', 'uai', 'ui', 'uan', 'uang', 
    'ue', 'üe', 'üan', 'ün'
]

VAL_TO_INDEX = {val: i for i, val in enumerate(CURRICULUM_SEQUENCE)}

INITIALS = sorted([
    'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h',
    'j', 'q', 'x', 'zh', 'ch', 'sh', 'r', 'z', 'c', 's', 'y', 'w'
], key=len, reverse=True)

BASIC_VOWELS = ['a', 'o', 'e', 'i', 'u', 'ü']
EXPANDED_DONORS = ['b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h']

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def simple_parse_pinyin(syllable):
    """Splits a syllable into Initial and Final (handling ü correctly)."""
    if not syllable: return "", ""
    s = syllable.lower().strip()
    
    # FIX: Replace ü variants with 'v' BEFORE normalization
    for char in ['ü', 'ǖ', 'ǘ', 'ǚ', 'ǜ']:
        s = s.replace(char, 'v')
    
    norm = unicodedata.normalize('NFD', s)
    clean = "".join(c for c in norm if unicodedata.category(c) != 'Mn').strip()
    
    initial = ''
    for ini in INITIALS:
        if clean.startswith(ini):
            initial = ini
            break
    final = clean[len(initial):]
    return initial, final

def calculate_strict_anchor(syllable):
    initial, final = simple_parse_pinyin(syllable)
    lookup_final = 'ü' if final == 'v' else final
    
    idx_initial = VAL_TO_INDEX.get(initial, -1)
    idx_final = VAL_TO_INDEX.get(lookup_final, -1)
    
    if idx_initial > idx_final:
        return initial
    elif idx_final > idx_initial:
        return lookup_final
    else:
        return lookup_final if lookup_final else initial

# ==========================================
# 3. MAIN MIGRATION SCRIPT
# ==========================================
def run_migration():
    print(f"🚀 STARTING DB MIGRATION...", flush=True)
    
    if not DB_PATH:
        print("❌ CRITICAL ERROR: Could not find 'srs4autism.db'.")
        print(f"   Current Directory: {os.getcwd()}")
        print("   Please run this from the project root.")
        return

    print(f"   Database found at: {DB_PATH}", flush=True)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Identify Table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        target_table = next((t for t in tables if 'syllable' in t and 'pinyin' in t), 'pinyin_syllable_notes')
        print(f"   Target Table: {target_table}", flush=True)

        # 2. Fetch Data
        cursor.execute(f"SELECT note_id, syllable, fields FROM {target_table}")
        rows = cursor.fetchall()
        print(f"   Loaded {len(rows)} notes. Analyzing...", flush=True)

        distribution = defaultdict(list)
        
        # 3. Calculate Strict Anchors (In Memory)
        for row in rows:
            note_id, syllable, fields_json = row
            if not syllable: continue
            
            syllable = syllable.strip()
            anchor = calculate_strict_anchor(syllable)
            ini, fin = simple_parse_pinyin(syllable)

            distribution[anchor].append({
                'note_id': note_id,
                'syllable': syllable,
                'fields_str': fields_json,
                'initial': ini,
                'final': fin,
                'target_anchor': anchor
            })

        # 4. Feed The Vowels (Reassign Anchors)
        moves_count = 0
        for vowel in BASIC_VOWELS:
            if len(distribution[vowel]) < 2:
                needed = 2 - len(distribution[vowel])
                found = 0
                target_final = 'v' if vowel == 'ü' else vowel
                
                for donor in EXPANDED_DONORS:
                    if found >= needed: break
                    if donor not in distribution: continue
                    
                    candidates = list(distribution[donor])
                    for item in candidates:
                        if found >= needed: break
                        if item['final'] == target_final:
                            # REASSIGN ANCHOR
                            item['target_anchor'] = vowel
                            
                            distribution[donor].remove(item)
                            distribution[vowel].append(item)
                            
                            found += 1
                            moves_count += 1
                            print(f"   -> Moving '{item['syllable']}' to feed vowel '{vowel}'", flush=True)

        # 5. Commit Updates to DB
        print(f"   Writing changes to database...", flush=True)
        updated_rows = 0
        
        all_items = []
        for items in distribution.values():
            all_items.extend(items)

        for item in all_items:
            try:
                fields = json.loads(item['fields_str']) if item['fields_str'] else {}
                old_anchor = fields.get('ElementToLearn', '')
                new_anchor = item['target_anchor']

                if old_anchor != new_anchor:
                    fields['ElementToLearn'] = new_anchor
                    new_json = json.dumps(fields, ensure_ascii=False)
                    
                    cursor.execute(f"UPDATE {target_table} SET fields = ? WHERE note_id = ?", (new_json, item['note_id']))
                    updated_rows += 1
            except Exception as e:
                print(f"⚠️ Error updating note {item['note_id']}: {e}", flush=True)

        conn.commit()
        conn.close()
        
        print("-" * 50, flush=True)
        print(f"✅ DONE. Redistributed {updated_rows} cards.", flush=True)
        print(f"   (Moved {moves_count} cards to fill empty vowels)", flush=True)

    except Exception as e:
        print("\n❌ FATAL SCRIPT ERROR:", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_migration()
