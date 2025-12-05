#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create complete pinyin element notes (initials and finals) according to 5-stage curriculum.
Insert them in the correct positions before syllables that use them.
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

def get_element_stage(element: str, is_initial: bool) -> int:
    """Get stage for an element"""
    for stage_num, stage_config in STAGES.items():
        if is_initial:
            if element in stage_config['initials']:
                return stage_num
        else:
            if element in stage_config['finals']:
                return stage_num
    return 99

def generate_tone_variations(element: str) -> list:
    """Generate all 4 tone variations for a final (empty for initials)"""
    # Initials don't have tones
    if len(element) == 1 and element in 'bpmfdtnlgkhjqxzcsrzhchshyw':
        return ['', '', '', '']
    
    # For finals, generate tones
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(element, tone)
        variations.append(toned)
    return variations

def create_complete_elements():
    """Create all element notes and insert them in correct positions"""
    print("=" * 80)
    print("Create Complete Pinyin Element Notes")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
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
        
        # Get existing elements
        cursor.execute("SELECT flds FROM notes WHERE mid = ?", (element_model_id,))
        existing_elements = set()
        for flds_str, in cursor.fetchall():
            fields = flds_str.split('\x1f')
            while len(fields) < len(element_field_names):
                fields.append('')
            field_dict = dict(zip(element_field_names, fields))
            element = field_dict.get('Element', '').strip()
            if element:
                existing_elements.add(element)
        
        print(f"\n📊 Existing elements: {len(existing_elements)}")
        print(f"   {sorted(existing_elements)}")
        
        # Collect all elements needed from curriculum
        all_elements = []
        for stage_num, stage_config in STAGES.items():
            # Add initials
            for initial in stage_config['initials']:
                all_elements.append({
                    'element': initial,
                    'is_initial': True,
                    'stage': stage_num
                })
            # Add finals
            for final in stage_config['finals']:
                all_elements.append({
                    'element': final,
                    'is_initial': False,
                    'stage': stage_num
                })
        
        # Remove duplicates while preserving order
        seen = set()
        unique_elements = []
        for elem in all_elements:
            key = elem['element']
            if key not in seen:
                seen.add(key)
                unique_elements.append(elem)
        
        print(f"\n📋 Curriculum elements needed: {len(unique_elements)}")
        
        # Create missing element notes
        current_time = int(time.time() * 1000)
        created_count = 0
        
        print(f"\n➕ Creating missing element notes...")
        for elem_info in unique_elements:
            element = elem_info['element']
            is_initial = elem_info['is_initial']
            stage = elem_info['stage']
            
            if element in existing_elements:
                print(f"   ⏭️  {element} already exists")
                continue
            
            # Generate tone variations
            tone_variations = generate_tone_variations(element)
            
            # Build field values
            field_values = {
                'Element': element,
                'ExampleChar': '',  # Can be filled later
                'Picture': '',  # Can be filled later if images available
                'Tone1': tone_variations[0] if len(tone_variations) > 0 else '',
                'Tone2': tone_variations[1] if len(tone_variations) > 1 else '',
                'Tone3': tone_variations[2] if len(tone_variations) > 2 else '',
                'Tone4': tone_variations[3] if len(tone_variations) > 3 else '',
                '_Remarks': f'Teaching card for {STAGES[stage]["name"]} stage',
                '_KG_Map': json.dumps({
                    "0": [{"kp": f"pinyin-element-{element}", "skill": "form_to_sound", "weight": 1.0}]
                })
            }
            
            fields = [field_values.get(name, '') for name in element_field_names]
            flds_str = '\x1f'.join(fields)
            
            note_id = current_time + created_count
            cursor.execute(
                "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (note_id, f"guid{note_id}", element_model_id, current_time, -1, '', flds_str, element, 0, 0, '')
            )
            
            # Create card (element notes have 1 card)
            card_id = current_time + created_count * 1000
            cursor.execute(
                "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (card_id, note_id, 1, 0, current_time, -1, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
            )
            
            created_count += 1
            print(f"   ✅ Created: {element} ({'initial' if is_initial else 'final'}, stage {stage})")
        
        conn.commit()
        print(f"\n✅ Created {created_count} new element notes")
        
        # Save note data BEFORE reorganizing
        print("\n💾 Saving note data before reorganization...")
        saved_elements = {}
        saved_syllables = {}
        
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (element_model_id,))
        for note_id, flds_str in cursor.fetchall():
            saved_elements[note_id] = flds_str
        
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
        for note_id, flds_str in cursor.fetchall():
            saved_syllables[note_id] = flds_str
        
        # Now reorganize: insert elements before syllables that use them
        print(f"\n🔄 Reorganizing deck to insert elements in correct positions...")
        
        # Get all notes (elements and syllables) with their stages
        all_notes_with_stage = []
        
        # Element notes
        for note_id, flds_str in saved_elements.items():
            fields = flds_str.split('\x1f')
            while len(fields) < len(element_field_names):
                fields.append('')
            field_dict = dict(zip(element_field_names, fields))
            element = field_dict.get('Element', '').strip()
            if element:
                is_initial = len(element) <= 2 and element in 'bpmfdtnlgkhjqxzcsrzhchshyw'
                stage = get_element_stage(element, is_initial)
                all_notes_with_stage.append({
                    'id': note_id,
                    'type': 'element',
                    'element': element,
                    'stage': stage,
                    'is_initial': is_initial,
                    'sort_key': (stage, 0 if is_initial else 1, element)  # Elements before syllables in same stage
                })
        
        # Syllable notes
        for note_id, flds_str in saved_syllables.items():
            fields = flds_str.split('\x1f')
            while len(fields) < len(syllable_field_names):
                fields.append('')
            field_dict = dict(zip(syllable_field_names, fields))
            syllable = field_dict.get('Syllable', '').strip()
            if syllable:
                stage = get_stage_for_syllable(syllable)
                parsed = parse_pinyin(syllable)
                initial = parsed.get('initial', '')
                final = parsed.get('final', '')
                pinyin_no_tone, _ = extract_tone(syllable)
                
                # Sort key: stage, then initial order, then final order
                stage_config = STAGES.get(stage, {})
                initial_order = stage_config.get('initials', []).index(initial) if initial in stage_config.get('initials', []) else 999
                final_order = stage_config.get('finals', []).index(final) if final in stage_config.get('finals', []) else 999
                
                all_notes_with_stage.append({
                    'id': note_id,
                    'type': 'syllable',
                    'syllable': syllable,
                    'stage': stage,
                    'initial': initial,
                    'final': final,
                    'sort_key': (stage, 2, initial_order, final_order, pinyin_no_tone)  # Syllables after elements
                })
        
        # Sort all notes
        all_notes_with_stage.sort(key=lambda x: x['sort_key'])
        
        print(f"   Total notes to reorganize: {len(all_notes_with_stage)}")
        print(f"   Elements: {sum(1 for n in all_notes_with_stage if n['type'] == 'element')}")
        print(f"   Syllables: {sum(1 for n in all_notes_with_stage if n['type'] == 'syllable')}")
        
        # Delete all existing notes and cards
        print(f"\n🗑️  Deleting existing notes and cards...")
        cursor.execute("DELETE FROM cards")
        cursor.execute("DELETE FROM notes")
        
        # Recreate notes in order
        print(f"\n➕ Recreating notes in curriculum order...")
        new_time = int(time.time() * 1000)
        note_counter = 0
        
        # Recreate in order
        for note_info in all_notes_with_stage:
            note_id = note_info['id']
            new_note_id = new_time + note_counter
            
            if note_info['type'] == 'element':
                flds_str = saved_elements.get(note_id, '')
                if not flds_str:
                    continue
                
                cursor.execute(
                    "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_note_id, f"guid{new_note_id}", element_model_id, new_time, -1, '', flds_str, 
                     note_info['element'], 0, 0, '')
                )
                
                card_id = new_time + note_counter * 1000
                cursor.execute(
                    "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (card_id, new_note_id, 1, 0, new_time, -1, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
                )
            else:
                flds_str = saved_syllables.get(note_id, '')
                if not flds_str:
                    continue
                
                fields = flds_str.split('\x1f')
                while len(fields) < len(syllable_field_names):
                    fields.append('')
                field_dict = dict(zip(syllable_field_names, fields))
                
                cursor.execute(
                    "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_note_id, f"guid{new_note_id}", syllable_model_id, new_time, -1, '', flds_str,
                     fields[syllable_field_names.index('WordHanzi')] if 'WordHanzi' in syllable_field_names else '', 0, 0, '')
                )
                
                # Create cards for each template
                num_templates = len(syllable_model.get('tmpls', []))
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
        print(f"\n✅ Recreated {note_counter} notes in curriculum order")
        
        conn.close()
        
        # Repackage
        print("\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(APKG_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print("✅ Deck updated with complete element notes in correct positions!")

if __name__ == "__main__":
    create_complete_elements()

