#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prefill mastered_english_words in profile based on words extracted from Anki packages.

This script:
1. Extracts English words from the two Anki .apkg files
2. Matches them to CEFR-J vocabulary to get canonical forms
3. Updates the profile's mastered_english_words field
"""

import os
import sys
import csv
import re
import sqlite3
import zipfile
import json
from collections import defaultdict
from pathlib import Path

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

# Configuration
DATA_DIR = os.path.join(project_root, 'data', 'content_db')
PROFILES_FILE = os.path.join(project_root, 'data', 'profiles', 'child_profiles.json')
CEFRJ_DIR = os.path.join(project_root, '..', 'olp-en-cefrj')
CEFRJ_VOCAB_CSV = os.path.join(CEFRJ_DIR, 'cefrj-vocabulary-profile-1.5.csv')
OCTANOVE_VOCAB_CSV = os.path.join(CEFRJ_DIR, 'octanove-vocabulary-profile-c1c2-1.0.csv')

# Anki package files
ANKI_PACKAGES = [
    os.path.join(DATA_DIR, 'English__Vocabulary__1. Basic.apkg'),
    os.path.join(DATA_DIR, 'English__Vocabulary__2. Level 2.apkg'),
]


def normalize_word(word):
    """Normalize word for matching (lowercase, remove punctuation)."""
    if not word:
        return None
    word = word.lower().strip()
    # Remove HTML tags
    word = re.sub(r'<[^>]+>', '', word)
    # Remove image tags
    word = re.sub(r'<img[^>]*>', '', word)
    # Remove common punctuation
    word = re.sub(r'[^\w\s-]', '', word)
    # Remove extra spaces
    word = re.sub(r'\s+', ' ', word).strip()
    return word if word else None


def extract_base_word(word):
    """Extract base form of word (simple stemming)."""
    if not word:
        return word
    
    word = word.lower()
    
    # Common suffixes to remove
    suffixes = [
        ('ies$', 'y'),
        ('ied$', 'y'),
        ('ing$', ''),
        ('ed$', ''),
        ('er$', ''),
        ('est$', ''),
        ('ly$', ''),
        ('s$', ''),
        ('es$', ''),
    ]
    
    for pattern, replacement in suffixes:
        if re.search(pattern, word):
            word = re.sub(pattern, replacement, word)
            break
    
    return word


def load_cefr_vocabulary():
    """Load CEFR-J vocabulary with word families and canonical forms."""
    cefr_map = {}  # normalized_word -> (canonical_word, cefr_level)
    word_families = defaultdict(set)  # base_word -> set of words
    
    # Load CEFR-J main vocabulary
    if os.path.exists(CEFRJ_VOCAB_CSV):
        with open(CEFRJ_VOCAB_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                headword = row.get('headword', '').strip()
                cefr = row.get('CEFR', '').strip()
                
                if headword and cefr:
                    # Handle variants like "catalog/catalogue"
                    variants = [v.strip() for v in headword.split('/')]
                    canonical = variants[0]  # Use first variant as canonical
                    base = extract_base_word(canonical)
                    
                    for variant in variants:
                        normalized = normalize_word(variant)
                        if normalized:
                            cefr_map[normalized] = (canonical, cefr)
                            word_families[base].add(normalized)
    
    # Load Octanove C1/C2 supplement
    if os.path.exists(OCTANOVE_VOCAB_CSV):
        with open(OCTANOVE_VOCAB_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                headword = row.get('headword', '').strip()
                cefr = row.get('CEFR', '').strip()
                
                if headword and cefr:
                    variants = [v.strip() for v in headword.split('/')]
                    canonical = variants[0]
                    base = extract_base_word(canonical)
                    
                    for variant in variants:
                        normalized = normalize_word(variant)
                        if normalized:
                            # Only add if not already in map (CEFR-J takes precedence)
                            if normalized not in cefr_map:
                                cefr_map[normalized] = (canonical, cefr)
                            word_families[base].add(normalized)
    
    return cefr_map, word_families


def extract_words_from_anki(apkg_path):
    """Extract English words from Anki package."""
    words = set()
    
    if not os.path.exists(apkg_path):
        print(f"⚠️  Package not found: {apkg_path}")
        return words
    
    temp_dir = os.path.join(project_root, 'temp_anki_extract', os.path.basename(apkg_path))
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Extract package
        with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find database file
        db_files = [
            os.path.join(temp_dir, 'collection.anki21'),
            os.path.join(temp_dir, 'collection.anki2'),
        ]
        
        db_path = None
        for db_file in db_files:
            if os.path.exists(db_file):
                db_path = db_file
                break
        
        if not db_path:
            print(f"  ⚠️  No database file found in {os.path.basename(apkg_path)}")
            return words
        
        # Read database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get models
        cursor.execute("SELECT models FROM col LIMIT 1")
        row = cursor.fetchone()
        if not row or not row[0]:
            conn.close()
            return words
        
        models_json = json.loads(row[0])
        model_fields = {}
        
        for model_id_str, model_data in models_json.items():
            fields = [fld.get('name', '') for fld in model_data.get('flds', [])]
            model_fields[int(model_id_str)] = fields
        
        # Get notes
        cursor.execute("SELECT mid, flds FROM notes")
        notes = cursor.fetchall()
        
        for mid, flds_str in notes:
            if not flds_str:
                continue
            
            fields = model_fields.get(mid, [])
            flds = flds_str.split('\x1f')
            
            # Extract words from all fields
            for field_value in flds:
                if not field_value:
                    continue
                
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', '', field_value)
                # Remove image tags
                text = re.sub(r'<img[^>]*>', '', text)
                
                # Extract English words (simple pattern: sequences of letters)
                english_words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
                
                for word in english_words:
                    normalized = normalize_word(word)
                    if normalized and len(normalized) >= 2:
                        words.add(normalized)
        
        conn.close()
        
    except Exception as e:
        print(f"  ❌ Error processing {os.path.basename(apkg_path)}: {e}")
    
    return words


def match_words_to_canonical(learned_words, cefr_map, word_families):
    """Match learned words to canonical CEFR vocabulary forms."""
    canonical_words = set()
    unmatched = set()
    
    for word in learned_words:
        normalized = normalize_word(word)
        if not normalized:
            continue
        
        # Direct match
        if normalized in cefr_map:
            canonical, _ = cefr_map[normalized]
            canonical_words.add(canonical.lower())
            continue
        
        # Try base form
        base = extract_base_word(normalized)
        if base in word_families:
            # Find any variant in the family that has a CEFR level
            found = False
            for variant in word_families[base]:
                if variant in cefr_map:
                    canonical, _ = cefr_map[variant]
                    canonical_words.add(canonical.lower())
                    found = True
                    break
            
            if not found:
                unmatched.add(word)
        else:
            unmatched.add(word)
    
    return canonical_words, unmatched


def main():
    """Main function to prefill mastered English words."""
    print("=" * 80)
    print("Prefill Mastered English Words from Anki Packages")
    print("=" * 80)
    print()
    
    # Load CEFR vocabulary
    print("Loading CEFR-J vocabulary...")
    cefr_map, word_families = load_cefr_vocabulary()
    print(f"  ✅ Loaded {len(cefr_map)} words with CEFR levels")
    print()
    
    # Extract words from Anki packages
    print("Extracting words from Anki packages...")
    all_learned_words = set()
    
    for apkg_path in ANKI_PACKAGES:
        package_name = os.path.basename(apkg_path)
        print(f"  Processing {package_name}...")
        words = extract_words_from_anki(apkg_path)
        print(f"    ✅ Extracted {len(words)} unique words")
        all_learned_words.update(words)
    
    print(f"\n  Total unique words learned: {len(all_learned_words)}")
    print()
    
    # Match to canonical CEFR forms
    print("Matching words to CEFR vocabulary...")
    canonical_words, unmatched = match_words_to_canonical(all_learned_words, cefr_map, word_families)
    print(f"  ✅ Matched {len(canonical_words)} words to CEFR vocabulary")
    print(f"  ⚠️  {len(unmatched)} words not found in CEFR-J vocabulary")
    print()
    
    # Sort canonical words for consistent output
    sorted_words = sorted(canonical_words)
    mastered_words_string = ', '.join(sorted_words)
    
    print(f"Canonical words to save: {len(sorted_words)}")
    print(f"Sample: {sorted_words[:10]}")
    print()
    
    # Load profiles
    if not os.path.exists(PROFILES_FILE):
        print(f"❌ Profiles file not found: {PROFILES_FILE}")
        sys.exit(1)
    
    print(f"Loading profiles from: {PROFILES_FILE}")
    with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    if not profiles:
        print("❌ No profiles found in file")
        sys.exit(1)
    
    # Update first profile (or ask which one?)
    print(f"\nFound {len(profiles)} profile(s)")
    if len(profiles) > 1:
        print("Updating first profile. If you want to update a different one, specify the profile name.")
        print("Profiles:", [p.get('name', 'unnamed') for p in profiles])
    
    profile = profiles[0]
    profile_name = profile.get('name', 'unnamed')
    
    print(f"\nUpdating profile: {profile_name}")
    print(f"  Current mastered_english_words: {len(profile.get('mastered_english_words', '').split(',')) if profile.get('mastered_english_words') else 0} words")
    
    # Update profile
    profile['mastered_english_words'] = mastered_words_string
    
    # Save profiles
    with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ Updated to {len(sorted_words)} words")
    print()
    print("=" * 80)
    print("✅ Profile updated successfully!")
    print("=" * 80)
    print(f"\nThe profile '{profile_name}' now has {len(sorted_words)} mastered English words.")
    print("You can now open the English Words Manager in the UI to see them pre-selected.")


if __name__ == "__main__":
    main()

