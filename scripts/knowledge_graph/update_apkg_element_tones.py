#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: Update Element card tones in the original .apkg file.

This script:
1. Extracts the original .apkg file (语言语文__拼音.apkg)
2. Updates Element card notes: converts Tone1-Tone4 from "a1" format to proper pinyin (ā, á, ǎ, à)
3. Repackages the .apkg file

Per instructions: "the four tones should display proper tones instead of 1-4"
"""

import sys
import os
import sqlite3
import zipfile
import tempfile
import json
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import add_tone_to_final, TONE_MARKS

PROJECT_ROOT = project_root
ORIGINAL_APKG = PROJECT_ROOT / "data" / "content_db" / "语言语文__拼音.apkg"
OUTPUT_APKG = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"


def convert_tone_number_to_mark(element: str, tone: int) -> str:
    """Convert element with tone number to tone mark (e.g., 'a1' -> 'ā')"""
    if tone < 1 or tone > 4:
        return element
    
    # Find the vowel to mark
    vowels_priority = ['a', 'o', 'e', 'i', 'u', 'ü', 'A', 'O', 'E', 'I', 'U', 'Ü']
    for vowel in vowels_priority:
        if vowel in element:
            mark = TONE_MARKS.get(vowel, [])[tone - 1]
            if mark:
                return element.replace(vowel, mark, 1)
    
    return element


def update_element_tones_in_apkg(apkg_path: Path, output_path: Path):
    """Extract, update, and repackage .apkg file"""
    
    if not apkg_path.exists():
        print(f"❌ Error: APKG file not found at {apkg_path}")
        return False
    
    print(f"📦 Opening .apkg file: {apkg_path}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg
        print("\n1. Extracting .apkg file...")
        with zipfile.ZipFile(apkg_path, 'r') as z:
            z.extractall(tmpdir_path)
        
        db_path = tmpdir_path / "collection.anki21"
        if not db_path.exists():
            db_path = tmpdir_path / "collection.anki2"
        
        if not db_path.exists():
            print("❌ Error: No database found in .apkg file")
            return False
        
        # Connect to database
        print("\n2. Updating database...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get note models
        cursor.execute("SELECT models FROM col")
        col_data = cursor.fetchone()
        models = json.loads(col_data[0]) if col_data else {}
        
        # Get all notes
        cursor.execute("SELECT id, mid, flds FROM notes ORDER BY id")
        all_notes = cursor.fetchall()
        
        updated_count = 0
        
        for note_id, mid, flds in all_notes:
            fields = flds.split('\x1f')
            
            # Get model to understand field structure
            model = models.get(str(mid), {})
            model_name = model.get('name', '')
            field_names = [f.get('name', f'Field{i}') for i, f in enumerate(model.get('flds', []))]
            
            # Only process "CUMA - Pinyin Element" notes
            if model_name != "CUMA - Pinyin Element":
                continue
            
            # Build fields dictionary
            note_fields = {}
            for i, field_value in enumerate(fields):
                field_name = field_names[i] if i < len(field_names) else f'Field{i}'
                note_fields[field_name] = field_value or ""
            
            # Get element
            element = note_fields.get('Element', '').strip()
            if not element:
                continue
            
            # Update Tone1-Tone4 fields
            updated = False
            for tone_num in [1, 2, 3, 4]:
                tone_field = f'Tone{tone_num}'
                
                # Find field index
                if tone_field not in field_names:
                    continue
                
                field_idx = field_names.index(tone_field)
                if field_idx >= len(fields):
                    continue
                
                current_value = fields[field_idx].strip()
                
                # Check if it's in "a1" format (element + number)
                if current_value and current_value.endswith(str(tone_num)):
                    element_part = current_value[:-1]  # Remove the number
                    if element_part == element:
                        # Convert to tone mark
                        toned = convert_tone_number_to_mark(element, tone_num)
                        if toned != current_value:
                            fields[field_idx] = toned
                            updated = True
                            print(f"   ✅ Note {note_id} ({element}): {tone_field} {current_value} -> {toned}")
            
            # Update database if changed
            if updated:
                updated_flds = '\x1f'.join(fields)
                cursor.execute("UPDATE notes SET flds = ? WHERE id = ?", (updated_flds, note_id))
                updated_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"\n   ✅ Updated {updated_count} element notes")
        
        # Repackage .apkg
        print("\n3. Repackaging .apkg file...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
            # Add all files from tmpdir
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print(f"   ✅ Created updated .apkg: {output_path}")
        return True


def main():
    """Main function"""
    print("=" * 80)
    print("Step 1: Update Element Card Tones")
    print("=" * 80)
    print("\nConverting Tone1-Tone4 fields from 'a1' format to proper pinyin (ā, á, ǎ, à)")
    
    success = update_element_tones_in_apkg(ORIGINAL_APKG, OUTPUT_APKG)
    
    if success:
        print("\n✅ Step 1 complete!")
        print(f"\n📦 Updated .apkg file: {OUTPUT_APKG}")
        print("\nNext steps:")
        print("  - Import the updated .apkg file into Anki to verify")
        print("  - Element cards should now show proper pinyin (ā, á, ǎ, à) instead of numbers")
    else:
        print("\n❌ Failed to update .apkg file")


if __name__ == "__main__":
    main()


