#!/usr/bin/env python3
"""
Recover English words from .apkg files
"""

import json
import sqlite3
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Set

project_root = Path(__file__).resolve().parent.parent.parent

APKG_FILES = [
    project_root / "data" / "content_db" / "English__Vocabulary__1. Basic.apkg",
    project_root / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"
]

PROFILE_FILE = project_root / "data" / "profiles" / "child_profiles.json"

def is_english_word(text: str) -> bool:
    """Check if text is a valid English word or phrase"""
    import re
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    text = text.strip()
    
    # Skip if empty
    if not text:
        return False
    
    # Skip if contains Chinese characters
    if re.search(r'[\u4e00-\u9fff]', text):
        return False
    
    # Skip if contains sound tags
    if '[sound:' in text.lower():
        return False
    
    # Skip if contains => (translation indicator)
    if '=>' in text or '=&gt;' in text:
        return False
    
    # Skip if too long (likely a sentence)
    if len(text) > 100:
        return False
    
    # Must contain at least one letter
    if not re.search(r'[a-zA-Z]', text):
        return False
    
    # Skip if it's a question or prompt
    if text.endswith('?') or text.startswith('Synonym to') or text.startswith('A ___ of'):
        return False
    
    return True

def extract_words_from_apkg(apkg_path: Path) -> Set[str]:
    """Extract all English words from an .apkg file"""
    words = set()
    
    print(f"\n📦 Processing: {apkg_path.name}")
    
    # Create temporary directory
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
            print(f"  ⚠️  No database found in {apkg_path.name}")
            return words
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all notes (simple query that works with all Anki versions)
        cursor.execute("SELECT flds FROM notes")
        
        for row in cursor.fetchall():
            fields = row[0].split('\x1f')  # Anki uses \x1f as field separator
            
            # Try to find English words in all fields
            for field in fields:
                field = field.strip()
                
                if is_english_word(field):
                    # Clean up HTML entities
                    import html
                    field = html.unescape(field)
                    words.add(field)
        
        conn.close()
    
    print(f"  ✅ Extracted {len(words)} words")
    return words

def main():
    print("=" * 80)
    print("Recovering English Words from Anki Packages")
    print("=" * 80)
    
    all_words = set()
    
    # Extract from both .apkg files
    for apkg_file in APKG_FILES:
        if apkg_file.exists():
            words = extract_words_from_apkg(apkg_file)
            all_words.update(words)
        else:
            print(f"⚠️  File not found: {apkg_file}")
    
    print(f"\n📊 Total unique English words: {len(all_words)}")
    
    # Sort words for consistent ordering
    sorted_words = sorted(all_words)
    
    # Load current profile
    with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    # Update the first profile
    profile = profiles[0]
    
    # Convert to comma-separated string
    mastered_english_words_str = ", ".join(sorted_words)
    
    profile['mastered_english_words'] = mastered_english_words_str
    
    # Save back
    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Updated profile with {len(sorted_words)} English words")
    print(f"📝 Saved to: {PROFILE_FILE}")
    
    # Show sample
    print(f"\nSample words (first 20):")
    for word in sorted_words[:20]:
        print(f"  - {word}")

if __name__ == "__main__":
    main()

