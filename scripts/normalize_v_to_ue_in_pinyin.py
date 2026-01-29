#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Normalize 'v' to 'ü' in pinyin elements and syllables throughout CUMA database.

This script:
1. Updates PinyinElementNote.element field
2. Updates PinyinSyllableNote.syllable field
3. Updates all pinyin-related fields in the fields JSON (Syllable, WordPinyin, Tone1-4, ElementToLearn, Confusor1-3, etc.)
"""

import sys
import json
import re
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import get_db_session, create_backup, DB_PATH
from backend.database.models import PinyinElementNote, PinyinSyllableNote


def normalize_v_to_ue_in_pinyin(text: str) -> str:
    """
    Normalize 'v' to 'ü' in pinyin text.
    
    Note: This is a simple replacement. In actual pinyin:
    - After j/q/x/y, 'ü' is written as 'u' (e.g., 'ju' not 'jü')
    - But in our database, we store the canonical form with 'ü'
    - 'v' is an input method hack that should be normalized to 'ü'
    """
    if not text or not isinstance(text, str):
        return text
    return text.replace('v', 'ü').replace('V', 'Ü')


def normalize_fields_json(fields: dict) -> dict:
    """Normalize 'v' to 'ü' in all pinyin-related fields."""
    pinyin_fields = [
        'Element', 'Syllable', 'WordPinyin', 'ElementToLearn',
        'Tone1', 'Tone2', 'Tone3', 'Tone4',
        'Confusor1', 'Confusor2', 'Confusor3'
    ]
    
    normalized_fields = {}
    for key, value in fields.items():
        if key in pinyin_fields and value:
            if isinstance(value, str):
                normalized_fields[key] = normalize_v_to_ue_in_pinyin(value)
            else:
                normalized_fields[key] = value
        else:
            normalized_fields[key] = value
    
    return normalized_fields


def main():
    """Main function."""
    print("=" * 80)
    print("Normalize 'v' to 'ü' in Pinyin Elements and Syllables")
    print("=" * 80)
    
    # Backup database first
    print("\n💾 Creating database backup...")
    try:
        backup_path = create_backup()
        print(f"   ✅ Backup created: {backup_path}")
    except Exception as e:
        print(f"   ⚠️  Warning: Could not create backup: {e}")
        response = input("   Continue without backup? (y/n): ")
        if response.lower() != 'y':
            print("   ❌ Aborted.")
            return
    
    with get_db_session() as db:
        # Update PinyinElementNote
        print("\n📝 Updating PinyinElementNote records...")
        element_updates = 0
        element_field_updates = 0
        
        elements = db.query(PinyinElementNote).all()
        for elem in elements:
            updated = False
            
            # Update element field
            if 'v' in elem.element or 'V' in elem.element:
                old_element = elem.element
                elem.element = normalize_v_to_ue_in_pinyin(elem.element)
                updated = True
                element_updates += 1
                print(f"   ✅ Element '{old_element}' → '{elem.element}'")
            
            # Update fields JSON
            if elem.fields:
                try:
                    fields = json.loads(elem.fields)
                    normalized_fields = normalize_fields_json(fields)
                    
                    # Check if any field changed
                    if normalized_fields != fields:
                        elem.fields = json.dumps(normalized_fields, ensure_ascii=False)
                        element_field_updates += 1
                        updated = True
                        print(f"   ✅ Updated fields for element '{elem.element}'")
                except json.JSONDecodeError:
                    print(f"   ⚠️  Warning: Invalid JSON in element '{elem.element}' fields")
        
        print(f"   ✅ Updated {element_updates} element fields")
        print(f"   ✅ Updated {element_field_updates} element field JSONs")
        
        # Update PinyinSyllableNote
        print("\n📝 Updating PinyinSyllableNote records...")
        syllable_updates = 0
        syllable_field_updates = 0
        
        syllables = db.query(PinyinSyllableNote).all()
        for syl in syllables:
            updated = False
            
            # Update syllable field
            if 'v' in syl.syllable or 'V' in syl.syllable:
                old_syllable = syl.syllable
                syl.syllable = normalize_v_to_ue_in_pinyin(syl.syllable)
                updated = True
                syllable_updates += 1
                print(f"   ✅ Syllable '{old_syllable}' → '{syl.syllable}'")
            
            # Update fields JSON
            if syl.fields:
                try:
                    fields = json.loads(syl.fields)
                    normalized_fields = normalize_fields_json(fields)
                    
                    # Check if any field changed
                    if normalized_fields != fields:
                        syl.fields = json.dumps(normalized_fields, ensure_ascii=False)
                        syllable_field_updates += 1
                        updated = True
                        print(f"   ✅ Updated fields for syllable '{syl.syllable}'")
                except json.JSONDecodeError:
                    print(f"   ⚠️  Warning: Invalid JSON in syllable '{syl.syllable}' fields")
        
        print(f"   ✅ Updated {syllable_updates} syllable fields")
        print(f"   ✅ Updated {syllable_field_updates} syllable field JSONs")
        
        print("\n✅ Normalization complete!")
        print(f"   - Elements updated: {element_updates}")
        print(f"   - Element fields updated: {element_field_updates}")
        print(f"   - Syllables updated: {syllable_updates}")
        print(f"   - Syllable fields updated: {syllable_field_updates}")


if __name__ == "__main__":
    main()







