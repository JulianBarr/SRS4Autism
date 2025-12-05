#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete final reorganization:
1. Create ALL 59 curriculum elements (even without syllables)
2. Copy ExampleChar, Picture, Tone1-4 from original deck
3. Mix elements and syllables - element right before syllables using it
4. Mix initials and finals within each stage
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

def generate_tone_variations(element: str) -> list:
    """Generate all 4 tone variations for a final (empty for initials)"""
    if len(element) == 1 and element in 'bpmfdtnlgkhjqxzcsrzhchshyw':
        return ['', '', '', '']
    
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(element, tone)
        variations.append(toned)
    return variations

def reorganize_complete():
    """Complete reorganization with all elements"""
    print("=" * 80)
    print("Complete Pinyin Deck Reorganization")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
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
        
        # Build complete element list from curriculum
        print("\n📋 Building complete element list from curriculum...")
        all_curriculum_elements = []
        for stage_num, stage_config in STAGES.items():
            for initial in stage_config['initials']:
                all_curriculum_elements.append((initial, True, stage_num))  # (element, is_initial, stage)
            for final in stage_config['finals']:
                all_curriculum_elements.append((final, False, stage_num))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_elements = []
        for elem_info in all_curriculum_elements:
            element = elem_info[0]
            if element not in seen:
                seen.add(element)
                unique_elements.append(elem_info)
        
        print(f"   Curriculum has {len(unique_elements)} unique elements")
        
        # Create/update all element notes
        print("\n➕ Creating/updating all element notes...")
        current_elements = {}
        
        # First, get existing elements
        cursor.execute("SELECT flds FROM notes WHERE mid = ?", (element_model_id,))
        existing_elements = {}
        for flds_str, in cursor.fetchall():
            fields = flds_str.split('\x1f')
            while len(fields) < len(element_field_names):
                fields.append('')
            field_dict = dict(zip(element_field_names, fields))
            element = field_dict.get('Element', '').strip()
            if element:
                existing_elements[element] = field_dict
        
        # Create/update all curriculum elements
        for element, is_initial, stage_num in unique_elements:
            # Get original data if available
            orig_data = original_elements.get(element, {})
            
            # Generate tone variations
            tone_variations = generate_tone_variations(element)
            
            # Build field values
            field_values = {
                'Element': element,
                'ExampleChar': orig_data.get('ExampleChar', ''),
                'Picture': orig_data.get('Picture', ''),
                'Tone1': orig_data.get('Tone1', '') or tone_variations[0] if len(tone_variations) > 0 else '',
                'Tone2': orig_data.get('Tone2', '') or tone_variations[1] if len(tone_variations) > 1 else '',
                'Tone3': orig_data.get('Tone3', '') or tone_variations[2] if len(tone_variations) > 2 else '',
                'Tone4': orig_data.get('Tone4', '') or tone_variations[3] if len(tone_variations) > 3 else '',
                '_Remarks': existing_elements.get(element, {}).get('_Remarks', f'Teaching card for {STAGES[stage_num]["name"]} stage'),
                '_KG_Map': existing_elements.get(element, {}).get('_KG_Map', json.dumps({
                    "0": [{"kp": f"pinyin-element-{element}", "skill": "form_to_sound", "weight": 1.0}]
                }))
            }
            
            fields = [field_values.get(name, '') for name in element_field_names]
            current_elements[element] = {
                'flds': '\x1f'.join(fields),
                'element': element,
                'stage': stage_num,
                'is_initial': is_initial
            }
        
        print(f"   Prepared {len(current_elements)} element notes")
        
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
        
        # Build final order: for each stage, mix elements and their syllables
        all_notes_ordered = []
        
        for stage_num in [1, 2, 3, 4, 5, 99]:
            stage_config = STAGES.get(stage_num, {})
            stage_initials = stage_config.get('initials', [])
            stage_finals = stage_config.get('finals', [])
            
            # Get all curriculum elements for this stage
            stage_elements = []
            for element, is_initial, elem_stage in unique_elements:
                if elem_stage == stage_num:
                    stage_elements.append((element, is_initial))
            
            # Mix: alternate finals and initials
            finals = [(e, i) for e, i in stage_elements if not i]
            initials = [(e, i) for e, i in stage_elements if i]
            
            mixed_order = []
            max_len = max(len(finals), len(initials))
            for i in range(max_len):
                if i < len(finals):
                    mixed_order.append(finals[i][0])
                if i < len(initials):
                    mixed_order.append(initials[i][0])
            
            # For each element in mixed order, add element then its syllables
            for element in mixed_order:
                if element in current_elements:
                    # Add element note (always, even if no syllables)
                    all_notes_ordered.append({
                        'type': 'element',
                        'element': element,
                        'stage': stage_num,
                        'flds': current_elements[element]['flds']
                    })
                    
                    # Add syllables using this element (immediately after)
                    if stage_num in syllables_by_stage_element and element in syllables_by_stage_element[stage_num]:
                        for syl in syllables_by_stage_element[stage_num][element]:
                            all_notes_ordered.append({
                                'type': 'syllable',
                                'syllable': syl['syllable'],
                                'element': syl['element'],
                                'stage': stage_num,
                                'flds': syl['flds']
                            })
            
            # Handle stage 99 (unknown/advanced) - group by element
            if stage_num == 99:
                if stage_num in syllables_by_stage_element:
                    # Get unique elements used in stage 99 syllables
                    stage99_elements = set()
                    for element in syllables_by_stage_element[stage_num].keys():
                        if element:
                            stage99_elements.add(element)
                    
                    # Sort elements
                    sorted_stage99_elements = sorted(stage99_elements)
                    
                    # Add elements with their syllables
                    for element in sorted_stage99_elements:
                        # Add element if it exists
                        if element in current_elements:
                            all_notes_ordered.append({
                                'type': 'element',
                                'element': element,
                                'stage': stage_num,
                                'flds': current_elements[element]['flds']
                            })
                        
                        # Add syllables
                        for syl in syllables_by_stage_element[stage_num][element]:
                            all_notes_ordered.append({
                                'type': 'syllable',
                                'syllable': syl['syllable'],
                                'element': syl['element'],
                                'stage': stage_num,
                                'flds': syl['flds']
                            })
                    
                    # Add remaining syllables without elements
                    for element, syl_list in syllables_by_stage_element[stage_num].items():
                        if not element:
                            for syl in syl_list:
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
        
        print("✅ Deck completely reorganized!")

if __name__ == "__main__":
    reorganize_complete()

