#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix tone marks for ü in WordPinyin fields.

This script:
1. Finds syllables with ü in WordPinyin that are missing tone marks
2. Looks up the correct pinyin with tones from the knowledge graph
3. Updates WordPinyin fields with proper tone-marked ü (ǖ, ǘ, ǚ, ǜ)
"""

import sys
import json
import re
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import get_db_session, create_backup
from backend.database.models import PinyinSyllableNote
from scripts.knowledge_graph.pinyin_parser import TONE_MARKS, extract_tone, add_tone_to_final


def get_word_pinyin_from_kg(word: str) -> str:
    """Get pinyin with tones from knowledge graph."""
    try:
        from backend.app.main import get_word_knowledge
        word_info = get_word_knowledge(word)
        pronunciations = word_info.get("pronunciations", [])
        if pronunciations:
            return pronunciations[0]  # Return first pronunciation
    except Exception as e:
        print(f"  ⚠️  Could not get pinyin from KG for '{word}': {e}")
    return None


def fix_ue_tone_in_pinyin(pinyin: str) -> str:
    """
    Fix ü tone marks in pinyin string.
    Replaces 'lü', 'nü', etc. with proper tone-marked versions if tone can be determined.
    """
    if not pinyin:
        return pinyin
    
    # Split into syllables
    syllables = pinyin.split()
    fixed_syllables = []
    
    for syllable in syllables:
        # Check if syllable contains ü without tone mark
        if 'ü' in syllable and not any(mark in syllable for mark in ['ǖ', 'ǘ', 'ǚ', 'ǜ']):
            # Try to extract tone from the syllable
            syllable_no_tone, tone = extract_tone(syllable)
            
            if tone:
                # Add tone to ü
                fixed_syllable = add_tone_to_final(syllable_no_tone, tone)
                fixed_syllables.append(fixed_syllable)
            else:
                # No tone found, keep as is (might be tone 0 or neutral)
                fixed_syllables.append(syllable)
        else:
            fixed_syllables.append(syllable)
    
    return ' '.join(fixed_syllables)


def main():
    """Main function."""
    print("=" * 80)
    print("Fix ü Tone Marks in WordPinyin Fields")
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
        print("\n📝 Checking syllables with ü in WordPinyin...")
        
        syllables_with_ue = db.query(PinyinSyllableNote).filter(
            PinyinSyllableNote.syllable.like('%ü%')
        ).all()
        
        updated_count = 0
        
        for syl in syllables_with_ue:
            if not syl.fields:
                continue
            
            try:
                fields = json.loads(syl.fields)
                word_pinyin = fields.get('WordPinyin', '')
                word = syl.word
                
                if not word_pinyin:
                    continue
                
                # Check if WordPinyin has ü without tone mark
                if 'ü' in word_pinyin and not any(mark in word_pinyin for mark in ['ǖ', 'ǘ', 'ǚ', 'ǜ']):
                    print(f"\n  Found: {word} - Current WordPinyin: {word_pinyin}")
                    
                    # Try to get correct pinyin from knowledge graph
                    correct_pinyin = get_word_pinyin_from_kg(word)
                    
                    if correct_pinyin:
                        # Check if the correct pinyin has proper tone marks
                        if 'ü' in correct_pinyin and any(mark in correct_pinyin for mark in ['ǖ', 'ǘ', 'ǚ', 'ǜ']):
                            fields['WordPinyin'] = correct_pinyin
                            syl.fields = json.dumps(fields, ensure_ascii=False)
                            updated_count += 1
                            print(f"    ✅ Updated to: {correct_pinyin}")
                        else:
                            # Try to fix it using the fix function
                            fixed = fix_ue_tone_in_pinyin(word_pinyin)
                            if fixed != word_pinyin:
                                fields['WordPinyin'] = fixed
                                syl.fields = json.dumps(fields, ensure_ascii=False)
                                updated_count += 1
                                print(f"    ✅ Fixed to: {fixed}")
                            else:
                                print(f"    ⚠️  Could not determine tone for '{word_pinyin}'")
                    else:
                        # Try to fix it using the fix function
                        fixed = fix_ue_tone_in_pinyin(word_pinyin)
                        if fixed != word_pinyin:
                            fields['WordPinyin'] = fixed
                            syl.fields = json.dumps(fields, ensure_ascii=False)
                            updated_count += 1
                            print(f"    ✅ Fixed to: {fixed}")
                        else:
                            print(f"    ⚠️  Could not determine tone for '{word_pinyin}'")
                            
            except json.JSONDecodeError:
                print(f"  ⚠️  Warning: Invalid JSON in syllable '{syl.syllable}' fields")
            except Exception as e:
                print(f"  ⚠️  Error processing syllable '{syl.syllable}': {e}")
        
        print(f"\n✅ Fix complete!")
        print(f"   - Updated {updated_count} WordPinyin fields")


if __name__ == "__main__":
    main()



