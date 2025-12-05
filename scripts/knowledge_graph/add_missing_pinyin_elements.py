#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add missing pinyin elements to the deck using missing_pinyin_elements.dat
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
import time
import shutil
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import extract_tone, add_tone_to_final

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
ELEMENTS_FILE = PROJECT_ROOT / "data" / "content_db" / "missing_pinyin_elements.dat"
JPGS_DIR = PROJECT_ROOT / "data" / "content_db" / "jpgs"

def parse_elements_file(elements_file: Path) -> dict:
    """Parse missing_pinyin_elements.dat file
    Supports multiple formats:
    1. New format: element, proper_name, ExampleChar, picture_file
       Example: k, ke, 渴, thirsty.png
    2. Mixed format: element: proper_name, ExampleChar, picture_file
       Example: ang: ang, 昂, ang2.png
    3. Old format: element: picture_file
       Example: m: touch.jpeg
    """
    elements = {}
    if not elements_file.exists():
        print(f"❌ Elements file not found: {elements_file}")
        return elements
    
    with open(elements_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            # Handle mixed format: element: proper_name, ExampleChar, picture_file
            if ':' in line and ',' in line:
                # Split by colon first
                colon_parts = line.split(':', 1)
                if len(colon_parts) == 2:
                    element = colon_parts[0].strip()
                    rest = colon_parts[1].strip()
                    # Split the rest by comma
                    comma_parts = [p.strip() for p in rest.split(',')]
                    if len(comma_parts) >= 3:
                        proper_name = comma_parts[0]
                        example_char = comma_parts[1]
                        picture_file = comma_parts[2]
                        elements[element] = {
                            'proper_name': proper_name,
                            'example_char': example_char,
                            'picture_file': picture_file
                        }
                        continue
            
            # Try comma-separated format (new format)
            if ',' in line:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 4:
                    element = parts[0]
                    proper_name = parts[1]
                    example_char = parts[2]
                    picture_file = parts[3]
                    elements[element] = {
                        'proper_name': proper_name,
                        'example_char': example_char,
                        'picture_file': picture_file
                    }
                elif len(parts) >= 2:
                    # Fallback: element, picture_file (old format)
                    element = parts[0]
                    picture_file = parts[1]
                    elements[element] = {
                        'proper_name': element,  # Use element as proper_name if not provided
                        'example_char': '',
                        'picture_file': picture_file
                    }
            # Try colon-separated format (old format)
            elif ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    element = parts[0].strip()
                    image_file = parts[1].strip()
                    elements[element] = {
                        'proper_name': element,
                        'example_char': '',
                        'picture_file': image_file
                    }
            else:
                print(f"   ⚠️  Skipping line {line_num}: invalid format: {line}")
    
    return elements

def find_image_file(image_name: str, jpgs_dir: Path) -> Path:
    """Find image file in jpgs directory"""
    # Try exact match first
    image_path = jpgs_dir / image_name
    if image_path.exists():
        return image_path
    
    # Try case-insensitive search
    image_name_lower = image_name.lower()
    for ext in ['.jpg', '.jpeg', '.png', '.gif']:
        if image_name_lower.endswith(ext):
            base_name = image_name_lower[:-len(ext)]
            for file_path in jpgs_dir.glob(f"{base_name}*"):
                if file_path.suffix.lower() == ext:
                    return file_path
    
    # Try any file with similar name
    for file_path in jpgs_dir.glob(f"*{image_name}*"):
        if file_path.is_file():
            return file_path
    
    return None

def generate_tone_variations(proper_name: str) -> list:
    """Generate all 4 tone variations using the proper name
    Args:
        proper_name: The proper pinyin name (e.g., 'ke' for element 'k')
    Returns:
        List of 4 tone variations: [kē, ké, kě, kè] or ['', '', '', ''] for initials
    """
    # For initials (single character), return empty tones
    if len(proper_name) == 1 and proper_name in 'bpmfdtnlgkhjqxzcsrzhchshyw':
        return ['', '', '', '']
    
    # For finals, generate tones using the proper name
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(proper_name, tone)
        variations.append(toned)
    return variations

def add_elements_to_deck(elements: dict):
    """Add missing elements to the pinyin deck"""
    print("=" * 80)
    print("Add Missing Pinyin Elements")
    print("=" * 80)
    
    if not elements:
        print("⚠️  No elements to add")
        return
    
    print(f"\n📋 Found {len(elements)} elements to add:")
    for element, data in elements.items():
        if isinstance(data, dict):
            print(f"   {element}: {data.get('proper_name', element)} - {data.get('example_char', '')} - {data.get('picture_file', '')}")
        else:
            # Old format compatibility
            print(f"   {element}: {data}")
    
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
            print("   Available models:")
            for mid_str, model in models.items():
                print(f"      {model.get('name')}")
            conn.close()
            return
        
        field_names = [f['name'] for f in element_model.get('flds', [])]
        print(f"\n✅ Found element model with fields: {field_names}")
        
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
        
        print(f"\n📊 Existing elements: {len(existing_elements)}")
        
        # Add new elements
        print(f"\n➕ Adding new elements...")
        current_time = int(time.time() * 1000)
        added_count = 0
        copied_images = []
        
        for element, data in elements.items():
            # Handle both old format (string) and new format (dict)
            if isinstance(data, dict):
                proper_name = data.get('proper_name', element)
                example_char = data.get('example_char', '')
                picture_file = data.get('picture_file', '')
            else:
                # Old format compatibility
                proper_name = element
                example_char = ''
                picture_file = data
            
            # Check if element exists and update if needed
            if element in existing_elements:
                print(f"   🔄 Updating existing element: {element}")
                # Find the note and update it
                cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (element_model_id,))
                for note_id, flds_str in cursor.fetchall():
                    fields = flds_str.split('\x1f')
                    while len(fields) < len(field_names):
                        fields.append('')
                    field_dict = dict(zip(field_names, fields))
                    if field_dict.get('Element', '').strip() == element:
                        # Update fields if they're empty or if we have new data
                        updated = False
                        
                        # Update ExampleChar if empty or if we have new data
                        if example_char and (not field_dict.get('ExampleChar', '').strip() or example_char != field_dict.get('ExampleChar', '').strip()):
                            field_dict['ExampleChar'] = example_char
                            updated = True
                        
                        # Update Picture if empty or if we have new data
                        if picture_file:
                            image_path = find_image_file(picture_file, JPGS_DIR)
                            if image_path:
                                dest_image = tmpdir_path / image_path.name
                                if not dest_image.exists():
                                    shutil.copy2(image_path, dest_image)
                                    copied_images.append(image_path.name)
                                new_image_tag = f'<img src="{image_path.name}">'
                                if not field_dict.get('Picture', '').strip() or new_image_tag != field_dict.get('Picture', '').strip():
                                    field_dict['Picture'] = new_image_tag
                                    updated = True
                        
                        # Update Tone1-4 if empty (using proper_name)
                        if proper_name != element:
                            tone_variations = generate_tone_variations(proper_name)
                            for i, tone_field in enumerate(['Tone1', 'Tone2', 'Tone3', 'Tone4'], 0):
                                if i < len(tone_variations) and tone_variations[i]:
                                    if not field_dict.get(tone_field, '').strip() or tone_variations[i] != field_dict.get(tone_field, '').strip():
                                        field_dict[tone_field] = tone_variations[i]
                                        updated = True
                        
                        if updated:
                            fields = [field_dict.get(name, '') for name in field_names]
                            flds_str = '\x1f'.join(fields)
                            cursor.execute("UPDATE notes SET flds = ? WHERE id = ?", (flds_str, note_id))
                            print(f"      ✅ Updated {element} with new data")
                        else:
                            print(f"      ℹ️  {element} already has all data")
                        break
                continue
            
            # Find image file (for new elements)
            image_path = find_image_file(picture_file, JPGS_DIR)
            if not image_path:
                print(f"   ⚠️  Image not found for {element}: {picture_file}")
                # Continue without image
                image_tag = ''
            else:
                # Copy image to media folder
                dest_image = tmpdir_path / image_path.name
                shutil.copy2(image_path, dest_image)
                copied_images.append(image_path.name)
                image_tag = f'<img src="{image_path.name}">'
                print(f"   ✅ Found image: {image_path.name}")
            
            # Generate tone variations using proper_name
            tone_variations = generate_tone_variations(proper_name)
            
            # Build field values
            field_values = {
                'Element': element,
                'ExampleChar': example_char,
                'Picture': image_tag,
                'Tone1': tone_variations[0] if len(tone_variations) > 0 else '',
                'Tone2': tone_variations[1] if len(tone_variations) > 1 else '',
                'Tone3': tone_variations[2] if len(tone_variations) > 2 else '',
                'Tone4': tone_variations[3] if len(tone_variations) > 3 else '',
                '_Remarks': f'Added from missing_pinyin_elements.dat',
                '_KG_Map': json.dumps({
                    "0": [{"kp": f"pinyin-element-{element}", "skill": "form_to_sound", "weight": 1.0}]
                })
            }
            
            # Create fields list
            fields = [field_values.get(name, '') for name in field_names]
            flds_str = '\x1f'.join(fields)
            
            # Create note
            note_id = current_time + added_count
            cursor.execute(
                "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (note_id, f"guid{note_id}", element_model_id, current_time, -1, '', flds_str, element, 0, 0, '')
            )
            
            # Create card (element notes have 1 card)
            card_id = current_time + added_count * 1000
            cursor.execute(
                "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (card_id, note_id, 1, 0, current_time, -1, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
            )
            
            added_count += 1
            print(f"   ✅ Added element: {element}")
        
        conn.commit()
        print(f"\n✅ Added {added_count} new elements")
        print(f"✅ Updated {len([e for e in elements.keys() if e in existing_elements])} existing elements")
        print(f"   Copied {len(copied_images)} images")
        
        conn.close()
        
        # Repackage .apkg
        print("\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(APKG_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print("✅ Deck updated with missing elements!")

def main():
    try:
        # Parse elements file
        print("=" * 80)
        print("Add Missing Pinyin Elements")
        print("=" * 80)
        print(f"\n📂 Elements file: {ELEMENTS_FILE}")
        print(f"   Exists: {ELEMENTS_FILE.exists()}")
        
        elements = parse_elements_file(ELEMENTS_FILE)
        
        if not elements:
            print("❌ No elements found in file")
            return
        
        print(f"\n✅ Parsed {len(elements)} elements from file")
        
        # Check jpgs directory
        print(f"\n📂 JPGs directory: {JPGS_DIR}")
        print(f"   Exists: {JPGS_DIR.exists()}")
        if not JPGS_DIR.exists():
            print(f"❌ JPGs directory not found: {JPGS_DIR}")
            return
        
        # Check APKG file
        print(f"\n📂 APKG file: {APKG_PATH}")
        print(f"   Exists: {APKG_PATH.exists()}")
        if not APKG_PATH.exists():
            print(f"❌ APKG file not found: {APKG_PATH}")
            return
        
        # Add elements to deck
        add_elements_to_deck(elements)
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        print("\nTraceback:")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()

