#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check sync status between:
1. CSV approval status (approved column)
2. Database existence (if note exists in database)
3. Identify items that are out of sync
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


def check_sync_status():
    """Check sync status between CSV and database"""
    print("=" * 80)
    print("Check Approval Sync Status")
    print("=" * 80)
    print()
    
    # Load all suggestions from CSV
    suggestions = []
    if not SUGGESTIONS_FILE.exists():
        print(f"❌ Suggestions file not found: {SUGGESTIONS_FILE}")
        return
    
    with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            syllable = row.get('Syllable', '').strip()
            word = row.get('Suggested Word', '').strip()
            approved_csv = row.get('approved', '').strip().lower()
            
            if syllable and word and word != 'NONE':
                suggestions.append({
                    'syllable': syllable,
                    'word': word,
                    'approved_csv': approved_csv == 'true' or approved_csv == '1',
                    'pinyin': row.get('Word Pinyin', '').strip(),
                    'image_file': row.get('Image File', '').strip(),
                    'has_image': row.get('Has Image', '').strip() == 'Yes'
                })
    
    print(f"📋 Loaded {len(suggestions)} suggestions from CSV")
    print()
    
    # Check database status
    with get_db_session() as db:
        approved_in_csv_not_in_db = []
        in_db_not_approved_in_csv = []
        approved_and_in_db = []
        not_approved_not_in_db = []
        
        for s in suggestions:
            # Check if exists in database
            existing = db.query(PinyinSyllableNote).filter(
                PinyinSyllableNote.syllable == s['syllable'],
                PinyinSyllableNote.word == s['word']
            ).first()
            
            # Also check by syllable only
            if not existing:
                existing = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.syllable == s['syllable']
                ).first()
            
            in_db = existing is not None
            approved_csv = s['approved_csv']
            
            if approved_csv and not in_db:
                approved_in_csv_not_in_db.append(s)
            elif in_db and not approved_csv:
                in_db_not_approved_in_csv.append(s)
            elif approved_csv and in_db:
                approved_and_in_db.append(s)
            else:
                not_approved_not_in_db.append(s)
    
    # Print summary
    print("📊 SYNC STATUS SUMMARY")
    print("=" * 80)
    print(f"✅ Approved in CSV AND in database: {len(approved_and_in_db)}")
    print(f"⚠️  Approved in CSV but NOT in database: {len(approved_in_csv_not_in_db)}")
    print(f"❌ In database but NOT approved in CSV: {len(in_db_not_approved_in_csv)}")
    print(f"   Not approved and not in database: {len(not_approved_not_in_db)}")
    print()
    
    # Show out-of-sync items
    if approved_in_csv_not_in_db:
        print("=" * 80)
        print("⚠️  APPROVED IN CSV BUT NOT IN DATABASE:")
        print("=" * 80)
        for s in sorted(approved_in_csv_not_in_db, key=lambda x: x['syllable']):
            print(f"  - {s['syllable']:6s} ({s['word']:10s}) - {s['pinyin']:15s} - Image: {s['image_file'] or 'None'}")
        print()
    
    if in_db_not_approved_in_csv:
        print("=" * 80)
        print("❌ IN DATABASE BUT NOT APPROVED IN CSV:")
        print("=" * 80)
        for s in sorted(in_db_not_approved_in_csv, key=lambda x: x['syllable']):
            print(f"  - {s['syllable']:6s} ({s['word']:10s}) - {s['pinyin']:15s} - Image: {s['image_file'] or 'None'}")
        print()
    
    # Show items with images that might be approved in UI but not CSV
    if in_db_not_approved_in_csv:
        print("=" * 80)
        print("🔍 ANALYSIS: Items in database but not approved in CSV")
        print("   (These might be approved in UI but CSV wasn't saved)")
        print("=" * 80)
        with_images = [s for s in in_db_not_approved_in_csv if s['has_image']]
        without_images = [s for s in in_db_not_approved_in_csv if not s['has_image']]
        
        print(f"\n   With images ({len(with_images)}): Likely approved in UI")
        for s in sorted(with_images, key=lambda x: x['syllable'])[:20]:
            print(f"     - {s['syllable']:6s} ({s['word']:10s}) - {s['image_file']}")
        if len(with_images) > 20:
            print(f"     ... and {len(with_images) - 20} more")
        
        if without_images:
            print(f"\n   Without images ({len(without_images)}): Possibly auto-created")
            for s in sorted(without_images, key=lambda x: x['syllable'])[:10]:
                print(f"     - {s['syllable']:6s} ({s['word']:10s})")
            if len(without_images) > 10:
                print(f"     ... and {len(without_images) - 10} more")
        print()
    
    print("=" * 80)
    print("✅ Sync check complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        check_sync_status()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        raise

