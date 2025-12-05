#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1. Add b and d elements from missing_pinyin_elements.dat
2. Fix WordPinyin field format: convert from "ba2_luo2_bo" to "bá luó bo"
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
import time
import shutil
import re
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import extract_tone, add_tone_to_final

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
ELEMENTS_FILE = PROJECT_ROOT / "data" / "content_db" / "missing_pinyin_elements.dat"
JPGS_DIR = PROJECT_ROOT / "data" / "content_db" / "jpgs"

def convert_pinyin_with_tone_number(pinyin_str: str) -> str:
    """Convert pinyin with tone numbers to tone marks
    Examples:
        'ba2_luo2_bo' -> 'bá luó bo'
        'bà4_ba' -> 'bà ba'
        'bó1_luo' -> 'bó luo'
        'bà4 ba' -> 'bà ba'
    """
    if not pinyin_str:
        return ''
    
    # Split by underscore or space
    parts = re.split(r'[_\s]+', pinyin_str)
    converted_parts = []
    
    for part in parts:
        if not part:
            continue
        
        # Remove any trailing tone numbers if there are tone marks
        # e.g., "bà4" -> "bà"
        if re.search(r'[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]', part):
            # Has tone marks, remove trailing numbers
            part = re.sub(r'[1-5]$', '', part)
            converted_parts.append(part)
        else:
            # Convert tone number to tone mark
            converted = extract_tone(part)
            if converted[1]:  # Has tone
                pinyin_no_tone, tone = converted
                toned = add_tone_to_final(pinyin_no_tone, tone)
                converted_parts.append(toned)
            else:
                # No tone, use as is
                converted_parts.append(part)
    
    return ' '.join(converted_parts)

