#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download HSK vocabulary list from online sources.

This script attempts to download HSK vocabulary data or provides
instructions for manual download.
"""

import os
import sys
import csv
import json
import requests

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
DATA_DIR = os.path.join(project_root, 'data', 'content_db')
HSK_CSV = os.path.join(DATA_DIR, 'hsk_vocabulary.csv')

def download_hsk_from_github():
    """Try to download HSK vocabulary from common GitHub sources."""
    urls = [
        "https://raw.githubusercontent.com/kaisersparpick/HSK-Vocabulary-List/main/hsk_vocabulary.csv",
        "https://raw.githubusercontent.com/pwxcoo/chinese-xinhua/master/data/idiom.json",  # Alternative source
    ]
    
    for url in urls:
        try:
            print(f"Attempting to download from: {url}")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Try to parse as CSV
                content = response.text
                lines = content.strip().split('\n')
                if len(lines) > 1:
                    os.makedirs(DATA_DIR, exist_ok=True)
                    with open(HSK_CSV, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"✅ Successfully downloaded HSK vocabulary to: {HSK_CSV}")
                    return True
        except Exception as e:
            print(f"  Failed: {e}")
            continue
    
    return False

def create_hsk_template():
    """Create a template HSK CSV file with expected format."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    template = """word,traditional,pinyin,hsk_level
朋友,朋友,péngyou,1
学习,學習,xuéxí,1
老师,老師,lǎoshī,2
学校,學校,xuéxiào,2
"""
    
    with open(HSK_CSV, 'w', encoding='utf-8') as f:
        f.write(template)
    
    print(f"Created template HSK file: {HSK_CSV}")
    print("Please download HSK vocabulary from:")
    print("  - https://github.com/kaisersparpick/HSK-Vocabulary-List")
    print("  - https://github.com/duguyue/hsk")
    print("  - Or use any HSK 1-6 vocabulary list in CSV format")
    print(f"\nExpected CSV format:")
    print("  word,traditional,pinyin,hsk_level")
    print("  朋友,朋友,péngyou,1")

def check_complete_hsk_project():
    """Check if complete-hsk-vocabulary project is available."""
    complete_hsk_dir = "/Users/maxent/src/complete-hsk-vocabulary"
    complete_json = os.path.join(complete_hsk_dir, "complete.json")
    
    if os.path.exists(complete_json):
        print(f"✅ Found complete-hsk-vocabulary project at: {complete_hsk_dir}")
        print(f"   Use generate_hsk_csv.py to generate the CSV from this project.")
        return True
    return False

def main():
    """Main function to download or create HSK vocabulary."""
    print("=" * 80)
    print("HSK Vocabulary Downloader")
    print("=" * 80)
    print()
    
    if os.path.exists(HSK_CSV):
        print(f"✅ HSK vocabulary file already exists: {HSK_CSV}")
        print(f"   File size: {os.path.getsize(HSK_CSV)} bytes")
        return
    
    # Check for complete-hsk-vocabulary project first
    if check_complete_hsk_project():
        print("\n💡 Recommended: Use generate_hsk_csv.py to create CSV from complete-hsk-vocabulary")
        print("   This will generate a complete HSK 1-7 vocabulary list with pinyin and traditional forms.")
        print("\n   Run: python scripts/knowledge_graph/generate_hsk_csv.py")
        print("\n   Or continue with automatic download...")
        print()
    
    print("Attempting to download HSK vocabulary...")
    if download_hsk_from_github():
        return
    
    print("\n⚠️  Automatic download failed.")
    print("\n💡 Alternative options:")
    print("   1. Use generate_hsk_csv.py if you have complete-hsk-vocabulary project")
    print("   2. Manually download HSK vocabulary")
    print("\nCreating template file with instructions...")
    create_hsk_template()

if __name__ == "__main__":
    main()

