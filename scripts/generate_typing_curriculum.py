import zipfile
import sqlite3
import json
import re
import os
import tempfile
import unicodedata
import sys
import random

# ==========================================
# CONFIGURATION
# ==========================================
TARGET_TOTAL = 150
MAX_PER_LESSON = 7  # 150 words / ~23 active lessons = ~6.5 words per lesson

# Optimized Sequence (Vowels moved up)
USER_SEQUENCE = ['a', 'f', 'd', 'e', 'i', 'u', 's', 'l', 'g', 'h']
REMAINING_KEYS = [
    'j', 'k', 'n', 'o',
    'r', 't', 'y', 'p',      
    'w', 'q', 'b', 'm',      
    'z', 'x', 'c', 'v'       
]

FULL_SEQUENCE = USER_SEQUENCE + REMAINING_KEYS
KEY_RANK_MAP = {char: index for index, char in enumerate(FULL_SEQUENCE)}

FIELD_PINYIN = 'WordPinyin'
FIELD_HANZI = 'WordHanzi'
FIELD_AUDIO = 'WordAudio'
FIELD_IMAGE = 'WordPicture'

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_unlocking_lesson(clean_syllable):
    if not clean_syllable: return 999
    current_max_rank = -1
    for char in clean_syllable:
        if char not in KEY_RANK_MAP: return 999 
        rank = KEY_RANK_MAP[char]
        if rank > current_max_rank:
            current_max_rank = rank
    return current_max_rank

def clean_syllable_text(text):
    nfkd = unicodedata.normalize('NFKD', text)
    only_ascii = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r'[^a-zA-Z]', '', only_ascii).lower()

def extract_anki_db(apkg_path):
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
        files = zip_ref.namelist()
        if 'collection.anki21' in files: db = 'collection.anki21'
        elif 'collection.anki2' in files: db = 'collection.anki2'
        else: raise ValueError("No DB found")
        zip_ref.extract(db, temp_dir)
    return os.path.join(temp_dir, db)

# ==========================================
# MAIN EXECUTION
# ==========================================

def generate_balanced_curriculum(apkg_path):
    print(f"--- Balancing Curriculum from {apkg_path} ---")
    try:
        db_path = extract_anki_db(apkg_path)
    except Exception as e:
        print(f"Error: {e}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT models FROM col")
    models = json.loads(cursor.fetchone()[0])

    # 1. COLLECT ALL CANDIDATES FIRST
    raw_lessons = {i: [] for i in range(len(FULL_SEQUENCE))}
    seen_signatures = set() # (hanzi, syllable, index)

    for model_id, model_data in models.items():
        flds = model_data['flds']
        field_names = [f['name'] for f in flds]
        
        if FIELD_PINYIN in field_names:
            idx_pinyin = field_names.index(FIELD_PINYIN)
            idx_hanzi = field_names.index(FIELD_HANZI)
            idx_audio = field_names.index(FIELD_AUDIO) if FIELD_AUDIO in field_names else -1
            idx_image = field_names.index(FIELD_IMAGE) if FIELD_IMAGE in field_names else -1

            cursor.execute("SELECT flds FROM notes WHERE mid = ?", (model_id,))
            notes = cursor.fetchall()

            for note in notes:
                fields = note[0].split('\x1f')
                if len(fields) <= idx_pinyin: continue

                raw_full_pinyin = fields[idx_pinyin]
                hanzi = fields[idx_hanzi]
                syllables_raw = raw_full_pinyin.split()
                
                for i, syl_raw in enumerate(syllables_raw):
                    syl_clean = clean_syllable_text(syl_raw)
                    if len(syl_clean) < 1: continue

                    signature = (hanzi, syl_clean, i)
                    if signature in seen_signatures: continue
                    
                    unlock_idx = get_unlocking_lesson(syl_clean)
                    
                    if unlock_idx < 999:
                        raw_lessons[unlock_idx].append({
                            "hanzi": hanzi,
                            "target_syllable": syl_clean,
                            "target_index": i,
                            "full_pinyin_raw": raw_full_pinyin,
                            "audio": fields[idx_audio] if idx_audio >= 0 else "",
                            "image": fields[idx_image] if idx_image >= 0 else ""
                        })
                        seen_signatures.add(signature)

    conn.close()

    # 2. FILTER & BALANCE
    final_lessons = {}
    total_selected = 0
    
    for i in sorted(raw_lessons.keys()):
        candidates = raw_lessons[i]
        if not candidates: continue
        
        # Strategy: Prioritize Unique Syllables
        unique_picks = []
        seen_syls = set()
        duplicates = []
        
        # Shuffle first to avoid alphabetical bias
        random.shuffle(candidates)
        
        for cand in candidates:
            syl = cand['target_syllable']
            if syl not in seen_syls:
                unique_picks.append(cand)
                seen_syls.add(syl)
            else:
                duplicates.append(cand)
        
        # Fill the quota
        selected = unique_picks[:MAX_PER_LESSON]
        
        # If we have space left and need more volume, add duplicates
        slots_left = MAX_PER_LESSON - len(selected)
        if slots_left > 0:
            selected.extend(duplicates[:slots_left])
            
        final_lessons[i] = selected
        total_selected += len(selected)

    # 3. OUTPUT
    print(f"\n=== BALANCED MAP ({total_selected} targets, Limit {MAX_PER_LESSON}/lesson) ===")
    
    for i, key in enumerate(FULL_SEQUENCE):
        if i in final_lessons:
            new_items = final_lessons[i]
            count = len(new_items)
            
            # Simplified print logic to avoid SyntaxError
            syl_list = [item['target_syllable'] for item in new_items]
            preview = ", ".join(syl_list)
            
            print(f"Lesson {i+1} (Key '{key.upper()}'): +{count} targets -> {preview}")
        else:
            if i < len(USER_SEQUENCE):
                 print(f"Lesson {i+1} (Key '{key.upper()}'): 0 targets (GAP)")

    with open('balanced_typing_course.json', 'w', encoding='utf-8') as f:
        json.dump(final_lessons, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to balanced_typing_course.json")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_balanced_curriculum(sys.argv[1])
    else:
        print("Usage: python generate_typing_curriculum.py <path_to_apkg>")
