import sqlite3
import os
import sys
import unicodedata
from collections import defaultdict

# ==========================================
# 1. CONFIGURATION
# ==========================================
DB_PATH = os.path.join("data", "srs4autism.db")

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

# Donor list includes n and l because they have ü syllables (nü, lü)
EXPANDED_DONORS = [
    'b', 'p', 'm', 'f', 
    'd', 't', 'n', 'l', 
    'g', 'k', 'h'
]

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def simple_parse_pinyin(syllable):
    """Splits a syllable into Initial and Final (handling ü correctly)."""
    s = syllable.lower().strip()
    
    # FIX: Replace ü variants with 'v' BEFORE normalization strips the dots
    # This ensures nü -> nv, not nu
    for char in ['ü', 'ǖ', 'ǘ', 'ǚ', 'ǜ']:
        s = s.replace(char, 'v')
    
    # Normalize (splits tones) and strip marks
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
    
    # Map 'v' back to 'ü' for index lookup if needed
    lookup_final = 'ü' if final == 'v' else final
    
    idx_initial = VAL_TO_INDEX.get(initial, -1)
    idx_final = VAL_TO_INDEX.get(lookup_final, -1)
    
    if idx_initial > idx_final:
        return initial, idx_initial
    elif idx_final > idx_initial:
        return lookup_final, idx_final
    else:
        # Fallback
        anchor = lookup_final if lookup_final else initial
        return anchor, max(idx_initial, idx_final)

# ==========================================
# 3. MAIN SCRIPT
# ==========================================
def run_dry_run():
    print(f"\n📊 PINYIN DISTRIBUTION V4 (Fixed ü/v Parsing)")
    print(f"   Database: {DB_PATH}")
    print("=" * 80)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database file not found")
        return

    distribution = defaultdict(list)
    orphans = []
    
    # 1. READ DATA
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        target_table = next((t for t in tables if 'syllable' in t and 'pinyin' in t), 'pinyin_syllable_notes')
        cursor.execute(f"SELECT note_id, syllable FROM {target_table}")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return

    # 2. INITIAL PASS
    for r in rows:
        note_id, syllable = r
        if not syllable: continue
        syllable = syllable.strip()
        
        anchor, index = calculate_strict_anchor(syllable)
        
        # Parse again just to store raw components
        ini, fin = simple_parse_pinyin(syllable)
        
        item = {'id': note_id, 'syllable': syllable, 'initial': ini, 'final': fin}
        
        if index == -1:
            orphans.append(item)
        else:
            distribution[anchor].append(item)

    # 3. "FEED THE VOWELS" LOGIC
    moved_log = []

    for vowel in BASIC_VOWELS:
        current_count = len(distribution[vowel])
        if current_count < 2:
            needed = 2 - current_count
            found = 0
            
            # The parsed final for 'ü' is 'v'
            target_final = 'v' if vowel == 'ü' else vowel
            
            for init in EXPANDED_DONORS:
                if found >= needed: break
                if init not in distribution: continue
                
                candidates = list(distribution[init])
                for item in candidates:
                    if found >= needed: break
                    
                    if item['final'] == target_final:
                        distribution[init].remove(item)
                        distribution[vowel].append(item)
                        moved_log.append(f"Moved '{item['syllable']}' from '{init}' -> '{vowel}'")
                        found += 1

    # 4. PRINT REPORT
    print(f"{'IDX':<4} | {'ELEMENT':<8} | {'TOT':<5} | {'ASSIGNED SYLLABLES'}")
    print("-" * 80)

    stage_boundaries = {
        0:  "STAGE 1: Basics",
        10: "STAGE 2: Tip of Tongue",
        18: "STAGE 3: Root of Tongue",
        25: "STAGE 4: Teeth & Curl",
        37: "STAGE 5: Compounds"
    }

    total_cards = 0

    for idx, element in enumerate(CURRICULUM_SEQUENCE):
        if idx in stage_boundaries:
            print(f"     | {stage_boundaries[idx].upper():<70} |")
            print("-" * 80)

        items = distribution[element]
        count = len(items)
        total_cards += count
        
        sep = "|" if count > 0 else "."
        
        syllables = [x['syllable'] for x in items]
        if not syllables:
            examples = ""
        else:
            examples = ", ".join(syllables[:6])
            if count > 6: examples += "..."
        
        print(f"{idx:<4} {sep} {element:<8} {sep} {count:<5} {sep} {examples}")

    print("=" * 80)
    print(f"TOTAL CARDS:    {total_cards}")
    print(f"UNMAPPED:       {len(orphans)}")
    
    if moved_log:
        print("\n📢 ADJUSTMENTS MADE:")
        for log in moved_log:
            print(f"   - {log}")

if __name__ == "__main__":
    run_dry_run()
