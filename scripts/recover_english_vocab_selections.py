#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recover English vocabulary selections for pinyin syllables.

This script can help restore English vocab selections that might have been lost.
It reads from pending_syllable_english_matches.json and updates the CSV file.
"""

import sys
import csv
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Paths
CSV_FILE = PROJECT_ROOT / "data" / "pinyin_gap_fill_suggestions.csv"
MATCHES_FILE = PROJECT_ROOT / "data" / "pending_syllable_english_matches.json"
BACKUP_FILE = CSV_FILE.with_suffix('.csv.backup')

def load_csv():
    """Load current CSV suggestions."""
    suggestions = {}
    if CSV_FILE.exists():
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                suggestions[row['Syllable']] = row
    return suggestions

def load_english_vocab_matches():
    """Load English vocab matches."""
    if not MATCHES_FILE.exists():
        print(f"❌ English vocab matches file not found: {MATCHES_FILE}")
        return {}
    
    with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('matches', {})

def convert_numbered_pinyin_to_tones(pinyin):
    """Convert numbered pinyin (e.g., 'hua1 bao4') to tone-marked pinyin (e.g., 'huā bào')."""
    # Tone mark maps
    TONE_MARKS = {
        'a': ['ā', 'á', 'ǎ', 'à'],
        'o': ['ō', 'ó', 'ǒ', 'ò'],
        'e': ['ē', 'é', 'ě', 'è'],
        'i': ['ī', 'í', 'ǐ', 'ì'],
        'u': ['ū', 'ú', 'ǔ', 'ù'],
        'ü': ['ǖ', 'ǘ', 'ǚ', 'ǜ']
    }
    
    def convert_syllable(syllable):
        # Extract tone number
        if syllable and len(syllable) > 0 and syllable[-1].isdigit():
            tone = int(syllable[-1])
            syllable_no_tone = syllable[:-1].lower()
            
            # Special cases: iu/ui
            if 'iu' in syllable_no_tone:
                iu_idx = syllable_no_tone.index('iu')
                u_idx = iu_idx + 1
                mark = TONE_MARKS['u'][tone - 1]
                return syllable[:-1][:u_idx] + mark + syllable[:-1][u_idx+1:]
            elif 'ui' in syllable_no_tone:
                ui_idx = syllable_no_tone.index('ui')
                i_idx = ui_idx + 1
                mark = TONE_MARKS['i'][tone - 1]
                return syllable[:-1][:i_idx] + mark + syllable[:-1][i_idx+1:]
            
            # Regular priority: a > o > e > i > u > ü
            for vowel in ['a', 'o', 'e', 'i', 'u', 'ü']:
                if vowel in syllable_no_tone:
                    mark = TONE_MARKS[vowel][tone - 1]
                    return syllable[:-1].replace(vowel, mark, 1)
        
        return syllable
    
    # Split by spaces and convert each syllable
    syllables = pinyin.split()
    converted = [convert_syllable(s) for s in syllables]
    return ' '.join(converted)

def find_image_for_english_word(english_word):
    """Try to find image file for English word."""
    import re
    pinyin_dir = PROJECT_ROOT / "media" / "pinyin"
    if not pinyin_dir.exists():
        return ""
    
    word_clean = re.sub(r'[^a-z0-9_-]', '', english_word.lower().replace(" ", "_"))
    
    # Try common extensions
    for ext in ['.jpg', '.jpeg', '.png', '.gif']:
        test_file = pinyin_dir / f"{word_clean}{ext}"
        if test_file.exists():
            return test_file.name
        # Try with _1, _2, etc.
        for i in range(1, 10):
            test_file = pinyin_dir / f"{word_clean}_{i}{ext}"
            if test_file.exists():
                return test_file.name
    
    return ""

def recover_selections(interactive=False):
    """Recover English vocab selections."""
    print("=" * 80)
    print("English Vocabulary Selection Recovery Tool")
    print("=" * 80)
    
    # Load data
    print("\n📂 Loading data...")
    suggestions = load_csv()
    matches = load_english_vocab_matches()
    
    print(f"   Loaded {len(suggestions)} suggestions from CSV")
    print(f"   Loaded {len(matches)} syllables with English vocab matches")
    
    # Find items that need recovery
    print("\n🔍 Analyzing suggestions...")
    to_update = []
    
    for syllable, english_matches in matches.items():
        if syllable not in suggestions:
            continue
        
        current = suggestions[syllable]
        current_word = current.get('Suggested Word', '').strip()
        
        # If NONE or empty, suggest first English vocab match
        if not current_word or current_word == 'NONE':
            if english_matches:
                best_match = english_matches[0]  # First match is usually best
                to_update.append({
                    'syllable': syllable,
                    'current': current,
                    'match': best_match
                })
    
    print(f"   Found {len(to_update)} syllables that could be updated")
    
    if not to_update:
        print("\n✅ No recovery needed - all suggestions already have words!")
        return
    
    # Show what will be updated
    print("\n📋 Items to update:")
    for i, item in enumerate(to_update[:10], 1):
        match = item['match']
        print(f"   {i}. {item['syllable']}: {match['english']} -> {match['chinese']} ({match['pinyin']})")
    if len(to_update) > 10:
        print(f"   ... and {len(to_update) - 10} more")
    
    if interactive:
        response = input(f"\n❓ Update {len(to_update)} suggestions? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cancelled.")
            return
    
    # Create backup
    print("\n💾 Creating backup...")
    if CSV_FILE.exists():
        import shutil
        shutil.copy2(CSV_FILE, BACKUP_FILE)
        print(f"   Backup created: {BACKUP_FILE}")
    
    # Update suggestions
    print("\n🔄 Updating suggestions...")
    fieldnames = ['Syllable', 'Suggested Word', 'Word Pinyin', 'HSK Level', 
                 'Frequency Rank', 'Has Image', 'Image File', 'Concreteness', 
                 'AoA', 'Num Syllables', 'Score', 'approved']
    
    for item in to_update:
        syllable = item['syllable']
        match = item['match']
        current = item['current']
        
        # Convert pinyin to tone marks
        pinyin_with_tones = convert_numbered_pinyin_to_tones(match['pinyin'])
        
        # Find image
        image_file = find_image_for_english_word(match['english'])
        
        # Update suggestion
        suggestions[syllable] = {
            'Syllable': syllable,
            'Suggested Word': match['chinese'],
            'Word Pinyin': pinyin_with_tones,
            'HSK Level': current.get('HSK Level', '-'),
            'Frequency Rank': current.get('Frequency Rank', '-'),
            'Has Image': 'Yes' if image_file else 'No',
            'Image File': image_file,
            'Concreteness': str(match.get('concreteness', '-')) if match.get('concreteness') else '-',
            'AoA': current.get('AoA', '-'),
            'Num Syllables': current.get('Num Syllables', '-'),
            'Score': current.get('Score', '-'),
            'approved': ''  # Clear approval so user can review
        }
    
    # Write updated CSV
    print(f"\n💾 Writing updated CSV to {CSV_FILE}...")
    with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for syllable in sorted(suggestions.keys()):
            writer.writerow(suggestions[syllable])
    
    print(f"✅ Successfully updated {len(to_update)} suggestions!")
    print(f"   Backup available at: {BACKUP_FILE}")

if __name__ == "__main__":
    interactive = '--yes' not in sys.argv
    recover_selections(interactive=interactive)