def add_bd_elements():
    """Add b and d elements"""
    print("=" * 80)
    print("Add b and d Elements")
    print("=" * 80)
    
    # Parse elements file for b and d
    elements_to_add = {}
    if ELEMENTS_FILE.exists():
        with open(ELEMENTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                parts = line.split(':', 1)
                if len(parts) == 2:
                    element = parts[0].strip()
                    image_file = parts[1].strip()
                    if element in ['b', 'd']:
                        elements_to_add[element] = image_file
    
    if not elements_to_add:
        print("⚠️  No b or d elements found in file")
        return
    
    print(f"\n📋 Elements to add: {list(elements_to_add.keys())}")
    
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
        
        # Find element model
        element_model_id = None
        element_model = None
        
        for mid_str, model in models.items():
            if model.get('name') == 'CUMA - Pinyin Element':
                element_model_id = int(mid_str)
                element_model = model
                break
        
        if not element_model:
            print("❌ Element model not found")
            conn.close()
            return
        
        field_names = [f['name'] for f in element_model.get('flds', [])]
        
        # Check existing elements
        cursor.execute("SELECT flds FROM notes WHERE mid = ?", (element_model_id,))
        existing_notes = cursor.fetchall()
        existing_elements = set()
        
        for flds_str, in existing_notes:
            fields = flds_str.split('\x1f')
            while len(fields) < len(field_names):
                fields.append('')
            field_dict = dict(zip(field_names, fields))
            element = field_dict.get('Element', '').strip()
            if element:
                existing_elements.add(element)
        
        print(f"\n📊 Existing elements: {sorted(existing_elements)}")
        
        # Add b and d
        current_time = int(time.time() * 1000)
        added_count = 0
        
        for element, image_file in elements_to_add.items():
            if element in existing_elements:
                print(f"   ⏭️  {element} already exists, checking if it has picture...")
                # Check if it has a picture
                cursor.execute("SELECT flds FROM notes WHERE mid = ?", (element_model_id,))
                for flds_str, in cursor.fetchall():
                    fields = flds_str.split('\x1f')
                    while len(fields) < len(field_names):
                        fields.append('')
                    field_dict = dict(zip(field_names, fields))
                    if field_dict.get('Element', '').strip() == element:
                        picture = field_dict.get('Picture', '')
                        if not picture or 'img' not in picture:
                            print(f"   ➕ {element} exists but has no picture, adding picture...")
                            # Update the note with picture
                            image_path = JPGS_DIR / image_file
                            if image_path.exists():
                                dest_image = tmpdir_path / image_path.name
                                shutil.copy2(image_path, dest_image)
                                field_dict['Picture'] = f'<img src="{image_path.name}">'
                                fields = [field_dict.get(name, '') for name in field_names]
                                flds_str = '\x1f'.join(fields)
                                cursor.execute(
                                    "UPDATE notes SET flds = ? WHERE mid = ? AND flds LIKE ?",
                                    (flds_str, element_model_id, f'%{element}%')
                                )
                                print(f"   ✅ Updated {element} with picture")
                        else:
                            print(f"   ✅ {element} already has picture")
                        break
                continue
            
            # Find image file
            image_path = find_image_file(image_file, JPGS_DIR)
            if not image_path:
                print(f"   ⚠️  Image not found for {element}: {image_file}")
                image_tag = ''
            else:
                dest_image = tmpdir_path / image_path.name
                shutil.copy2(image_path, dest_image)
                image_tag = f'<img src="{image_path.name}">'
                print(f"   ✅ Found image: {image_path.name}")
            
            # Build field values (initials don't have tones)
            field_values = {
                'Element': element,
                'ExampleChar': '',
                'Picture': image_tag,
                'Tone1': '',
                'Tone2': '',
                'Tone3': '',
                'Tone4': '',
                '_Remarks': f'Added from missing_pinyin_elements.dat',
                '_KG_Map': json.dumps({
                    "0": [{"kp": f"pinyin-element-{element}", "skill": "form_to_sound", "weight": 1.0}]
                })
            }
            
            fields = [field_values.get(name, '') for name in field_names]
            flds_str = '\x1f'.join(fields)
            
            note_id = current_time + added_count
            cursor.execute(
                "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (note_id, f"guid{note_id}", element_model_id, current_time, -1, '', flds_str, element, 0, 0, '')
            )
            
            card_id = current_time + added_count * 1000
            cursor.execute(
                "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (card_id, note_id, 1, 0, current_time, -1, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
            )
            
            added_count += 1
            print(f"   ✅ Added element: {element}")
        
        conn.commit()
        print(f"\n✅ Added/updated {added_count} elements")
        conn.close()
        
        # Fix WordPinyin fields
        print("\n🔧 Fixing WordPinyin fields...")
        fix_wordpinyin_fields(tmpdir_path, models)
        
        # Repackage
        print("\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(APKG_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print("✅ Deck updated!")

def find_image_file(image_name: str, jpgs_dir: Path) -> Path:
    """Find image file in jpgs directory"""
    image_path = jpgs_dir / image_name
    if image_path.exists():
        return image_path
    
    image_name_lower = image_name.lower()
    for ext in ['.jpg', '.jpeg', '.png', '.gif']:
        if image_name_lower.endswith(ext):
            base_name = image_name_lower[:-len(ext)]
            for file_path in jpgs_dir.glob(f"{base_name}*"):
                if file_path.suffix.lower() == ext:
                    return file_path
    
    for file_path in jpgs_dir.glob(f"*{image_name}*"):
        if file_path.is_file():
            return file_path
    
    return None

def fix_wordpinyin_fields(tmpdir_path: Path, models: dict):
    """Fix WordPinyin field format in all syllable notes"""
    db = tmpdir_path / "collection.anki21"
    if not db.exists():
        db = tmpdir_path / "collection.anki2"
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    
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
    word_pinyin_idx = field_names.index('WordPinyin') if 'WordPinyin' in field_names else -1
    
    if word_pinyin_idx < 0:
        print("❌ WordPinyin field not found")
        conn.close()
        return
    
    # Get all notes
    cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
    notes = cursor.fetchall()
    
    updated_count = 0
    for note_id, flds_str in notes:
        fields = flds_str.split('\x1f')
        while len(fields) < len(field_names):
            fields.append('')
        
        word_pinyin = fields[word_pinyin_idx]
        if word_pinyin:
            # Convert format
            converted = convert_pinyin_with_tone_number(word_pinyin)
            if converted != word_pinyin:
                fields[word_pinyin_idx] = converted
                new_flds = '\x1f'.join(fields)
                cursor.execute("UPDATE notes SET flds = ? WHERE id = ?", (new_flds, note_id))
                updated_count += 1
    
    conn.commit()
    print(f"   ✅ Fixed {updated_count} WordPinyin fields")
    conn.close()

if __name__ == "__main__":
    add_bd_elements()

