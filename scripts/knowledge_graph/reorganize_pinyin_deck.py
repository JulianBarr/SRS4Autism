#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reorganize pinyin deck according to 5-stage curriculum:
Stage 1: Lips & Simple Vowels (b, p, m, f + a, o, e, i, u)
Stage 2: Tip of Tongue (d, t, n, l + ai, ei, ao, ou)
Stage 3: Root of Tongue (g, k, h + an, en, in, un)
Stage 4: Teeth & Curl (z, c, s, zh, ch, sh, r + ang, eng, ing, ong, er)
Stage 5: Magic Palatals (j, q, x, y, w + complex finals)
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import parse_pinyin, extract_tone, add_tone_to_final

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"

# 5-Stage Curriculum
STAGES = {
    1: {
        'name': 'Lips & Simple Vowels',
        'initials': ['b', 'p', 'm', 'f'],
        'finals': ['a', 'o', 'e', 'i', 'u'],
        'order': 1
    },
    2: {
        'name': 'Tip of Tongue',
        'initials': ['d', 't', 'n', 'l'],
        'finals': ['ai', 'ei', 'ao', 'ou'],
        'order': 2
    },
    3: {
        'name': 'Root of Tongue',
        'initials': ['g', 'k', 'h'],
        'finals': ['an', 'en', 'in', 'un'],
        'order': 3
    },
    4: {
        'name': 'Teeth & Curl',
        'initials': ['z', 'c', 's', 'zh', 'ch', 'sh', 'r'],
        'finals': ['ang', 'eng', 'ing', 'ong', 'er'],
        'order': 4
    },
    5: {
        'name': 'Magic Palatals',
        'initials': ['j', 'q', 'x', 'y', 'w'],
        'finals': ['i', 'u', 'ü', 'ia', 'ie', 'iao', 'iu', 'ian', 'iang', 'iong', 
                   'ua', 'uo', 'uai', 'ui', 'uan', 'uang', 'ue', 'üe', 'üan', 'ün'],
        'order': 5
    }
}

def get_stage_for_syllable(syllable: str) -> int:
    """Determine which stage a syllable belongs to"""
    parsed = parse_pinyin(syllable)
    initial = parsed.get('initial', '')
    final = parsed.get('final', '')
    
    if not initial and not final:
        return 99  # Unknown
    
    # Check each stage
    for stage_num, stage_config in STAGES.items():
        if initial in stage_config['initials']:
            if final in stage_config['finals']:
                return stage_num
        # Also check if it's just the final (for standalone vowels)
        if not initial and final in stage_config['finals']:
            return stage_num
    
    # Special case: j/q/x + u (which is actually ü)
    if initial in ['j', 'q', 'x'] and final == 'u':
        return 5
    
    return 99  # Unknown stage

def get_syllable_sort_key(syllable: str, stage: int) -> tuple:
    """Generate sort key for syllables within a stage"""
    parsed = parse_pinyin(syllable)
    initial = parsed.get('initial', '')
    final = parsed.get('final', '')
    
    stage_config = STAGES.get(stage, {})
    
    # Get order within stage
    initial_order = stage_config.get('initials', []).index(initial) if initial in stage_config.get('initials', []) else 999
    final_order = stage_config.get('finals', []).index(final) if final in stage_config.get('finals', []) else 999
    
    # Get tone
    _, tone = extract_tone(syllable)
    tone = tone if tone else 0
    
    return (stage, initial_order, final_order, tone)

def reorganize_deck():
    """Reorganize deck according to 5-stage curriculum"""
    print("=" * 80)
    print("Reorganize Pinyin Deck - 5-Stage Curriculum")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg
        print("\n📦 Extracting .apkg...")
        with zipfile.ZipFile(APKG_PATH, 'r') as z:
            z.extractall(tmpdir_path)
        
        db = tmpdir_path / "collection.anki21"
        if not db.exists():
            db = tmpdir_path / "collection.anki2"
        
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT models FROM col")
        models = json.loads(cursor.fetchone()[0])
        
        # Find syllable model
        syllable_model_id = None
        syllable_model = None
        
        for mid_str, model in models.items():
            if model.get('name') == 'CUMA - Pinyin Syllable':
                syllable_model_id = int(mid_str)
                syllable_model = model
                break
        
        if not syllable_model:
            print("❌ Syllable model not found")
            conn.close()
            return
        
        field_names = [f['name'] for f in syllable_model.get('flds', [])]
        num_templates = len(syllable_model.get('tmpls', []))
        
        # Get all notes
        print("\n📋 Analyzing notes...")
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
        all_notes = cursor.fetchall()
        
        # Organize notes by stage
        notes_by_stage = {1: [], 2: [], 3: [], 4: [], 5: [], 99: []}
        
        for note_id, flds_str in all_notes:
            fields = flds_str.split('\x1f')
            while len(fields) < len(field_names):
                fields.append('')
            
            field_dict = dict(zip(field_names, fields))
            syllable = field_dict.get('Syllable', '').strip()
            element = field_dict.get('ElementToLearn', '').strip()
            
            stage = get_stage_for_syllable(syllable)
            notes_by_stage[stage].append((note_id, field_dict, syllable, element))
        
        # Print analysis
        print(f"\n📊 Notes by stage:")
        for stage_num in [1, 2, 3, 4, 5, 99]:
            count = len(notes_by_stage[stage_num])
            stage_name = STAGES.get(stage_num, {}).get('name', 'Unknown') if stage_num != 99 else 'Unknown'
            print(f"   Stage {stage_num} ({stage_name}): {count} notes")
        
        # Sort notes within each stage
        print("\n🔄 Sorting notes within stages...")
        for stage_num in notes_by_stage:
            notes_by_stage[stage_num].sort(key=lambda x: get_syllable_sort_key(x[2], stage_num))
        
        # Delete all existing notes and cards
        print("\n🗑️  Deleting existing notes and cards...")
        cursor.execute("DELETE FROM cards WHERE nid IN (SELECT id FROM notes WHERE mid = ?)", (syllable_model_id,))
        cursor.execute("DELETE FROM notes WHERE mid = ?", (syllable_model_id,))
        
        # Recreate notes in order
        print("\n➕ Recreating notes in curriculum order...")
        current_time = int(time.time() * 1000)
        note_counter = 0
        
        for stage_num in [1, 2, 3, 4, 5, 99]:
            stage_notes = notes_by_stage[stage_num]
            
            for note_id, field_dict, syllable, element in stage_notes:
                # Build field values
                fields = [field_dict.get(name, '') for name in field_names]
                flds_str = '\x1f'.join(fields)
                
                # Create new note with sequential ID
                new_note_id = current_time + note_counter
                cursor.execute(
                    "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_note_id, f"guid{new_note_id}", syllable_model_id, current_time, -1, '', flds_str, 
                     fields[field_names.index('WordHanzi')] if 'WordHanzi' in field_names else '', 0, 0, '')
                )
                
                # Create cards
                for ord_val in range(num_templates):
                    card_id = current_time + note_counter * 1000 + ord_val
                    cursor.execute(
                        "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (card_id, new_note_id, 1, ord_val, current_time, -1, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
                    )
                
                note_counter += 1
                if note_counter % 50 == 0:
                    print(f"   Progress: {note_counter} notes recreated...")
        
        conn.commit()
        print(f"\n✅ Recreated {note_counter} notes in curriculum order")
        
        conn.close()
        
        # Repackage .apkg
        print("\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(APKG_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print("✅ Deck reorganized!")

if __name__ == "__main__":
    reorganize_deck()
