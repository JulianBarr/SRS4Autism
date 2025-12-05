#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Restore syllable notes from original deck and reorganize with element notes
according to 5-stage curriculum.
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

def restore_and_reorganize():
    """Restore syllables and reorganize everything"""
    print("=" * 80)
    print("Restore and Reorganize Pinyin Deck")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract sample deck
        print("\n📦 Extracting sample .apkg...")
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
        
        # Save existing element notes
        print("\n💾 Saving existing element notes...")
        saved_elements = {}
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (element_model_id,))
        for note_id, flds_str in cursor.fetchall():
            saved_elements[note_id] = flds_str
        print(f"   Saved {len(saved_elements)} element notes")
        
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
                        orig_cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (int(mid_str),))
                        for note_id, flds_str in orig_cursor.fetchall():
                            original_syllables.append((note_id, flds_str, orig_field_names))
                        break
                
                orig_conn.close()
        
        print(f"   Extracted {len(original_syllables)} syllable notes")
        
        # Process syllable notes - convert tones and add missing fields
        print("\n🔧 Processing syllable notes...")
        processed_syllables = []
        
        for note_id, flds_str, orig_field_names in original_syllables:
            fields = flds_str.split('\x1f')
            while len(fields) < len(orig_field_names):
                fields.append('')
            
            # Convert to new field structure
            field_dict = dict(zip(orig_field_names, fields))
            
            # Convert syllable tone
            syllable = field_dict.get('Syllable', '').strip()
            if syllable:
                # Convert tone number to tone mark
                pinyin_no_tone, tone = extract_tone(syllable)
                if tone:
                    syllable = add_tone_to_final(pinyin_no_tone, tone)
            
            # Convert WordPinyin
            word_pinyin = field_dict.get('WordPinyin', '').strip()
            if word_pinyin:
                # Convert format
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
            processed_syllables.append(('\x1f'.join(fields), syllable))
        
        print(f"   Processed {len(processed_syllables)} syllables")
        
        # Build all notes with stages
        print("\n🔄 Building note list with stages...")
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
                    'type': 'element',
                    'flds': flds_str,
                    'element': element,
                    'stage': stage,
                    'is_initial': is_initial,
                    'sort_key': (stage, 0 if is_initial else 1, element)
                })
        
        # Syllable notes
        for flds_str, syllable in processed_syllables:
            fields = flds_str.split('\x1f')
            while len(fields) < len(syllable_field_names):
                fields.append('')
            field_dict = dict(zip(syllable_field_names, fields))
            
            stage = get_stage_for_syllable(syllable)
            parsed = parse_pinyin(syllable)
            initial = parsed.get('initial', '')
            final = parsed.get('final', '')
            pinyin_no_tone, _ = extract_tone(syllable)
            
            stage_config = STAGES.get(stage, {})
            initial_order = stage_config.get('initials', []).index(initial) if initial in stage_config.get('initials', []) else 999
            final_order = stage_config.get('finals', []).index(final) if final in stage_config.get('finals', []) else 999
            
            all_notes_with_stage.append({
                'type': 'syllable',
                'flds': flds_str,
                'syllable': syllable,
                'stage': stage,
                'sort_key': (stage, 2, initial_order, final_order, pinyin_no_tone)
            })
        
        # Sort all notes
        all_notes_with_stage.sort(key=lambda x: x['sort_key'])
        
        print(f"   Total notes: {len(all_notes_with_stage)}")
        print(f"   Elements: {sum(1 for n in all_notes_with_stage if n['type'] == 'element')}")
        print(f"   Syllables: {sum(1 for n in all_notes_with_stage if n['type'] == 'syllable')}")
        
        # Delete all existing notes and cards
        print(f"\n🗑️  Deleting existing notes and cards...")
        cursor.execute("DELETE FROM cards")
        cursor.execute("DELETE FROM notes")
        
        # Recreate in order
        print(f"\n➕ Recreating notes in curriculum order...")
        new_time = int(time.time() * 1000)
        note_counter = 0
        
        for note_info in all_notes_with_stage:
            new_note_id = new_time + note_counter
            
            if note_info['type'] == 'element':
                fields = note_info['flds'].split('\x1f')
                while len(fields) < len(element_field_names):
                    fields.append('')
                field_dict = dict(zip(element_field_names, fields))
                
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
        print(f"\n✅ Recreated {note_counter} notes in curriculum order")
        
        conn.close()
        
        # Repackage
        print("\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(SAMPLE_APKG, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print("✅ Deck restored and reorganized!")

if __name__ == "__main__":
    restore_and_reorganize()

