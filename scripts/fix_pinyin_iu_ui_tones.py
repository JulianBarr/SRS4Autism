#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix existing pinyin syllable notes to follow 'i u 并列标在后' rule.

This script:
1. Checks all existing PinyinSyllableNote entries
2. Fixes pinyin tone marks that violate the 'i u 并列标在后' rule
3. Updates the database with corrected pinyin

Rule: When i and u appear together:
- 'iu' -> tone should be on 'u' (e.g., 'liú' not 'líu')
- 'ui' -> tone should be on 'i' (e.g., 'guì' not 'gúi')
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.database.db import get_db_session
from backend.database.models import PinyinSyllableNote
from backend.app.main import fix_iu_ui_tone_placement


def fix_syllable_notes():
    """Fix all syllable notes to follow i u 并列标在后 rule"""
    print("🔧 Fixing pinyin tone marks to follow 'i u 并列标在后' rule...\n")
    
    with get_db_session() as db:
        notes = db.query(PinyinSyllableNote).all()
        print(f"Found {len(notes)} syllable notes to check\n")
        
        updated_count = 0
        fixed_entries = []
        
        for note in notes:
            fields = json.loads(note.fields) if note.fields else {}
            updated = False
            
            # Fix WordPinyin field
            word_pinyin = fields.get('WordPinyin', '')
            if word_pinyin:
                fixed_pinyin = fix_iu_ui_tone_placement(word_pinyin)
                if fixed_pinyin != word_pinyin:
                    fields['WordPinyin'] = fixed_pinyin
                    updated = True
                    fixed_entries.append({
                        'word': note.word,
                        'field': 'WordPinyin',
                        'old': word_pinyin,
                        'new': fixed_pinyin
                    })
                    print(f"   ✅ {note.word}: WordPinyin")
                    print(f"      {word_pinyin} -> {fixed_pinyin}")
            
            # Fix Syllable field
            syllable = fields.get('Syllable', '') or note.syllable
            if syllable:
                fixed_syllable = fix_iu_ui_tone_placement(syllable)
                if fixed_syllable != syllable:
                    fields['Syllable'] = fixed_syllable
                    note.syllable = fixed_syllable
                    updated = True
                    fixed_entries.append({
                        'word': note.word,
                        'field': 'Syllable',
                        'old': syllable,
                        'new': fixed_syllable
                    })
                    print(f"   ✅ {note.word}: Syllable")
                    print(f"      {syllable} -> {fixed_syllable}")
            
            if updated:
                note.fields = json.dumps(fields, ensure_ascii=False)
                updated_count += 1
        
        if updated_count > 0:
            db.commit()
            print(f"\n✅ Successfully fixed {updated_count} notes ({len(fixed_entries)} fields)")
        else:
            print(f"\n✅ No violations found - all entries already follow the rule!")
        
        return updated_count, fixed_entries


if __name__ == "__main__":
    try:
        updated_count, fixed_entries = fix_syllable_notes()
        
        if fixed_entries:
            print("\n📋 Summary of fixes:")
            for entry in fixed_entries[:20]:  # Show first 20
                print(f"  {entry['word']}: {entry['field']}")
                print(f"    {entry['old']} -> {entry['new']}")
            if len(fixed_entries) > 20:
                print(f"  ... and {len(fixed_entries) - 20} more")
        
        print(f"\n✨ Done! Fixed {updated_count} notes.")
        
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        sys.exit(1)

