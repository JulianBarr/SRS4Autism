#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze English vocabulary learned from Anki packages and compare with CEFR levels.

This script:
1. Extracts English words from the two Anki .apkg files
2. Matches them against CEFR-J vocabulary to get CEFR levels
3. Groups by word families (base forms)
4. Generates statistics comparing learned words vs overall CEFR distribution
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
    """Load CEFR-J vocabulary with word families."""
    cefr_map = {}  # word -> cefr_level
    word_families = defaultdict(set)  # base_word -> set of words
    
    # Load CEFR-J main vocabulary
    if os.path.exists(CEFRJ_VOCAB_CSV):
        with open(CEFRJ_VOCAB_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                headword = row.get('headword', '').strip()
                cefr_level = row.get('CEFR', '').strip()
                
                if headword and cefr_level:
                    # Handle variants like "catalog/catalogue"
                    variants = [v.strip() for v in headword.split('/')]
                    base = extract_base_word(variants[0])
                    
                    for variant in variants:
                        normalized = normalize_word(variant)
                        if normalized:
                            cefr_map[normalized] = cefr_level
                            word_families[base].add(normalized)
    
    # Load Octanove C1/C2 supplement
    if os.path.exists(OCTANOVE_VOCAB_CSV):
        with open(OCTANOVE_VOCAB_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                headword = row.get('headword', '').strip()
                cefr_level = row.get('CEFR', '').strip()
                
                if headword and cefr_level:
                    variants = [v.strip() for v in headword.split('/')]
                    base = extract_base_word(variants[0])
                    
                    for variant in variants:
                        normalized = normalize_word(variant)
                        if normalized:
                            # Only add if not already in map (CEFR-J takes precedence)
                            if normalized not in cefr_map:
                                cefr_map[normalized] = cefr_level
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
                # This is a basic extraction - you might want to improve it
                english_words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
                
                for word in english_words:
                    normalized = normalize_word(word)
                    if normalized and len(normalized) >= 2:
                        words.add(normalized)
        
        conn.close()
        
    except Exception as e:
        print(f"  ❌ Error processing {os.path.basename(apkg_path)}: {e}")
    
    return words


def match_words_to_cefr(learned_words, cefr_map, word_families):
    """Match learned words to CEFR levels, including word family matching."""
    matched = {}  # word -> cefr_level
    unmatched = set()
    
    for word in learned_words:
        normalized = normalize_word(word)
        if not normalized:
            continue
        
        # Direct match
        if normalized in cefr_map:
            matched[word] = cefr_map[normalized]
            continue
        
        # Try base form
        base = extract_base_word(normalized)
        if base in word_families:
            # Find any variant in the family that has a CEFR level
            for variant in word_families[base]:
                if variant in cefr_map:
                    matched[word] = cefr_map[variant]
                    break
            
            if word not in matched:
                unmatched.add(word)
        else:
            unmatched.add(word)
    
    return matched, unmatched


def main():
    """Main analysis function."""
    print("=" * 80)
    print("English Vocabulary CEFR Analysis")
    print("=" * 80)
    print()
    
    # Load CEFR vocabulary
    print("Loading CEFR-J vocabulary...")
    cefr_map, word_families = load_cefr_vocabulary()
    print(f"  ✅ Loaded {len(cefr_map)} words with CEFR levels")
    print(f"  ✅ Found {len(word_families)} word families")
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
    
    # Match to CEFR levels
    print("Matching words to CEFR levels...")
    matched, unmatched = match_words_to_cefr(all_learned_words, cefr_map, word_families)
    print(f"  ✅ Matched {len(matched)} words to CEFR levels")
    print(f"  ⚠️  {len(unmatched)} words not found in CEFR-J vocabulary")
    print()
    
    # Calculate statistics
    cefr_counts = defaultdict(int)
    for word, level in matched.items():
        cefr_counts[level] += 1
    
    # Overall CEFR distribution
    overall_cefr = defaultdict(int)
    for level in cefr_map.values():
        overall_cefr[level] += 1
    
    # Print statistics
    print("=" * 80)
    print("CEFR Level Distribution - Learned Words")
    print("=" * 80)
    print()
    
    total_matched = len(matched)
    if total_matched > 0:
        print(f"{'Level':<6} {'Count':<8} {'Percentage':<12} {'Bar Chart'}")
        print("-" * 80)
        
        for level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
            count = cefr_counts.get(level, 0)
            pct = (count / total_matched * 100) if total_matched > 0 else 0
            bar_length = int(pct / 2)  # Scale bar to 50 chars max
            bar = '█' * bar_length
            print(f"{level:<6} {count:<8} {pct:>6.1f}%      {bar}")
        
        print()
        print(f"Total matched: {total_matched} words")
        print(f"Unmatched: {len(unmatched)} words")
        print()
    
    # Overall CEFR distribution for comparison
    print("=" * 80)
    print("CEFR Level Distribution - Overall CEFR-J Vocabulary")
    print("=" * 80)
    print()
    
    total_overall = sum(overall_cefr.values())
    if total_overall > 0:
        print(f"{'Level':<6} {'Count':<8} {'Percentage':<12} {'Bar Chart'}")
        print("-" * 80)
        
        for level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
            count = overall_cefr.get(level, 0)
            pct = (count / total_overall * 100) if total_overall > 0 else 0
            bar_length = int(pct / 2)
            bar = '█' * bar_length
            print(f"{level:<6} {count:<8} {pct:>6.1f}%      {bar}")
        
        print()
        print(f"Total vocabulary: {total_overall} words")
        print()
    
    # Comparison
    print("=" * 80)
    print("Comparison: Learned vs Overall")
    print("=" * 80)
    print()
    
    print(f"{'Level':<6} {'Learned %':<12} {'Overall %':<12} {'Difference':<12}")
    print("-" * 80)
    
    for level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
        learned_pct = (cefr_counts.get(level, 0) / total_matched * 100) if total_matched > 0 else 0
        overall_pct = (overall_cefr.get(level, 0) / total_overall * 100) if total_overall > 0 else 0
        diff = learned_pct - overall_pct
        diff_str = f"{diff:+.1f}%"
        print(f"{level:<6} {learned_pct:>6.1f}%      {overall_pct:>6.1f}%      {diff_str:>10}")
    
    print()
    
    # Word families
    print("=" * 80)
    print("Word Families Analysis")
    print("=" * 80)
    print()
    
    learned_families = defaultdict(set)
    for word in matched.keys():
        base = extract_base_word(normalize_word(word))
        if base in word_families:
            learned_families[base].add(word)
    
    print(f"Unique word families learned: {len(learned_families)}")
    print(f"Average words per family: {sum(len(family) for family in learned_families.values()) / len(learned_families) if learned_families else 0:.1f}")
    print()
    
    # Sample unmatched words
    if unmatched:
        print("=" * 80)
        print("Sample Unmatched Words (first 20)")
        print("=" * 80)
        print()
        sample = sorted(list(unmatched))[:20]
        for word in sample:
            print(f"  - {word}")
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more")
        print()
    
    print("=" * 80)
    print("Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()

