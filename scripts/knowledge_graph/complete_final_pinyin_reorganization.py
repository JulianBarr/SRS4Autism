#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete final reorganization - clean slate approach:
1. Delete all notes
2. Create ALL 59 curriculum elements with data from original deck
3. Restore all 271 syllables from original deck
4. Mix elements and syllables - element right before syllables using it
5. Mix initials and finals within each stage
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
    """Complete reorganization from scratch"""
    print("=" * 80)
    print("Complete Final Pinyin Deck Reorganization")
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
        print("\n📋 Extracting element data from original deck...")
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
        
        # Extract syllable notes from original deck
        print("\n📋 Extracting syllable notes from original deck...")
        original_syllables = []
        
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
                    if model.get('name') == 'CUMA - Pinyin Syllable':
                        orig_field_names = [f['name'] for f in model.get('flds', [])]
                        orig_cursor.execute("SELECT flds FROM notes WHERE mid = ?", (int(mid_str),))
                        for flds_tuple in orig_cursor.fetchall():
                            flds_str = flds_tuple[0]
                            fields = flds_str.split('\x1f')
                            while len(fields) < len(orig_field_names):
                                fields.append('')
                            field_dict = dict(zip(orig_field_names, fields))
                            original_syllables.append((field_dict, orig_field_names))
                        break
                
                orig_conn.close()
        
        print(f"   Found {len(original_syllables)} syllables in original deck")
        
        # Build all 59 curriculum elements
        print("\n📋 Building all 59 curriculum elements...")
        all_curriculum_elements = []
        for stage_num, stage_config in STAGES.items():
            for initial in stage_config['initials']:
                all_curriculum_elements.append((initial, True, stage_num))
            for final in stage_config['finals']:
                all_curriculum_elements.append((final, False, stage_num))
        
        # Remove duplicates
        seen = set()
        unique_elements = []
        for elem_info in all_curriculum_elements:
            element = elem_info[0]
            if element not in seen:
                seen.add(element)
                unique_elements.append(elem_info)
        
        print(f"   Created {len(unique_elements)} unique curriculum elements")
        
        # Process syllables - convert tones and add missing fields
        print("\n🔧 Processing syllable notes...")
        processed_syllables = []
        
        for field_dict, orig_field_names in original_syllables:
            # Convert syllable tone
            syllable = field_dict.get('Syllable', '').strip()
            if syllable:
                pinyin_no_tone, tone = extract_tone(syllable)
                if tone:
                    syllable = add_tone_to_final(pinyin_no_tone, tone)
            
            # Convert WordPinyin
            word_pinyin = field_dict.get('WordPinyin', '').strip()
            if word_pinyin:
                parts = word_pinyin.replace('_', ' ').split()
                converted_parts = []
                for part in parts:
                    pinyin_no_tone, tone = extract_tone(part)
                    if tone:
                        toned = add_tone_to_final(pinyin_no_tone, tone)
                        converted_parts.append(toned)
                    else:
                        converted_parts.append(part)
                word_pinyin = ' '.join(converted_parts)
            
            # Generate tone variations
            pinyin_no_tone, _ = extract_tone(syllable)
            tone_variations = []
            for tone in [1, 2, 3, 4]:
                toned = add_tone_to_final(pinyin_no_tone, tone)
                tone_variations.append(toned)
            
            # Generate confusors
            confusors = []
            if pinyin_no_tone:
                base_initial = pinyin_no_tone[0] if pinyin_no_tone else ''
                base_final = pinyin_no_tone[1:] if len(pinyin_no_tone) > 1 else pinyin_no_tone
                confusors = [
                    add_tone_to_final('b' + base_final if base_final else 'ba', 1),
                    add_tone_to_final('p' + base_final if base_final else 'pa', 2),
                    add_tone_to_final(pinyin_no_tone, 3 if syllable != add_tone_to_final(pinyin_no_tone, 3) else 4)
                ]
            
            # Build new field values
            new_field_dict = {
                'ElementToLearn': field_dict.get('ElementToLearn', ''),
                'Syllable': syllable,
                'WordPinyin': word_pinyin,
                'WordHanzi': field_dict.get('WordHanzi', ''),
                'WordPicture': field_dict.get('WordPicture', ''),
                'WordAudio': field_dict.get('WordAudio', ''),
                '_Remarks': field_dict.get('_Remarks', ''),
                '_KG_Map': field_dict.get('_KG_Map', ''),
                'Tone1': tone_variations[0] if len(tone_variations) > 0 else '',
                'Tone2': tone_variations[1] if len(tone_variations) > 1 else '',
                'Tone3': tone_variations[2] if len(tone_variations) > 2 else '',
                'Tone4': tone_variations[3] if len(tone_variations) > 3 else '',
                'Confusor1': confusors[0] if len(confusors) > 0 else '',
                'ConfusorPicture1': '',
                'Confusor2': confusors[1] if len(confusors) > 1 else '',
                'ConfusorPicture2': '',
                'Confusor3': confusors[2] if len(confusors) > 2 else '',
                'ConfusorPicture3': ''
            }
            
            fields = [new_field_dict.get(name, '') for name in syllable_field_names]
            processed_syllables.append({
                'flds': '\x1f'.join(fields),
                'syllable': syllable,
                'element': new_field_dict.get('ElementToLearn', ''),
                'stage': get_stage_for_syllable(syllable)
            })
        
        print(f"   Processed {len(processed_syllables)} syllables")
        
        # Delete all existing notes
        print("\n🗑️  Deleting all existing notes...")
        cursor.execute("DELETE FROM cards")
        cursor.execute("DELETE FROM notes")
        
        # Organize: group syllables by stage and element
        print("\n🔄 Organizing notes...")
        syllables_by_stage_element = defaultdict(lambda: defaultdict(list))
        for syl in processed_syllables:
            stage = syl['stage']
            element = syl['element']
            syllables_by_stage_element[stage][element].append(syl)
        
        # Build final order
        all_notes_ordered = []
        
        for stage_num in [1, 2, 3, 4, 5, 99]:
            stage_config = STAGES.get(stage_num, {})
            
            # Get curriculum elements for this stage
            stage_elements = []
            for element, is_initial, elem_stage in unique_elements:
                if elem_stage == stage_num:
                    stage_elements.append((element, is_initial))
            
            # Mix: alternate finals and initials
            finals = [e for e, i in stage_elements if not i]
            initials = [e for e, i in stage_elements if i]
            
            mixed_order = []
            max_len = max(len(finals), len(initials))
            for i in range(max_len):
                if i < len(finals):
                    mixed_order.append(finals[i])
                if i < len(initials):
                    mixed_order.append(initials[i])
            
            # For each element, add element note then its syllables
            for element in mixed_order:
                # Build element note
                orig_data = original_elements.get(element, {})
                tone_variations = generate_tone_variations(element)
                
                field_values = {
                    'Element': element,
                    'ExampleChar': orig_data.get('ExampleChar', ''),
                    'Picture': orig_data.get('Picture', ''),
                    'Tone1': orig_data.get('Tone1', '') or (tone_variations[0] if len(tone_variations) > 0 else ''),
                    'Tone2': orig_data.get('Tone2', '') or (tone_variations[1] if len(tone_variations) > 1 else ''),
                    'Tone3': orig_data.get('Tone3', '') or (tone_variations[2] if len(tone_variations) > 2 else ''),
                    'Tone4': orig_data.get('Tone4', '') or (tone_variations[3] if len(tone_variations) > 3 else ''),
                    '_Remarks': f'Teaching card for {STAGES[stage_num]["name"]} stage',
                    '_KG_Map': json.dumps({
                        "0": [{"kp": f"pinyin-element-{element}", "skill": "form_to_sound", "weight": 1.0}]
                    })
                }
                
                element_flds = '\x1f'.join([field_values.get(name, '') for name in element_field_names])
                
                # Add element note
                all_notes_ordered.append({
                    'type': 'element',
                    'element': element,
                    'stage': stage_num,
                    'flds': element_flds
                })
                
                # Add syllables using this element
                if stage_num in syllables_by_stage_element and element in syllables_by_stage_element[stage_num]:
                    for syl in syllables_by_stage_element[stage_num][element]:
                        all_notes_ordered.append({
                            'type': 'syllable',
                            'syllable': syl['syllable'],
                            'element': syl['element'],
                            'stage': stage_num,
                            'flds': syl['flds']
                        })
            
            # Handle stage 99 - group by element
            if stage_num == 99:
                if stage_num in syllables_by_stage_element:
                    stage99_elements = sorted(set(syllables_by_stage_element[stage_num].keys()))
                    for element in stage99_elements:
                        if element and element in unique_elements:
                            # Create element note
                            elem_info = next((e for e in unique_elements if e[0] == element), None)
                            if elem_info:
                                _, _, elem_stage = elem_info
                                orig_data = original_elements.get(element, {})
                                tone_variations = generate_tone_variations(element)
                                
                                field_values = {
                                    'Element': element,
                                    'ExampleChar': orig_data.get('ExampleChar', ''),
                                    'Picture': orig_data.get('Picture', ''),
                                    'Tone1': orig_data.get('Tone1', '') or (tone_variations[0] if len(tone_variations) > 0 else ''),
                                    'Tone2': orig_data.get('Tone2', '') or (tone_variations[1] if len(tone_variations) > 1 else ''),
                                    'Tone3': orig_data.get('Tone3', '') or (tone_variations[2] if len(tone_variations) > 2 else ''),
                                    'Tone4': orig_data.get('Tone4', '') or (tone_variations[3] if len(tone_variations) > 3 else ''),
                                    '_Remarks': f'Teaching card',
                                    '_KG_Map': json.dumps({
                                        "0": [{"kp": f"pinyin-element-{element}", "skill": "form_to_sound", "weight": 1.0}]
                                    })
                                }
                                
                                element_flds = '\x1f'.join([field_values.get(name, '') for name in element_field_names])
                                
                                all_notes_ordered.append({
                                    'type': 'element',
                                    'element': element,
                                    'stage': stage_num,
                                    'flds': element_flds
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
        
        print(f"   Organized {len(all_notes_ordered)} notes")
        
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


