import sys
import os
import json
import unicodedata
from collections import defaultdict

# Add project root to path so we can access database models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database.db import get_db_session
    from database.models import PinyinSyllableNote
except ImportError:
    print("❌ Error: Could not import database modules.")
    print("   Please run this script from your project root directory.")
    sys.exit(1)

# ==========================================
# 1. CURRICULUM DEFINITION
# ==========================================
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

# Map for O(1) lookup: {'a': 0, 'o': 1, ...}
VAL_TO_INDEX = {val: i for i, val in enumerate(CURRICULUM_SEQUENCE)}

# Known Initials for simple parsing
INITIALS = sorted([
    'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h',
    'j', 'q', 'x', 'zh', 'ch', 'sh', 'r', 'z', 'c', 's', 'y', 'w'
], key=len, reverse=True)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def simple_parse_pinyin(syllable):
    """Splits a syllable into Initial and Final (ignoring tones)."""
    norm = unicodedata.normalize('NFD', syllable)
    clean = "".join(c for c in norm if unicodedata.category(c) != 'Mn').lower().strip()
    
    initial = ''
    for ini in INITIALS:
        if clean.startswith(ini):
            initial = ini
            break
    final = clean[len(initial):]
    return initial, final

def calculate_anchor(syllable):
    """
    Determine the ElementToLearn based on Latest Component logic.
    Returns: (anchor_element, index)
    """
    initial, final = simple_parse_pinyin(syllable)
    
    idx_initial = VAL_TO_INDEX.get(initial, -1)
    idx_final = VAL_TO_INDEX.get(final, -1)
    
    # Logic: Whichever appears LATER in the curriculum wins
    if idx_initial > idx_final:
        return initial, idx_initial
    elif idx_final > idx_initial:
        return final, idx_final
    else:
        # Fallback to final, or initial if final is empty
        anchor = final if final else initial
        return anchor, max(idx_initial, idx_final)

# ==========================================
# 3. REPORTING
# ==========================================
def run_dry_run():
    print(f"\n📊 PINYIN DISTRIBUTION DRY RUN (Per Element)")
    print("=" * 75)
    
    # 1. Load Data
    distribution = defaultdict(list)
    orphans = []
    
    with get_db_session() as db:
        notes = db.query(PinyinSyllableNote).all()
        for note in notes:
            syllable = note.syllable.strip()
            anchor, index = calculate_anchor(syllable)
            
            if index == -1:
                orphans.append(syllable)
            else:
                distribution[anchor].append(syllable)

    # 2. Print Report Row by Row
    print(f"{'IDX':<4} | {'ELEMENT':<8} | {'COUNT':<5} | {'ASSIGNED SYLLABLES (Examples)'}")
    print("-" * 75)

    # Markers to show where stages begin
    stage_boundaries = {
        0:  "STAGE 1: Basics",
        10: "STAGE 2: Tip of Tongue",
        18: "STAGE 3: Root of Tongue",
        25: "STAGE 4: Teeth & Curl",
        37: "STAGE 5: Compounds"
    }

    total_assigned = 0

    for idx, element in enumerate(CURRICULUM_SEQUENCE):
        # Print Stage Header if applicable
        if idx in stage_boundaries:
            print(f"     | {stage_boundaries[idx].upper():<65} |")
            print("-" * 75)

        cards = distribution[element]
        count = len(cards)
        total_assigned += count
        
        # Format examples
        if count == 0:
            examples = ""
        else:
            # Show first 5 examples
            examples = ", ".join(cards[:6])
            if count > 6:
                examples += "..."
        
        # Highlight empty rows with dot, filled rows with normal pipe
        separator = "|" if count > 0 else "."
        print(f"{idx:<4} {separator} {element:<8} {separator} {count:<5} {separator} {examples}")

    print("=" * 75)
    print(f"TOTAL NOTES:    {len(notes)}")
    print(f"MAPPED:         {total_assigned}")
    print(f"UNMAPPED:       {len(orphans)}")
    
    if orphans:
        print("\n⚠️  UNMAPPED SYLLABLES (Components not in curriculum):")
        print(", ".join(orphans[:20]))

if __name__ == "__main__":
    run_dry_run()
