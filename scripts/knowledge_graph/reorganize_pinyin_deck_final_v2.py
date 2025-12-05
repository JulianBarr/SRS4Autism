#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final reorganization of pinyin deck:
1. Copy ExampleChar, Picture, Tone1-4 from original deck for elements
2. Mix elements and syllables - element "a" right before syllables using "a"
3. Mix initials and finals within each stage
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
import time
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import extract_tone, add_tone_to_final, parse_pinyin

PROJECT_ROOT = project_root
ORIGINAL_APKG = PROJECT_ROOT / "data" / "content_db" / "语言语文__拼音.apkg"
SAMPLE_APKG = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"

# 5-Stage Curriculum
STAGES = {
    1: {'name': 'Lips & Simple Vowels', 'initials': ['b', 'p', 'm', 'f'], 'finals': ['a', 'o', 'e', 'i', 'u'], 'order': 1},
    2: {'name': 'Tip of Tongue', 'initials': ['d', 't', 'n', 'l'], 'finals': ['ai', 'ei', 'ao', 'ou'], 'order': 2},
    3: {'name': 'Root of Tongue', 'initials': ['g', 'k', 'h'], 'finals': ['an', 'en', 'in', 'un'], 'order': 3},
    4: {'name': 'Teeth & Curl', 'initials': ['z', 'c', 's', 'zh', 'ch', 'sh', 'r'], 'finals': ['ang', 'eng', 'ing', 'ong', 'er'], 'order': 4},
    5: {'name': 'Magic Palatals', 'initials': ['j', 'q', 'x', 'y', 'w'], 'finals': ['i', 'u', 'ü', 'ia', 'ie', 'iao', 'iu', 'ian', 'iang', 'iong', 'ua', 'uo', 'uai', 'ui', 'uan', 'uang', 'ue', 'üe', 'üan', 'ün'], 'order': 5}
}

def get_stage_for_syllable(syllable: str) -> int:
    """Determine which stage a syllable belongs to"""
    parsed = parse_pinyin(syllable)
    initial = parsed.get('initial', '')
    final = parsed.get('final', '')
    
    if not initial and not final:
        return 99
    
    for stage_num, stage_config in STAGES.items():
        if initial in stage_config['initials']:
            if final in stage_config['finals']:
                return stage_num
        if not initial and final in stage_config['finals']:
            return stage_num
    
    if initial in ['j', 'q', 'x'] and final == 'u':
        return 5
    
    return 99

