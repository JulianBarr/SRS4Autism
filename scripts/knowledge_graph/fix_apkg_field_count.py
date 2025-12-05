#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix field count inconsistency in .apkg file.

When a new field is added to a note type, all existing notes need to be updated
to include the new field (even if empty).
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"


def fix_field_count(apkg_path: Path):
    """Fix field count for all notes in the .apkg file"""
    
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
        print("\n2. Fixing field counts...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get note models
        cursor.execute("SELECT models FROM col")
        col_data = cursor.fetchone()
        models = json.loads(col_data[0]) if col_data else {}
        
        # Find syllable model
        syllable_model_id = None
        syllable_model = None
        
        for mid_str, model in models.items():
            if model.get('name') == 'CUMA - Pinyin Syllable':
                syllable_model_id = int(mid_str)
                syllable_model = model
                break
        
        if not syllable_model:
            print("❌ Error: CUMA - Pinyin Syllable model not found")
            conn.close()
            return False
        
        # Get expected field count
        expected_field_count = len(syllable_model.get('flds', []))
        print(f"   Expected field count: {expected_field_count}")
        
        # Get all notes for this model
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
        all_notes = cursor.fetchall()
        
        updated_count = 0
        
        for note_id, flds in all_notes:
            fields = flds.split('\x1f')
            current_field_count = len(fields)
            
            if current_field_count != expected_field_count:
                print(f"   ⚠️  Note {note_id}: has {current_field_count} fields, expected {expected_field_count}")
                
                # Pad with empty fields if too few, or truncate if too many
                if current_field_count < expected_field_count:
                    # Add empty fields
                    fields.extend([''] * (expected_field_count - current_field_count))
                else:
                    # Truncate (shouldn't happen, but just in case)
                    fields = fields[:expected_field_count]
                
                # Update note
                updated_flds = '\x1f'.join(fields)
                cursor.execute("UPDATE notes SET flds = ? WHERE id = ?", (updated_flds, note_id))
                updated_count += 1
                print(f"      ✅ Fixed: now has {len(fields)} fields")
        
        if updated_count > 0:
            conn.commit()
            print(f"\n   ✅ Fixed {updated_count} notes")
        else:
            print("\n   ✅ All notes already have correct field count")
        
        conn.close()
        
        # Repackage .apkg
        print("\n3. Repackaging .apkg file...")
        
        with zipfile.ZipFile(apkg_path, 'w', zipfile.ZIP_DEFLATED) as z:
            # Add all files from tmpdir
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print(f"   ✅ Updated .apkg: {apkg_path}")
        return True


def main():
    """Main function"""
    print("=" * 80)
    print("Fix Field Count Inconsistency")
    print("=" * 80)
    
    success = fix_field_count(APKG_PATH)
    
    if success:
        print("\n✅ Fix complete!")
        print(f"\n📦 Updated .apkg file: {APKG_PATH}")
        print("\nYou can now import the .apkg file into Anki without field count errors.")
    else:
        print("\n❌ Failed to fix .apkg file")


if __name__ == "__main__":
    main()


