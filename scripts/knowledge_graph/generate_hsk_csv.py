#!/usr/bin/env python3
"""
Generate HSK vocabulary CSV from complete-hsk-vocabulary JSON files.

This script reads all HSK level JSON files and generates a CSV file
with columns: word,traditional,pinyin,hsk_level
"""

import json
import os
import csv
from pathlib import Path
from collections import defaultdict

# Path to the complete-hsk-vocabulary project
HSK_PROJECT_DIR = Path("/Users/maxent/src/complete-hsk-vocabulary")
OUTPUT_CSV = Path("/Users/maxent/src/SRS4Autism/data/content_db/hsk_vocabulary.csv")

def extract_hsk_level(level_list):
    """
    Extract the lowest new HSK level from a level list.
    Example: ["new-1", "old-3"] -> 1
    Example: ["new-6"] -> 6
    Example: ["new-7+"] -> 7
    """
    new_levels = []
    for level in level_list:
        if level.startswith("new-"):
            level_str = level.replace("new-", "").replace("+", "")  # Handle "new-7+"
            try:
                new_levels.append(int(level_str))
            except ValueError:
                continue
    if new_levels:
        return min(new_levels)  # Return the lowest (earliest) level
    return None

def load_hsk_data():
    """
    Load HSK data from complete.json (which has level information).
    Returns a dictionary: {word: {'traditional': ..., 'pinyin': ..., 'hsk_level': ...}}
    """
    hsk_data = {}
    
    complete_json = HSK_PROJECT_DIR / "complete.json"
    
    if not complete_json.exists():
        print(f"❌ Error: {complete_json} not found!")
        return hsk_data
    
    print(f"📖 Loading HSK data from {complete_json.name}...")
    
    try:
        with open(complete_json, 'r', encoding='utf-8') as f:
            words = json.load(f)
        
        print(f"   Found {len(words)} words in complete.json")
        
        for word_entry in words:
            simplified = word_entry.get('simplified', '')
            if not simplified:
                continue
            
            # Get level information
            levels = word_entry.get('level', [])
            hsk_level = extract_hsk_level(levels)
            
            # Get forms (traditional and pinyin)
            forms = word_entry.get('forms', [])
            if not forms:
                continue
            
            # Use the first form (most common)
            first_form = forms[0]
            traditional = first_form.get('traditional', simplified)  # Fallback to simplified if no traditional
            
            transcriptions = first_form.get('transcriptions', {})
            pinyin = transcriptions.get('pinyin', '')
            
            # Skip if no pinyin
            if not pinyin:
                continue
            
            # Store the data
            hsk_data[simplified] = {
                'traditional': traditional,
                'pinyin': pinyin,
                'hsk_level': hsk_level
            }
    
    except Exception as e:
        print(f"❌ Error processing {complete_json}: {e}")
        import traceback
        traceback.print_exc()
    
    return hsk_data

def write_csv(hsk_data, output_file):
    """
    Write HSK data to CSV file.
    """
    print(f"\n📝 Writing CSV to {output_file}...")
    
    # Sort by HSK level, then by word
    sorted_items = sorted(
        hsk_data.items(),
        key=lambda x: (x[1]['hsk_level'] or 999, x[0])
    )
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['word', 'traditional', 'pinyin', 'hsk_level'])
        
        # Write data
        count = 0
        for word, data in sorted_items:
            # Skip entries without pinyin (incomplete data)
            if not data['pinyin']:
                continue
            
            writer.writerow([
                word,
                data['traditional'],
                data['pinyin'],
                data['hsk_level'] or ''
            ])
            count += 1
    
    print(f"✅ Successfully wrote {count} entries to {output_file}")
    
    # Print statistics
    level_counts = defaultdict(int)
    for data in hsk_data.values():
        level = data['hsk_level']
        if level:
            level_counts[level] += 1
        else:
            level_counts[0] += 1
    
    print(f"\n📊 Statistics:")
    for level in sorted(level_counts.keys()):
        if level == 0:
            print(f"   Level unknown: {level_counts[level]} words")
        else:
            print(f"   HSK {level}: {level_counts[level]} words")
    print(f"   Total: {count} words (with pinyin)")

def main():
    print("=" * 70)
    print("HSK Vocabulary CSV Generator")
    print("=" * 70)
    print()
    
    # Check if HSK project directory exists
    if not HSK_PROJECT_DIR.exists():
        print(f"❌ Error: HSK project directory not found: {HSK_PROJECT_DIR}")
        print("   Please ensure the complete-hsk-vocabulary project is available.")
        return
    
    # Load HSK data
    hsk_data = load_hsk_data()
    
    if not hsk_data:
        print("❌ Error: No HSK data loaded!")
        return
    
    print(f"\n✅ Loaded {len(hsk_data)} unique words")
    
    # Write CSV
    output_file = OUTPUT_CSV
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_csv(hsk_data, output_file)
    
    print("\n" + "=" * 70)
    print("✅ Done!")
    print("=" * 70)

if __name__ == "__main__":
    main()

