#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Match pending pinyin syllables with English vocabulary from Anki decks.
Use CEDICT to find Chinese words that match English words.
"""

import sys
import sqlite3
import json
import zipfile
import tempfile
from pathlib import Path
from collections import defaultdict
import re

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
CEDICT_FILE = PROJECT_ROOT / "data" / "content_db" / "cedict_1_0_ts_utf-8_mdbg.txt"
APKG_FILES = [
    PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__1. Basic.apkg",
    PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"
]


def load_cedict():
    """Load CEDICT dictionary"""
    cedict = defaultdict(list)  # english -> [(chinese, pinyin), ...]
    
    if not CEDICT_FILE.exists():
        print(f"⚠️  CEDICT file not found: {CEDICT_FILE}")
        return cedict
    
    print(f"Loading CEDICT from {CEDICT_FILE.name}...")
    with open(CEDICT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            
            # Parse CEDICT format: 汉字 拼音 [english1/english2/...]
            # Example: 你好 ni3 hao3 [hello/good day]
            # Or: 熊猫 熊猫 [xiong2 mao1] /panda/
            match = re.match(r'(\S+)\s+(\S+)\s+\[(.*?)\]', line)
            if match:
                chinese = match.group(1)
                pinyin = match.group(2)
                english_str = match.group(3)
                
                # Split English definitions
                english_words = [e.strip().lower() for e in english_str.split('/')]
                
                for eng in english_words:
                    # Clean up English word (remove extra info in parentheses)
                    eng_clean = re.sub(r'\s*\([^)]*\)', '', eng).strip()
                    # Remove pinyin in brackets like [xiong2 mao1]
                    eng_clean = re.sub(r'\[.*?\]', '', eng_clean).strip()
                    if eng_clean:
                        cedict[eng_clean].append((chinese, pinyin))
    
    print(f"  Loaded {len(cedict)} English words from CEDICT")
    return cedict


def extract_english_words_from_apkg(apkg_path: Path):
    """Extract English words from Anki .apkg file"""
    words = set()
    
    if not apkg_path.exists():
        print(f"⚠️  File not found: {apkg_path}")
        return words
    
    print(f"Extracting words from {apkg_path.name}...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg (it's a zip file)
        with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir_path)
        
        # Open the SQLite database
        db_path = tmpdir_path / "collection.anki21"
        if not db_path.exists():
            db_path = tmpdir_path / "collection.anki2"
        
        if not db_path.exists():
            print(f"  ⚠️  No database found")
            return words
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all notes
        try:
            cursor.execute("SELECT flds FROM notes")
            for row in cursor.fetchall():
                fields = row[0].split('\x1f')  # Anki uses \x1f as field separator
                
                # Try to find English words in all fields
                for field in fields:
                    # Clean HTML
                    field = re.sub(r'<[^>]+>', '', field).strip()
                    field = field.replace('&nbsp;', ' ').strip()
                    
                    # Check if it looks like an English word
                    if field and re.match(r'^[a-zA-Z\s]+$', field):
                        # Split by spaces and take individual words
                        for word in field.split():
                            word = word.lower().strip('.,!?;:"()[]{}')
                            if len(word) > 1 and word.isalpha():
                                words.add(word)
        except Exception as e:
            print(f"  ⚠️  Error reading notes: {e}")
        
        conn.close()
    
    print(f"  ✅ Extracted {len(words)} unique words")
    return words


def normalize_syllable(syllable: str):
    """Normalize syllable for matching (remove tone, lowercase)"""
    # Just lowercase and strip - don't remove tone marks yet
    return syllable.lower().strip()


def split_pinyin_to_syllables(pinyin: str):
    """Split pinyin string into individual syllables"""
    # Remove tone numbers (1-5) but keep the base letters
    pinyin = re.sub(r'[1-5]', '', pinyin)
    # Split by spaces
    syllables = []
    for s in pinyin.split():
        s = s.strip()
        # Remove tone marks but keep letters
        s = re.sub(r'[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]', lambda m: {
            'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
            'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
            'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
            'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
            'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
            'ǖ': 'u', 'ǘ': 'u', 'ǚ': 'u', 'ǜ': 'u'
        }.get(m.group(0), m.group(0)), s)
        if s:
            syllables.append(s.lower())
    return syllables


def find_chinese_words_for_syllable(syllable: str, english_words: set, cedict: dict, limit=3):
    """
    Find Chinese words for a syllable by matching English vocabulary.
    Returns up to 3 suggestions.
    """
    suggestions = []
    syllable_normalized = normalize_syllable(syllable)
    seen_combinations = set()  # Avoid duplicates
    
    # For each English word in vocabulary decks
    for eng_word in sorted(english_words):
        if eng_word not in cedict:
            continue
        
        # Get all Chinese translations
        for chinese, pinyin in cedict[eng_word]:
            # Split pinyin into syllables
            pinyin_syllables = split_pinyin_to_syllables(pinyin)
            
            # Check if target syllable matches any syllable in this word
            if syllable_normalized in pinyin_syllables:
                # Create unique key
                key = (chinese, eng_word)
                if key not in seen_combinations:
                    seen_combinations.add(key)
                    suggestions.append({
                        'english': eng_word,
                        'chinese': chinese,
                        'pinyin': pinyin,
                        'matched_syllable': syllable_normalized
                    })
                    
                    if len(suggestions) >= limit:
                        return suggestions
    
    return suggestions[:limit]


def match_all_pending_syllables():
    """Match all pending syllables with English vocabulary"""
    print("=" * 80)
    print("Match Pending Syllables with English Vocabulary")
    print("=" * 80)
    print()
    
    # Load CEDICT
    cedict = load_cedict()
    print()
    
    # Extract English words from .apkg files
    all_english_words = set()
    for apkg_file in APKG_FILES:
        words = extract_english_words_from_apkg(apkg_file)
        all_english_words.update(words)
    print(f"\nTotal unique English words: {len(all_english_words)}")
    print()
    
    # Get pending syllables from API
    import requests
    try:
        response = requests.get('http://localhost:8000/pinyin/gap-fill-suggestions', timeout=10)
        api_data = response.json()
        
        pending = []
        for s in api_data['suggestions']:
            approved_val = s.get('approved', '')
            if not approved_val:  # Not approved (pending)
                syllable = s.get('Syllable', '').strip()
                word = s.get('Suggested Word', '').strip()
                if syllable and (word == 'NONE' or not word):
                    pending.append(s)
        
        print(f"Found {len(pending)} pending syllables")
        print()
        
        # Match each pending syllable
        matches = {}
        for item in pending:
            syllable = item.get('Syllable', '').strip()
            suggestions = find_chinese_words_for_syllable(
                syllable, all_english_words, cedict, limit=3
            )
            if suggestions:
                matches[syllable] = suggestions
        
        # Save to JSON for API
        output_file = PROJECT_ROOT / "data" / "pending_syllable_english_matches.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Matched {len(matches)} syllables")
        print(f"   Saved to: {output_file}")
        print()
        
        # Show summary
        print("Matches found:")
        for syllable, suggestions in sorted(matches.items()):
            print(f"  {syllable}: {len(suggestions)} suggestions")
            for i, sug in enumerate(suggestions, 1):
                print(f"    {i}. {sug['chinese']} ({sug['pinyin']}) - {sug['english']}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    match_all_pending_syllables()

