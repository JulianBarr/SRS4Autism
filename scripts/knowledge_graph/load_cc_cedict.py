#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load CC-CEDICT dictionary data for Chinese-to-English translation lookup.

CC-CEDICT format (each line):
Traditional Simplified [pinyin] /English translation 1/English translation 2/.../

Example:
中國 中国 [Zhong1 guo2] /China/Middle Kingdom/
"""

import os
import sys
import re
from pathlib import Path
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def parse_cedict_line(line):
    """
    Parse a single line from CC-CEDICT dictionary.
    
    Format: Traditional Simplified [pinyin] /def1/def2/.../
    
    Returns: dict with 'traditional', 'simplified', 'pinyin', 'definitions'
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Pattern: traditional simplified [pinyin] /def1/def2/.../
    # Match: traditional, simplified, pinyin (optional), definitions
    pattern = r'^(\S+)\s+(\S+)\s+(?:\[([^\]]+)\]\s+)?(/.+)$'
    match = re.match(pattern, line)
    
    if not match:
        return None
    
    traditional = match.group(1)
    simplified = match.group(2)
    pinyin = match.group(3) if match.group(3) else None
    definitions_str = match.group(4)
    
    # Extract definitions (between / and /)
    definitions = []
    if definitions_str:
        # Remove leading and trailing /
        definitions_str = definitions_str.strip('/')
        # Split by / and filter empty
        definitions = [d.strip() for d in definitions_str.split('/') if d.strip()]
    
    return {
        'traditional': traditional,
        'simplified': simplified,
        'pinyin': pinyin,
        'definitions': definitions
    }


def load_cedict_file(file_path):
    """
    Load CC-CEDICT dictionary from a text file.
    
    Returns: dict mapping simplified Chinese -> list of entries
    """
    if not os.path.exists(file_path):
        print(f"⚠️  CC-CEDICT file not found: {file_path}")
        return {}
    
    import sys
    print(f"Loading CC-CEDICT from: {file_path}", flush=True)
    sys.stdout.flush()
    entries = defaultdict(list)
    count = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                entry = parse_cedict_line(line)
                if entry:
                    # Index by simplified (most common)
                    entries[entry['simplified']].append(entry)
                    # Also index by traditional for lookup
                    if entry['traditional'] != entry['simplified']:
                        entries[entry['traditional']].append(entry)
                    count += 1
                    
                    if count % 10000 == 0:
                        print(f"  Loaded {count} entries...", flush=True)
                        sys.stdout.flush()
        
        print(f"✅ Loaded {count} entries from CC-CEDICT", flush=True)
        sys.stdout.flush()
        return dict(entries)
    except Exception as e:
        print(f"❌ Error loading CC-CEDICT: {e}")
        return {}


def get_english_translations(cedict_data, chinese_word):
    """
    Get English translations for a Chinese word from CC-CEDICT.
    
    Args:
        cedict_data: Dictionary from load_cedict_file()
        chinese_word: Chinese word (simplified or traditional)
    
    Returns: List of English translation strings
    """
    if not cedict_data or not chinese_word:
        return []
    
    entries = cedict_data.get(chinese_word, [])
    translations = []
    
    for entry in entries:
        translations.extend(entry.get('definitions', []))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_translations = []
    for trans in translations:
        if trans.lower() not in seen:
            seen.add(trans.lower())
            unique_translations.append(trans)
    
    return unique_translations


def find_cedict_file():
    """
    Try to find CC-CEDICT file in common locations.
    
    Returns: Path to CC-CEDICT file or None
    """
    # Common locations
    possible_paths = [
        # User's specified location
        project_root / 'data' / 'content_db' / 'cedict_1_0_ts_utf-8_mdbg.txt',
        # Standard CC-CEDICT download location
        Path.home() / 'Downloads' / 'cedict_ts.u8',
        # Project data directory
        project_root / 'data' / 'cedict_ts.u8',
        # CC-CEDICT directory
        Path('/Users/maxent/src/cc-cedict-1.0.3') / 'cedict_ts.u8',
        # Alternative names
        project_root / 'data' / 'cc-cedict.txt',
        project_root / 'data' / 'cedict_ts.u8',
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


if __name__ == "__main__":
    # Test loading
    cedict_file = find_cedict_file()
    if cedict_file:
        data = load_cedict_file(cedict_file)
        # Test lookup
        test_words = ['朋友', '猫', '吃', '中国']
        print("\nTest lookups:")
        for word in test_words:
            translations = get_english_translations(data, word)
            print(f"  {word}: {translations[:3]}")  # Show first 3
    else:
        print("⚠️  CC-CEDICT file not found.")
        print("   Please download from: https://www.mdbg.net/chinese/dictionary?page=cc-cedict")
        print("   Save as: cedict_ts.u8")

