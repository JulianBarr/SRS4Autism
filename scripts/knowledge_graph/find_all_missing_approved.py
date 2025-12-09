#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find all approved items that should be in the database but aren't.
Compare:
- Original count: 271
- Approved from missing list: 105 (from UI, not CSV)
- Current count: 341
- Expected: ~376
- Missing: ~35 items
"""

import sys
import csv
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.db import get_db_session
from backend.database.models import PinyinSyllableNote

PROJECT_ROOT = project_root
SUGGESTIONS_FILE = PROJECT_ROOT / "data" / "pinyin_gap_fill_suggestions.csv"


def find_missing_approved():
    """Find all approved items missing from database"""
    print("=" * 80)
    print("Find All Missing Approved Items")
    print("=" * 80)
    print()
    
    # Load ALL suggestions (not just approved in CSV, since UI might have more)
    all_suggestions = []
    if SUGGESTIONS_FILE.exists():
        with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                syllable = row.get('Syllable', '').strip()
                word = row.get('Suggested Word', '').strip()
                approved_csv = row.get('approved', '').strip().lower()
                has_image = row.get('Has Image', '').strip() == 'Yes'
                
                if syllable and word and word != 'NONE':
                    all_suggestions.append({
                        'syllable': syllable,
                        'word': word,
                        'approved_csv': approved_csv == 'true' or approved_csv == '1',
                        'pinyin': row.get('Word Pinyin', '').strip(),
                        'image_file': row.get('Image File', '').strip(),
                        'has_image': has_image
                    })
    
    print(f"📋 Total suggestions in CSV: {len(all_suggestions)}")
    
    # Count approved in CSV
    approved_in_csv = sum(1 for s in all_suggestions if s['approved_csv'])
    print(f"📋 Approved in CSV: {approved_in_csv}")
    print()
    
    # Check database
    with get_db_session() as db:
        total_in_db = db.query(PinyinSyllableNote).count()
        print(f"📊 Total in database: {total_in_db}")
        print()
        
        # Check which suggestions are missing
        missing_approved = []
        missing_with_images = []
        in_db_not_approved = []
        
        for suggestion in all_suggestions:
            # Check if exists in database
            existing = db.query(PinyinSyllableNote).filter(
                PinyinSyllableNote.syllable == suggestion['syllable'],
                PinyinSyllableNote.word == suggestion['word']
            ).first()
            
            if not existing:
                existing = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.syllable == suggestion['syllable']
                ).first()
            
            in_db = existing is not None
            
            # Items approved in CSV but missing from DB
            if suggestion['approved_csv'] and not in_db:
                missing_approved.append(suggestion)
            
            # Items with images but not in DB (likely approved in UI)
            if suggestion['has_image'] and not in_db:
                missing_with_images.append(suggestion)
            
            # Items in DB but not approved in CSV
            if in_db and not suggestion['approved_csv']:
                in_db_not_approved.append(suggestion)
        
        print("=" * 80)
        print("MISSING ITEMS ANALYSIS")
        print("=" * 80)
        print()
        
        print(f"❌ Approved in CSV but missing from DB: {len(missing_approved)}")
        if missing_approved:
            print("\nMissing approved items:")
            for s in sorted(missing_approved, key=lambda x: x['syllable']):
                print(f"  - {s['syllable']:6s} ({s['word']:10s}) - {s['pinyin']:15s} - Image: {s['image_file'] or 'None'}")
        print()
        
        print(f"⚠️  Has image but missing from DB: {len(missing_with_images)}")
        if missing_with_images:
            print("\nMissing items with images (likely approved in UI but CSV not saved):")
            for s in sorted(missing_with_images, key=lambda x: x['syllable'])[:50]:
                approved_status = "✅ APPROVED" if s['approved_csv'] else "❌ Not in CSV"
                print(f"  {approved_status} - {s['syllable']:6s} ({s['word']:10s}) - {s['pinyin']:15s} - {s['image_file'] or 'None'}")
            if len(missing_with_images) > 50:
                print(f"  ... and {len(missing_with_images) - 50} more")
        print()
        
        print(f"✅ In DB but not approved in CSV: {len(in_db_not_approved)}")
        print()
        
        # Expected vs actual
        print("=" * 80)
        print("EXPECTED vs ACTUAL")
        print("=" * 80)
        print(f"Original syllables: 271")
        print(f"Approved from missing (UI says): 105")
        print(f"Expected total: ~376")
        print(f"Current total: {total_in_db}")
        print(f"Missing: ~{376 - total_in_db}")
        print()
        
        # Items with images that should likely be created (approved in UI)
        candidates = [s for s in missing_with_images if not s['approved_csv']]
        print(f"📝 Candidates (has image, not approved in CSV, missing from DB): {len(candidates)}")
        print("   These are likely approved in UI but CSV wasn't saved:")
        for s in sorted(candidates, key=lambda x: x['syllable'])[:30]:
            print(f"     - {s['syllable']:6s} ({s['word']:10s}) - {s['image_file'] or 'None'}")
        if len(candidates) > 30:
            print(f"     ... and {len(candidates) - 30} more")


if __name__ == "__main__":
    try:
        find_missing_approved()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        raise

