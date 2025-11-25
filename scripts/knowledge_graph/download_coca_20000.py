#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download COCA 20000 word list.

Attempts to download from wordfrequency.info or provides instructions
for manual download.

Sources:
- WordFrequency.info: https://www.wordfrequency.info/
- COCA: https://www.english-corpora.org/coca/
"""

import os
import sys
import csv
import requests
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
DATA_DIR = project_root / 'data' / 'content_db'
OUTPUT_CSV = DATA_DIR / 'coca_20000.csv'


def download_wordfrequency_sample():
    """
    Attempt to download from wordfrequency.info or alternative sources.
    
    Alternative sources:
    - GitHub: hermitdave/FrequencyWords (English frequency words)
    """
    print("Attempting to download from various sources...")
    
    # Try alternative sources first (public repositories)
    alt_urls = [
        {
            'url': 'https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2016/en/en_full.txt',
            'format': 'space_separated',  # "word frequency" format
            'name': 'GitHub FrequencyWords (English)'
        }
    ]
    
    for source in alt_urls:
        try:
            print(f"  Trying: {source['name']}")
            response = requests.get(source['url'], timeout=30)
            if response.status_code == 200 and len(response.text) > 10000:
                print(f"  ✅ Downloaded {len(response.text)} bytes")
                if source['format'] == 'space_separated':
                    return parse_space_separated_data(response.text)
                else:
                    return parse_wordfrequency_data(response.text)
        except Exception as e:
            print(f"  ⚠️  {source['name']}: {e}")
            continue
    
    # Try wordfrequency.info (may require purchase)
    wordfrequency_urls = [
        "https://www.wordfrequency.info/files/readable/lemmatized_tv.txt",
        "https://www.wordfrequency.info/files/coca20000.txt",
    ]
    
    for url in wordfrequency_urls:
        try:
            print(f"  Trying: {url}")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                if len(lines) > 100:
                    print(f"  ✅ Downloaded {len(lines)} words")
                    return parse_wordfrequency_data(response.text)
        except Exception as e:
            print(f"  ⚠️  {url}: {e}")
            continue
    
    return None


def parse_space_separated_data(text: str) -> list:
    """Parse space-separated format: 'word frequency'."""
    words = []
    lines = text.strip().split('\n')
    
    for i, line in enumerate(lines, 1):
        parts = line.strip().split()
        if len(parts) >= 2:
            word = parts[0].strip()
            freq_str = parts[1].strip().replace(',', '')
            try:
                frequency = int(freq_str)
                words.append({
                    'word': word,
                    'rank': i,
                    'frequency': frequency,
                    'pos': parts[2].strip() if len(parts) > 2 else ''
                })
                # Limit to top 20000
                if i >= 20000:
                    break
            except:
                continue
    
    return words


def parse_wordfrequency_data(text: str) -> list:
    """Parse wordfrequency.info format."""
    words = []
    lines = text.strip().split('\n')
    
    for i, line in enumerate(lines, 1):
        parts = line.strip().split('\t')
        if len(parts) >= 2:
            word = parts[0].strip()
            freq_str = parts[1].strip().replace(',', '')
            try:
                frequency = int(freq_str)
                words.append({
                    'word': word,
                    'rank': i,
                    'frequency': frequency,
                    'pos': parts[2].strip() if len(parts) > 2 else ''
                })
            except:
                continue
    
    return words


def create_coca_sample():
    """
    Create a sample COCA word list from common words.
    
    This is a placeholder - real COCA data should be downloaded manually.
    """
    # Top 1000 most common English words with estimated frequencies
    common_words = [
        ('the', 56271872), ('be', 28636776), ('and', 26877386), ('of', 26021939),
        ('a', 21306062), ('in', 19543136), ('to', 18317987), ('have', 15518822),
        ('it', 12330326), ('I', 12047621), ('that', 11860220), ('for', 11580668),
        ('you', 10951548), ('he', 10138669), ('with', 9740210), ('on', 9558612),
        ('do', 9200823), ('say', 9182692), ('this', 8923186), ('they', 8346521),
    ]
    
    words = []
    for rank, (word, freq) in enumerate(common_words, 1):
        words.append({
            'word': word,
            'rank': rank,
            'frequency': freq,
            'pos': ''
        })
    
    return words


def save_coca_csv(words: list, output_file: Path):
    """Save COCA words to CSV file."""
    if not words:
        return False
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['word', 'rank', 'frequency', 'pos'])
        writer.writeheader()
        writer.writerows(words)
    
    print(f"✅ Saved {len(words)} words to {output_file}")
    return True


def main():
    """Main function."""
    print("=" * 80)
    print("COCA 20000 Downloader")
    print("=" * 80)
    print()
    
    # Try to download
    print("1. Attempting to download from wordfrequency.info...")
    words = download_wordfrequency_sample()
    
    if not words or len(words) < 1000:
        print()
        print("⚠️  Download not available or insufficient data.")
        print()
        print("Please download COCA 20000 manually:")
        print("1. Visit: https://www.wordfrequency.info/sample.asp")
        print("2. Download the full 20,000 word list (CSV format)")
        print(f"3. Save as: {OUTPUT_CSV}")
        print()
        print("Expected CSV format:")
        print("  word,rank,frequency,pos")
        print("  the,1,56271872,det")
        print("  be,2,28636776,v")
        print()
        
        # Create small sample for testing
        print("Creating small sample file for testing...")
        sample = create_coca_sample()
        if save_coca_csv(sample, OUTPUT_CSV):
            print(f"✅ Created sample file with {len(sample)} words")
            print("   Replace with full COCA 20000 data when available")
    else:
        # Save downloaded data
        print(f"\n2. Saving {len(words)} words...")
        if save_coca_csv(words, OUTPUT_CSV):
            print()
            print("=" * 80)
            print("✅ Download complete!")
            print("=" * 80)
            print(f"\nYou can now run:")
            print(f"  python scripts/knowledge_graph/populate_english_vocab.py")


if __name__ == "__main__":
    main()

