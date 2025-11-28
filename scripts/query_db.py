#!/usr/bin/env python3
"""
Simple database query examples
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database.db import get_db_session
from backend.database.models import Profile, MasteredWord, MasteredGrammar


def main():
    print("=" * 80)
    print("SRS4Autism Database Query Examples")
    print("=" * 80)
    
    with get_db_session() as db:
        # Get all profiles
        print("\n📊 Profiles:")
        profiles = db.query(Profile).all()
        for profile in profiles:
            print(f"\n  ID: {profile.id}")
            print(f"  Name: {profile.name}")
            print(f"  Mental Age: {profile.mental_age}")
            
            # Count words
            chinese_count = db.query(MasteredWord).filter_by(
                profile_id=profile.id, 
                language='zh'
            ).count()
            english_count = db.query(MasteredWord).filter_by(
                profile_id=profile.id,
                language='en'
            ).count()
            grammar_count = db.query(MasteredGrammar).filter_by(
                profile_id=profile.id
            ).count()
            
            print(f"  Chinese Words: {chinese_count}")
            print(f"  English Words: {english_count}")
            print(f"  Grammar Points: {grammar_count}")
            
            # Show sample words
            print(f"\n  Sample Chinese words:")
            sample_zh = db.query(MasteredWord).filter_by(
                profile_id=profile.id,
                language='zh'
            ).limit(10).all()
            for word in sample_zh:
                print(f"    - {word.word}")
            
            print(f"\n  Sample English words:")
            sample_en = db.query(MasteredWord).filter_by(
                profile_id=profile.id,
                language='en'
            ).limit(10).all()
            for word in sample_en:
                print(f"    - {word.word}")


if __name__ == "__main__":
    main()


