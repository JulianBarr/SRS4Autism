#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update pinyin notes to use proper tone marks instead of tone numbers.

This script:
1. Updates existing element notes: converts Tone1-Tone4 from "a1" to "ā" format
2. Updates existing syllable notes: converts "ma1" to "mā" format
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import add_tone_to_final, TONE_MARKS
from backend.database.models import PinyinElementNote, PinyinSyllableNote, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = project_root
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"


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


def update_element_notes(session):
    """Update element notes to use proper tone marks"""
    print("\n1. Updating element notes...")
    notes = session.query(PinyinElementNote).all()
    updated_count = 0
    
    for note in notes:
        fields = json.loads(note.fields) if note.fields else {}
        updated = False
        
        # Update Tone1-Tone4 fields
        element = fields.get('Element', '')
        if element:
            for tone_num in [1, 2, 3, 4]:
                tone_field = f'Tone{tone_num}'
                current_value = fields.get(tone_field, '')
                
                # Check if it's in "a1" format
                if current_value and current_value.endswith(str(tone_num)):
                    # Extract element and convert
                    element_part = current_value[:-1]  # Remove the number
                    if element_part == element:
                        # Convert to tone mark
                        toned = convert_tone_number_to_mark(element, tone_num)
                        if toned != current_value:
                            fields[tone_field] = toned
                            updated = True
                            print(f"   ✅ {note.element}: {tone_field} {current_value} -> {toned}")
        
        if updated:
            note.fields = json.dumps(fields, ensure_ascii=False)
            updated_count += 1
    
    session.commit()
    print(f"   ✅ Updated {updated_count} element notes")
    return updated_count


def update_syllable_notes(session):
    """Update syllable notes to use proper tone marks"""
    print("\n2. Updating syllable notes...")
    notes = session.query(PinyinSyllableNote).all()
    updated_count = 0
    
    for note in notes:
        fields = json.loads(note.fields) if note.fields else {}
        updated = False
        
        # Update Syllable field (e.g., "ma1" -> "mā")
        syllable = fields.get('Syllable', '')
        if syllable and syllable[-1].isdigit():
            # Extract tone number
            tone_num = int(syllable[-1])
            syllable_no_tone = syllable[:-1]
            
            # Convert to tone mark
            toned_syllable = add_tone_to_final(syllable_no_tone, tone_num)
            if toned_syllable != syllable:
                fields['Syllable'] = toned_syllable
                # Also update the note's syllable field
                note.syllable = toned_syllable
                updated = True
                print(f"   ✅ {note.word}: Syllable {syllable} -> {toned_syllable}")
        
        # Update WordPinyin if it has tone numbers
        word_pinyin = fields.get('WordPinyin', '')
        if word_pinyin:
            # Simple conversion: replace patterns like "ma1" with "mā"
            import re
            def replace_tone(match):
                syllable_part = match.group(1)
                tone_num = int(match.group(2))
                return add_tone_to_final(syllable_part, tone_num)
            
            new_word_pinyin = re.sub(r'([a-zü]+)([1-4])', replace_tone, word_pinyin, flags=re.IGNORECASE)
            if new_word_pinyin != word_pinyin:
                fields['WordPinyin'] = new_word_pinyin
                updated = True
                print(f"   ✅ {note.word}: WordPinyin {word_pinyin} -> {new_word_pinyin}")
        
        if updated:
            note.fields = json.dumps(fields, ensure_ascii=False)
            updated_count += 1
    
    session.commit()
    print(f"   ✅ Updated {updated_count} syllable notes")
    return updated_count


def main():
    """Main function"""
    print("=" * 80)
    print("Update Pinyin Notes to Use Proper Tone Marks")
    print("=" * 80)
    
    if not DB_PATH.exists():
        print(f"❌ Error: Database not found at {DB_PATH}")
        return
    
    # Connect to database
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Update element notes
        element_count = update_element_notes(session)
        
        # Update syllable notes
        syllable_count = update_syllable_notes(session)
        
        print(f"\n✅ Update complete!")
        print(f"   - Updated {element_count} element notes")
        print(f"   - Updated {syllable_count} syllable notes")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()

















