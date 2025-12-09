#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate detailed reuse report and summarize syllable coverage.
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
import csv

PROJECT_ROOT = project_root
REUSE_REPORT_FILE = PROJECT_ROOT / "data" / "pinyin_reuse_opportunities.csv"


def get_element_to_learn_from_syllable(syllable: str) -> list:
    """Get possible elements to learn from a syllable."""
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


def analyze_reuse_opportunities():
    """Analyze reuse opportunities and generate report"""
    print("=" * 80)
    print("Pinyin Reuse Opportunities Analysis")
    print("=" * 80)
    print()
    
    with get_db_session() as db:
        db_notes = db.query(PinyinSyllableNote).all()
        
        # Build maps
        word_to_elements = defaultdict(set)  # word -> set of elements it's used for
        syllable_to_words = defaultdict(set)  # syllable -> set of (word, element) tuples
        word_to_pinyin = {}  # word -> full pinyin
        word_to_image = {}  # word -> image file
        
        for note in db_notes:
            fields = json.loads(note.fields) if note.fields else {}
            word_hanzi = fields.get('WordHanzi', note.word)
            element_to_learn = fields.get('ElementToLearn', '').strip()
            word_pinyin = fields.get('WordPinyin', '').strip()
            word_picture = fields.get('WordPicture', '')
            
            if element_to_learn:
                word_to_elements[word_hanzi].add(element_to_learn)
                syllable_to_words[note.syllable].add((word_hanzi, element_to_learn))
            
            if word_pinyin:
                word_to_pinyin[word_hanzi] = word_pinyin
            
            # Extract image filename
            if word_picture and '<img src=' in word_picture:
                import re
                match = re.search(r'<img src="([^"]+)"', word_picture)
                if match:
                    word_to_image[word_hanzi] = match.group(1)
        
        print(f"Current state:")
        print(f"  Unique words: {len(word_to_elements)}")
        print(f"  Unique syllables: {len(syllable_to_words)}")
        print()
        
        # Find reuse opportunities
        reuse_opportunities = []
        all_syllables = set(note.syllable for note in db_notes)
        
        for word_hanzi, existing_elements in word_to_elements.items():
            word_pinyin = word_to_pinyin.get(word_hanzi, '')
            if not word_pinyin:
                continue
            
            # Parse word pinyin to get all syllables
            syllables_in_word = [s.strip() for s in word_pinyin.split()]
            
            for syllable in syllables_in_word:
                syllable_no_tone, _ = extract_tone(syllable)
                if not syllable_no_tone:
                    continue
                
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
                            reuse_opportunities.append({
                                'word_hanzi': word_hanzi,
                                'word_pinyin': word_pinyin,
                                'target_syllable': syllable_no_tone,
                                'target_element': element,
                                'existing_elements': sorted(existing_elements),
                                'image_file': word_to_image.get(word_hanzi, ''),
                                'has_image': word_hanzi in word_to_image
                            })
        
        print(f"Found {len(reuse_opportunities)} reuse opportunities")
        print()
        
        # Prioritize: concrete words with images
        prioritized = sorted(
            reuse_opportunities,
            key=lambda x: (
                not x['has_image'],  # Has image first
                x['word_hanzi']  # Then alphabetically
            )
        )
        
        # Group by target_syllable to see coverage
        syllable_coverage = defaultdict(list)
        for opp in prioritized:
            syllable_coverage[opp['target_syllable']].append(opp)
        
        print("=" * 80)
        print("SYLLABLE COVERAGE WITH REUSE")
        print("=" * 80)
        print()
        
        # Current coverage
        current_syllables = set(syllable_to_words.keys())
        reuse_syllables = set(syllable_coverage.keys())
        all_covered = current_syllables | reuse_syllables
        
        print(f"Current syllables covered: {len(current_syllables)}")
        print(f"Additional syllables from reuse: {len(reuse_syllables - current_syllables)}")
        print(f"Total syllables covered (with reuse): {len(all_covered)}")
        print()
        
        # Show syllables that would be newly covered
        newly_covered = reuse_syllables - current_syllables
        if newly_covered:
            print(f"Newly covered syllables ({len(newly_covered)}):")
            for syllable in sorted(newly_covered):
                opportunities = syllable_coverage[syllable]
                with_images = [o for o in opportunities if o['has_image']]
                print(f"  {syllable:6s} - {len(opportunities)} opportunities ({len(with_images)} with images)")
        print()
        
        # Generate CSV report
        print("📝 Generating reuse report CSV...")
        with open(REUSE_REPORT_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'WordHanzi', 'WordPinyin', 'TargetSyllable', 'TargetElement',
                'ExistingElements', 'HasImage', 'ImageFile', 'Priority'
            ])
            writer.writeheader()
            
            for opp in prioritized:
                priority = 'High' if opp['has_image'] else 'Medium'
                writer.writerow({
                    'WordHanzi': opp['word_hanzi'],
                    'WordPinyin': opp['word_pinyin'],
                    'TargetSyllable': opp['target_syllable'],
                    'TargetElement': opp['target_element'],
                    'ExistingElements': ', '.join(opp['existing_elements']),
                    'HasImage': 'Yes' if opp['has_image'] else 'No',
                    'ImageFile': opp['image_file'],
                    'Priority': priority
                })
        
        print(f"✅ Report saved to: {REUSE_REPORT_FILE}")
        print()
        
        # Summary statistics
        print("=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)
        print()
        
        high_priority = [o for o in prioritized if o['has_image']]
        medium_priority = [o for o in prioritized if not o['has_image']]
        
        print(f"High priority (with images): {len(high_priority)}")
        print(f"Medium priority (no images): {len(medium_priority)}")
        print()
        
        # Top reuse opportunities
        print("Top 30 reuse opportunities (with images, prioritized):")
        print()
        for i, opp in enumerate(high_priority[:30], 1):
            existing_str = ', '.join(opp['existing_elements'])
            print(f"{i:3d}. {opp['word_hanzi']:10s} ({opp['word_pinyin']:15s})")
            print(f"     -> Syllable: {opp['target_syllable']:6s} | Element: {opp['target_element']:3s} | "
                  f"Already used for: {existing_str}")
            print(f"     Image: {opp['image_file']}")
            print()
        
        if len(high_priority) > 30:
            print(f"... and {len(high_priority) - 30} more high-priority opportunities")
        
        print()
        print("=" * 80)
        print("✅ Analysis complete!")
        print("=" * 80)


if __name__ == "__main__":
    try:
        analyze_reuse_opportunities()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        raise