def reorganize_deck():
    """Reorganize deck with mixed elements and syllables"""
    print("=" * 80)
    print("Final Pinyin Deck Reorganization")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract both decks
        print("\n📦 Extracting decks...")
        with zipfile.ZipFile(SAMPLE_APKG, 'r') as z:
            z.extractall(tmpdir_path)
        
        db = tmpdir_path / "collection.anki21"
        if not db.exists():
            db = tmpdir_path / "collection.anki2"
        
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT models FROM col")
        models = json.loads(cursor.fetchone()[0])
        
        # Find models
        element_model_id = None
        element_model = None
        syllable_model_id = None
        syllable_model = None
        
        for mid_str, model in models.items():
            if model.get('name') == 'CUMA - Pinyin Element':
                element_model_id = int(mid_str)
                element_model = model
            elif model.get('name') == 'CUMA - Pinyin Syllable':
                syllable_model_id = int(mid_str)
                syllable_model = model
        
        if not element_model or not syllable_model:
            print("❌ Models not found")
            conn.close()
            return
        
        element_field_names = [f['name'] for f in element_model.get('flds', [])]
        syllable_field_names = [f['name'] for f in syllable_model.get('flds', [])]
        num_templates = len(syllable_model.get('tmpls', []))
        
        # Extract element notes from original deck
        print("\n📋 Extracting element notes from original deck...")
        original_elements = {}
        
        if ORIGINAL_APKG.exists():
            with tempfile.TemporaryDirectory() as orig_tmpdir:
                orig_tmpdir_path = Path(orig_tmpdir)
                with zipfile.ZipFile(ORIGINAL_APKG, 'r') as z:
                    z.extractall(orig_tmpdir_path)
                
                orig_db = orig_tmpdir_path / "collection.anki21"
                if not orig_db.exists():
                    orig_db = orig_tmpdir_path / "collection.anki2"
                
                orig_conn = sqlite3.connect(orig_db)
                orig_cursor = orig_conn.cursor()
                orig_cursor.execute("SELECT models FROM col")
                orig_models = json.loads(orig_cursor.fetchone()[0])
                
                for mid_str, model in orig_models.items():
                    if model.get('name') == 'CUMA - Pinyin Element':
                        orig_field_names = [f['name'] for f in model.get('flds', [])]
                        orig_cursor.execute("SELECT flds FROM notes WHERE mid = ?", (int(mid_str),))
                        for flds_tuple in orig_cursor.fetchall():
                            flds_str = flds_tuple[0]
                            fields = flds_str.split('\x1f')
                            while len(fields) < len(orig_field_names):
                                fields.append('')
                            field_dict = dict(zip(orig_field_names, fields))
                            element = field_dict.get('Element', '').strip()
                            if element:
                                # Convert tone numbers to tone marks
                                def convert_tone(tone_str):
                                    if not tone_str:
                                        return ''
                                    pinyin_no_tone, tone = extract_tone(tone_str)
                                    if tone:
                                        return add_tone_to_final(pinyin_no_tone, tone)
                                    return tone_str
                                
                                original_elements[element] = {
                                    'ExampleChar': field_dict.get('ExampleChar', ''),
                                    'Picture': field_dict.get('Picture', ''),
                                    'Tone1': convert_tone(field_dict.get('Tone1', '')),
                                    'Tone2': convert_tone(field_dict.get('Tone2', '')),
                                    'Tone3': convert_tone(field_dict.get('Tone3', '')),
                                    'Tone4': convert_tone(field_dict.get('Tone4', ''))
                                }
                        break
                
                orig_conn.close()
        
        print(f"   Found {len(original_elements)} elements in original deck")
        
        # Get current element notes and update with original data
        print("\n💾 Loading and updating element notes...")
        current_elements = {}
        cursor.execute("SELECT flds FROM notes WHERE mid = ?", (element_model_id,))
        for flds_str, in cursor.fetchall():
            fields = flds_str.split('\x1f')
            while len(fields) < len(element_field_names):
                fields.append('')
            field_dict = dict(zip(element_field_names, fields))
            element = field_dict.get('Element', '').strip()
            if element:
                # Update with original data if available
                if element in original_elements:
                    orig_data = original_elements[element]
                    field_dict['ExampleChar'] = orig_data.get('ExampleChar', field_dict.get('ExampleChar', ''))
                    field_dict['Picture'] = orig_data.get('Picture', field_dict.get('Picture', ''))
                    if orig_data.get('Tone1'):
                        field_dict['Tone1'] = orig_data['Tone1']
                    if orig_data.get('Tone2'):
                        field_dict['Tone2'] = orig_data['Tone2']
                    if orig_data.get('Tone3'):
                        field_dict['Tone3'] = orig_data['Tone3']
                    if orig_data.get('Tone4'):
                        field_dict['Tone4'] = orig_data['Tone4']
                
                current_elements[element] = {
                    'flds': '\x1f'.join([field_dict.get(name, '') for name in element_field_names]),
                    'element': element
                }
        
        print(f"   Loaded {len(current_elements)} element notes")
        
        # Get syllable notes
        print("\n💾 Loading syllable notes...")
        syllables = []
        cursor.execute("SELECT flds FROM notes WHERE mid = ?", (syllable_model_id,))
        for flds_str, in cursor.fetchall():
            fields = flds_str.split('\x1f')
            while len(fields) < len(syllable_field_names):
                fields.append('')
            field_dict = dict(zip(syllable_field_names, fields))
            syllable = field_dict.get('Syllable', '').strip()
            element = field_dict.get('ElementToLearn', '').strip()
            
            if syllable:
                parsed = parse_pinyin(syllable)
                initial = parsed.get('initial', '')
                final = parsed.get('final', '')
                
                syllables.append({
                    'flds': flds_str,
                    'syllable': syllable,
                    'element': element,
                    'initial': initial,
                    'final': final,
                    'stage': get_stage_for_syllable(syllable)
                })
        
        print(f"   Loaded {len(syllables)} syllable notes")
        
        # Organize: group syllables by stage and element
        print("\n🔄 Organizing notes by stage and element...")
        syllables_by_stage_element = defaultdict(lambda: defaultdict(list))
        for syl in syllables:
            stage = syl['stage']
            element = syl['element']
            syllables_by_stage_element[stage][element].append(syl)
        
        # Build final order: for each stage, interleave elements and their syllables
        all_notes_ordered = []
        
        for stage_num in [1, 2, 3, 4, 5, 99]:
            stage_config = STAGES.get(stage_num, {})
            stage_initials = stage_config.get('initials', [])
            stage_finals = stage_config.get('finals', [])
            
            # Get unique elements used in this stage's syllables
            elements_used = set()
            if stage_num in syllables_by_stage_element:
                for element in syllables_by_stage_element[stage_num].keys():
                    if element:
                        elements_used.add(element)
            
            # Build mixed element order (alternate finals and initials)
            element_order = []
            
            # Separate finals and initials that are used
            finals_used = [f for f in stage_finals if f in elements_used]
            initials_used = [i for i in stage_initials if i in elements_used]
            
            # Interleave: alternate between finals and initials
            max_len = max(len(finals_used), len(initials_used))
            for i in range(max_len):
                if i < len(finals_used):
                    element_order.append(finals_used[i])
                if i < len(initials_used):
                    element_order.append(initials_used[i])
            
            # Add remaining elements not in curriculum order
            for element in elements_used:
                if element not in element_order:
                    element_order.append(element)
            
            # For each element in order, add element note then its syllables
            for element in element_order:
                # Add element note if it exists
                if element in current_elements:
                    all_notes_ordered.append({
                        'type': 'element',
                        'element': element,
                        'stage': stage_num,
                        'flds': current_elements[element]['flds']
                    })
                
                # Add syllables using this element (immediately after element)
                if stage_num in syllables_by_stage_element and element in syllables_by_stage_element[stage_num]:
                    for syl in syllables_by_stage_element[stage_num][element]:
                        all_notes_ordered.append({
                            'type': 'syllable',
                            'syllable': syl['syllable'],
                            'element': syl['element'],
                            'stage': stage_num,
                            'flds': syl['flds']
                        })
        
        print(f"   Organized {len(all_notes_ordered)} notes")
        
        # Delete and recreate
        print("\n🗑️  Deleting existing notes and cards...")
        cursor.execute("DELETE FROM cards")
        cursor.execute("DELETE FROM notes")
        
        # Recreate in order
        print("\n➕ Recreating notes in final order...")
        new_time = int(time.time() * 1000)
        note_counter = 0
        
        for note_info in all_notes_ordered:
            new_note_id = new_time + note_counter
            
            if note_info['type'] == 'element':
                cursor.execute(
                    "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_note_id, f"guid{new_note_id}", element_model_id, new_time, -1, '', note_info['flds'],
                     note_info['element'], 0, 0, '')
                )
                
                card_id = new_time + note_counter * 1000
                cursor.execute(
                    "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (card_id, new_note_id, 1, 0, new_time, -1, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
                )
            else:
                fields = note_info['flds'].split('\x1f')
                while len(fields) < len(syllable_field_names):
                    fields.append('')
                field_dict = dict(zip(syllable_field_names, fields))
                
                cursor.execute(
                    "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_note_id, f"guid{new_note_id}", syllable_model_id, new_time, -1, '', note_info['flds'],
                     fields[syllable_field_names.index('WordHanzi')] if 'WordHanzi' in syllable_field_names else '', 0, 0, '')
                )
                
                for ord_val in range(num_templates):
                    card_id = new_time + note_counter * 1000 + ord_val
                    cursor.execute(
                        "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (card_id, new_note_id, 1, ord_val, new_time, -1, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
                    )
            
            note_counter += 1
            if note_counter % 50 == 0:
                print(f"   Progress: {note_counter} notes recreated...")
        
        conn.commit()
        print(f"\n✅ Recreated {note_counter} notes in final order")
        
        conn.close()
        
        # Repackage
        print("\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(SAMPLE_APKG, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print("✅ Deck reorganized with mixed elements and syllables!")

if __name__ == "__main__":
    reorganize_deck()


