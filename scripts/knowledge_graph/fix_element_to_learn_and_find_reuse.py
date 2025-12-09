#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1. Add ElementToLearn field to all syllable notes (if missing)
2. Review 323 word+syllable combinations to find reuse opportunities for other syllables
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.db import get_db_session
from backend.database.models import PinyinSyllableNote
from scripts.knowledge_graph.pinyin_parser import extract_tone, parse_pinyin
import shutil
from datetime import datetime

PROJECT_ROOT = project_root
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def create_database_backup():
    """Create a backup of the SQLite database"""
    if not DB_PATH.exists():
        print("⚠️  Database file does not exist, nothing to backup")
        return None
    
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f"srs4autism_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    size_mb = backup_path.stat().st_size / (1024 * 1024)
    print(f"✅ Database backup created: {backup_path}")
    print(f"   Size: {size_mb:.2f} MB")
    return backup_path


def get_element_to_learn_from_syllable(syllable: str) -> list:
    """
    Get possible elements to learn from a syllable.
    Returns list of [initial, final] that could be the ElementToLearn.
    """
    syllable_no_tone, _ = extract_tone(syllable)
    if not syllable_no_tone:
        return []
    
    parsed = parse_pinyin(syllable_no_tone)
    initial = parsed.get('initial', '')
    final = parsed.get('final', '')
    
    elements = []
    if initial:
        elements.append(initial)
    if final:
        elements.append(final)
    
    return elements


def analyze_and_fix():
    """Analyze ElementToLearn and find reuse opportunities"""
    print("=" * 80)
    print("Fix ElementToLearn and Find Reuse Opportunities")
    print("=" * 80)
    print()
    
    # Create backup
    print("💾 Creating database backup...")
    try:
        backup_path = create_database_backup()
    except Exception as e:
        print(f"   ❌ Error creating backup: {e}")
        return
    print()
    
    with get_db_session() as db:
        db_notes = db.query(PinyinSyllableNote).all()
        
        # Track by (WordHanzi, ElementToLearn) to find reuse opportunities
        word_to_elements = defaultdict(set)  # word -> set of elements it's used for
        syllable_to_words = defaultdict(set)  # syllable -> set of (word, element) tuples
        missing_element_to_learn = []
        
        print("📊 Analyzing current state...")
        print()
        
        for note in db_notes:
            fields = json.loads(note.fields) if note.fields else {}
            word_hanzi = fields.get('WordHanzi', note.word)
            element_to_learn = fields.get('ElementToLearn', '').strip()
            
            if not element_to_learn:
                missing_element_to_learn.append({
                    'note_id': note.note_id,
                    'syllable': note.syllable,
                    'word': word_hanzi
                })
            
            if element_to_learn:
                word_to_elements[word_hanzi].add(element_to_learn)
                syllable_to_words[note.syllable].add((word_hanzi, element_to_learn))
        
        print(f"Notes missing ElementToLearn: {len(missing_element_to_learn)}")
        print(f"Unique words: {len(word_to_elements)}")
        print(f"Unique syllables: {len(syllable_to_words)}")
        print()
        
        # Fix missing ElementToLearn
        if missing_element_to_learn:
            print("🔧 Fixing missing ElementToLearn fields...")
            print()
            
            fixed_count = 0
            for item in missing_element_to_learn:
                note = db.query(PinyinSyllableNote).filter_by(note_id=item['note_id']).first()
                if not note:
                    continue
                
                fields = json.loads(note.fields) if note.fields else {}
                syllable = note.syllable
                
                # Determine ElementToLearn from syllable
                possible_elements = get_element_to_learn_from_syllable(syllable)
                
                # Check if this word is already used for any element
                word_hanzi = fields.get('WordHanzi', note.word)
                existing_elements = word_to_elements.get(word_hanzi, set())
                
                # Choose element that's not already used, or just use the final if available
                element_to_learn = ''
                if possible_elements:
                    # Prefer final (usually the second element)
                    if len(possible_elements) > 1 and possible_elements[1] not in existing_elements:
                        element_to_learn = possible_elements[1]  # final
                    elif possible_elements[0] not in existing_elements:
                        element_to_learn = possible_elements[0]  # initial
                    else:
                        # Use any available element
                        element_to_learn = possible_elements[-1]
                
                if element_to_learn:
                    fields['ElementToLearn'] = element_to_learn
                    note.fields = json.dumps(fields, ensure_ascii=False)
                    fixed_count += 1
                    word_to_elements[word_hanzi].add(element_to_learn)
                    print(f"  ✅ {note.syllable:6s} ({word_hanzi:10s}) -> ElementToLearn: {element_to_learn}")
            
            print()
            print(f"✅ Fixed {fixed_count} notes")
            print()
        
        # Analyze reuse opportunities
        print("=" * 80)
        print("REUSE OPPORTUNITIES")
        print("=" * 80)
        print()
        print("Finding words that can be reused for additional syllables...")
        print()
        
        # Get all syllables that need words
        all_syllables = set()
        for note in db_notes:
            all_syllables.add(note.syllable)
        
        # For each word, check if it contains other syllables that could use it
        reuse_opportunities = defaultdict(list)  # (word, target_syllable) -> [existing elements]
        
        for word_hanzi, existing_elements in word_to_elements.items():
            # Get all notes with this word
            word_notes = [n for n in db_notes if json.loads(n.fields).get('WordHanzi', n.word) == word_hanzi]
            
            for note in word_notes:
                fields = json.loads(note.fields) if note.fields else {}
                word_pinyin = fields.get('WordPinyin', '').strip()
                
                if word_pinyin:
                    # Parse word pinyin to get all syllables
                    syllables_in_word = [s.strip() for s in word_pinyin.split()]
                    
                    # For each syllable in the word, check if we can reuse this word
                    for syllable in syllables_in_word:
                        syllable_no_tone, _ = extract_tone(syllable)
                        if syllable_no_tone:
                            # Check if this syllable already has this word
                            existing_for_syllable = any(
                                n.syllable == syllable_no_tone and 
                                json.loads(n.fields).get('WordHanzi', n.word) == word_hanzi
                                for n in db_notes
                            )
                            
                            if not existing_for_syllable:
                                # This syllable doesn't have this word yet - potential reuse
                                possible_elements = get_element_to_learn_from_syllable(syllable_no_tone)
                                for element in possible_elements:
                                    if element not in existing_elements:
                                        reuse_opportunities[(word_hanzi, syllable_no_tone)].append({
                                            'element': element,
                                            'existing_elements': list(existing_elements),
                                            'word_pinyin': word_pinyin
                                        })
        
        if reuse_opportunities:
            print(f"Found {len(reuse_opportunities)} reuse opportunities:")
            print()
            for (word, syllable), opportunities in sorted(reuse_opportunities.items(), key=lambda x: x[0][1])[:30]:
                for opp in opportunities:
                    print(f"  Word: {word:10s} | Syllable: {syllable:6s} | Element: {opp['element']:3s} | "
                          f"Already used for: {', '.join(opp['existing_elements'])}")
            if len(reuse_opportunities) > 30:
                print(f"  ... and {len(reuse_opportunities) - 30} more")
        else:
            print("  No obvious reuse opportunities found (all syllables already covered)")
        
        print()
        print("=" * 80)
        print("✅ Analysis complete!")
        print("=" * 80)


if __name__ == "__main__":
    try:
        analyze_and_fix()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        raise

