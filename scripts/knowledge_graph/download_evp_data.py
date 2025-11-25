#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script to download or prepare EVP (English Vocabulary Profile) data.

This script attempts to download EVP data from various sources or provides
instructions for manual download.

Sources:
- English Profile website: https://www.englishprofile.org/wordlists
- CEFRLex project: https://cental.uclouvain.be/cefrlex/
- Cambridge English word lists
"""

import os
import sys
import csv
import json
import requests
from urllib.parse import urljoin

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
DATA_DIR = os.path.join(project_root, 'data', 'content_db')
OUTPUT_CSV = os.path.join(DATA_DIR, 'english_vocab_evp.csv')
OUTPUT_JSON = os.path.join(DATA_DIR, 'english_vocab_evp.json')


def download_cefrlex():
    """
    Attempt to download from CEFRLex project.
    
    Note: This is a placeholder - actual implementation would need
    to parse the CEFRLex database format.
    """
    print("ℹ️  CEFRLex download not yet implemented.")
    print("   CEFRLex is available at: https://cental.uclouvain.be/cefrlex/")
    print("   You may need to contact the project for data access.")
    return []


def create_sample_from_common_words():
    """
    Create a sample vocabulary list from common English words with CEFR estimates.
    
    This is a placeholder that creates a small sample. In production, you would
    download the full EVP dataset.
    """
    # Common A1-A2 words with estimated CEFR levels
    sample_words = [
        # A1 - Basic words
        {"word": "cat", "definition": "a small domesticated carnivorous mammal", "cefr_level": "A1", "pos": "noun", "concreteness": 4.8},
        {"word": "dog", "definition": "a domesticated carnivorous mammal", "cefr_level": "A1", "pos": "noun", "concreteness": 4.9},
        {"word": "house", "definition": "a building for human habitation", "cefr_level": "A1", "pos": "noun", "concreteness": 5.0},
        {"word": "book", "definition": "a written or printed work consisting of pages", "cefr_level": "A1", "pos": "noun", "concreteness": 4.2},
        {"word": "water", "definition": "a colorless, transparent, odorless liquid", "cefr_level": "A1", "pos": "noun", "concreteness": 5.0},
        {"word": "food", "definition": "any nutritious substance that people eat", "cefr_level": "A1", "pos": "noun", "concreteness": 4.5},
        {"word": "friend", "definition": "a person whom one knows and with whom one has a bond", "cefr_level": "A1", "pos": "noun", "concreteness": 3.2},
        {"word": "happy", "definition": "feeling or showing pleasure or contentment", "cefr_level": "A1", "pos": "adjective", "concreteness": 2.8},
        {"word": "big", "definition": "of considerable size or extent", "cefr_level": "A1", "pos": "adjective", "concreteness": 4.1},
        {"word": "small", "definition": "of a size that is less than normal or usual", "cefr_level": "A1", "pos": "adjective", "concreteness": 4.0},
        {"word": "run", "definition": "move at a speed faster than a walk", "cefr_level": "A1", "pos": "verb", "concreteness": 3.5},
        {"word": "walk", "definition": "move at a regular pace by lifting and setting down each foot", "cefr_level": "A1", "pos": "verb", "concreteness": 4.2},
        {"word": "eat", "definition": "put food into the mouth and chew and swallow it", "cefr_level": "A1", "pos": "verb", "concreteness": 4.5},
        {"word": "drink", "definition": "take a liquid into the mouth and swallow", "cefr_level": "A1", "pos": "verb", "concreteness": 4.3},
        {"word": "see", "definition": "perceive with the eyes", "cefr_level": "A1", "pos": "verb", "concreteness": 3.8},
        # A2 - Elementary
        {"word": "beautiful", "definition": "pleasing the senses or mind aesthetically", "cefr_level": "A2", "pos": "adjective", "concreteness": 2.5},
        {"word": "difficult", "definition": "requiring much effort or skill to accomplish", "cefr_level": "A2", "pos": "adjective", "concreteness": 1.8},
        {"word": "important", "definition": "of great significance or value", "cefr_level": "A2", "pos": "adjective", "concreteness": 1.5},
        {"word": "understand", "definition": "perceive the intended meaning of", "cefr_level": "A2", "pos": "verb", "concreteness": 1.2},
        {"word": "remember", "definition": "have in or be able to bring to one's mind", "cefr_level": "A2", "pos": "verb", "concreteness": 1.0},
    ]
    
    return sample_words


def save_to_csv(words, output_file):
    """Save words to CSV file."""
    if not words:
        print("⚠️  No words to save.")
        return False
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['word', 'definition', 'cefr_level', 'pos', 'concreteness']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(words)
    
    print(f"✅ Saved {len(words)} words to {output_file}")
    return True


def save_to_json(words, output_file):
    """Save words to JSON file."""
    if not words:
        print("⚠️  No words to save.")
        return False
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(words, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(words)} words to {output_file}")
    return True


def main():
    """Main function."""
    print("=" * 80)
    print("EVP Data Downloader/Preparer")
    print("=" * 80)
    print()
    
    print("Attempting to download EVP data...")
    print()
    
    # Try different sources
    words = []
    
    # Option 1: Try CEFRLex
    print("1. Trying CEFRLex...")
    cefrlex_words = download_cefrlex()
    if cefrlex_words:
        words.extend(cefrlex_words)
        print(f"   ✅ Downloaded {len(cefrlex_words)} words from CEFRLex")
    else:
        print("   ⚠️  CEFRLex download not available")
    print()
    
    # Option 2: Create sample if no data downloaded
    if not words:
        print("2. Creating sample vocabulary list...")
        sample_words = create_sample_from_common_words()
        words.extend(sample_words)
        print(f"   ✅ Created {len(sample_words)} sample words")
        print("   ⚠️  This is a small sample. For full EVP data:")
        print("      - Visit https://www.englishprofile.org/wordlists")
        print("      - Download the EVP dataset")
        print("      - Convert to CSV/JSON format with columns: word, definition, cefr_level, pos")
        print()
    
    # Save to files
    if words:
        print("Saving data...")
        save_to_csv(words, OUTPUT_CSV)
        save_to_json(words, OUTPUT_JSON)
        print()
        print("=" * 80)
        print("✅ Data preparation complete!")
        print("=" * 80)
        print(f"\nYou can now run:")
        print(f"  python scripts/knowledge_graph/populate_english_vocab.py")
    else:
        print("❌ No data available. Please download EVP data manually.")


if __name__ == "__main__":
    main()

