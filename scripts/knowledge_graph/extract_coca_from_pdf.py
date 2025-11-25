#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract COCA 20000 word list from PDF.

Extracts word frequency data from the Word Frequency List of American English PDF
and converts it to CSV format.

Usage:
    python extract_coca_from_pdf.py
"""

import os
import sys
import csv
import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber is not installed.")
    print("Please install it with: pip install pdfplumber")
    sys.exit(1)

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Configuration
PDF_FILE = project_root / 'data' / 'content_db' / 'Word_Frequency_List_of_American_English_20000.pdf'
OUTPUT_CSV = project_root / 'data' / 'content_db' / 'coca_20000.csv'

# POS abbreviations mapping (common in frequency lists)
POS_MAP = {
    'n': 'noun', 'v': 'verb', 'j': 'adjective', 'r': 'adverb',
    'c': 'conjunction', 'i': 'preposition', 'd': 'determiner',
    'm': 'number', 'e': 'pronoun', 'p': 'pronoun'
}


def extract_words_from_pdf(pdf_path: Path) -> list:
    """
    Extract word frequency data from PDF.
    
    Returns:
        List of dicts with word, rank, frequency, pos
    """
    words = []
    word_set = set()  # Track unique words by rank
    
    print(f"Extracting words from PDF: {pdf_path.name}")
    print(f"  File size: {pdf_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"  Total pages: {total_pages}")
        print()
        
        # Skip first few pages (title/header)
        start_page = 5
        
        for page_num in range(start_page, total_pages):
            if page_num % 100 == 0:
                print(f"  Processing page {page_num + 1}/{total_pages}... (found {len(words)} words so far)", flush=True)
            
            page = pdf.pages[page_num]
            text = page.extract_text()
            
            if not text:
                continue
            
            # Pattern: "rank word pos" or "rank word pos next_rank next_word next_pos"
            # e.g., "107 even r 114 life n" - two entries on one line
            # e.g., "361067 | 0.98" - frequency appears later
            # Try to find word entries with rank and POS
            
            # Pattern 1: "rank word pos" format (can have multiple on same line)
            # Match: number word single_letter (POS) optionally followed by another number
            pattern1 = r'(\d+)\s+([a-z]+(?:[-\'][a-z]+)*)\s+([a-z])(?:\s+\d+)?'
            matches1 = re.findall(pattern1, text, re.IGNORECASE)
            
            for match in matches1:
                rank_str, word, pos = match
                rank = int(rank_str)
                word = word.strip().lower()
                pos = pos.lower()
                
                # Skip if we already have this rank
                if rank in word_set:
                    continue
                
                # Skip common non-word patterns
                if word in ['noun', 'verb', 'adj', 'adv', 'prep', 'conj', 'pron']:
                    continue
                if len(word) < 1 or not word[0].isalpha():
                    continue
                
                # Look for frequency later in text (pattern: "frequency | dispersion")
                # Search in a window around this match
                match_pos = text.find(rank_str + ' ' + word)
                if match_pos >= 0:
                    window = text[max(0, match_pos-200):min(len(text), match_pos+1000)]
                    freq_pattern = r'(\d{4,})\s*\|\s*0\.\d+'
                    freq_matches = re.findall(freq_pattern, window)
                    frequency = int(freq_matches[0].replace(',', '')) if freq_matches else None
                else:
                    frequency = None
                
                # Expand POS abbreviation
                pos_full = POS_MAP.get(pos, pos)
                
                words.append({
                    'word': word,
                    'rank': rank,
                    'frequency': frequency,
                    'pos': pos_full
                })
                word_set.add(rank)
            
            # Pattern 2: Sometimes format is "rank. word pos"
            pattern2 = r'(\d+)\.\s+([a-z]+(?:[-\'][a-z]+)*)\s+([a-z])'
            matches2 = re.findall(pattern2, text, re.IGNORECASE)
            
            for match in matches2:
                rank_str, word, pos = match
                rank = int(rank_str)
                word = word.strip().lower()
                pos = pos.lower()
                
                # Skip if we already have this rank
                if rank in word_set:
                    continue
                
                # Skip common non-word patterns
                if word in ['noun', 'verb', 'adj', 'adv', 'prep', 'conj', 'pron']:
                    continue
                if len(word) < 1 or not word[0].isalpha():
                    continue
                
                pos_full = POS_MAP.get(pos, pos)
                
                words.append({
                    'word': word,
                    'rank': rank,
                    'frequency': None,
                    'pos': pos_full
                })
                word_set.add(rank)
            
            # Stop if we have 20,000 words
            if len(words) >= 20000:
                break
    
    # Sort by rank to ensure order
    words.sort(key=lambda x: x['rank'])
    
    print(f"\n✅ Extracted {len(words)} words from PDF")
    return words


def save_coca_csv(words: list, output_file: Path):
    """Save COCA words to CSV file."""
    if not words:
        print("❌ No words to save")
        return False
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Backup existing file if it exists
    if output_file.exists():
        backup = output_file.with_suffix('.csv.backup')
        output_file.rename(backup)
        print(f"  📦 Backed up existing file to {backup.name}")
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['word', 'rank', 'frequency', 'pos'])
        writer.writeheader()
        writer.writerows(words)
    
    print(f"✅ Saved {len(words)} words to {output_file}")
    return True


def main():
    """Main function."""
    print("=" * 80)
    print("Extract COCA 20000 from PDF")
    print("=" * 80)
    print()
    
    if not PDF_FILE.exists():
        print(f"❌ PDF file not found: {PDF_FILE}")
        print(f"   Expected location: data/content_db/Word_Frequency_List_of_American_English_20000.pdf")
        sys.exit(1)
    
    # Extract words from PDF
    words = extract_words_from_pdf(PDF_FILE)
    
    if not words:
        print("\n❌ Failed to extract words from PDF")
        print("   The PDF format may be different than expected")
        sys.exit(1)
    
    # Show sample
    print("\nSample extracted words:")
    print("-" * 80)
    for word in words[:10]:
        freq_str = f", frequency: {word['frequency']:,}" if word['frequency'] else ""
        print(f"  Rank {word['rank']:5d}: {word['word']:20s} ({word['pos']:10s}{freq_str})")
    print()
    
    # Check rank coverage
    ranks = [w['rank'] for w in words]
    print(f"Rank coverage: {min(ranks)} - {max(ranks)}")
    print(f"Missing ranks: {len([i for i in range(1, max(ranks) + 1) if i not in ranks])}")
    print()
    
    # Save to CSV
    print("Saving to CSV...")
    if save_coca_csv(words, OUTPUT_CSV):
        print()
        print("=" * 80)
        print("✅ Complete!")
        print("=" * 80)
        print(f"\nYou can now run:")
        print(f"  python scripts/knowledge_graph/populate_english_vocab.py")


if __name__ == "__main__":
    main()

