#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate English word recognition notes from Chinese word recognition notes.

This script:
1. Reads Chinese word recognition notes from database
2. Extracts the English concepts
3. Creates English word recognition notes with:
   - English word = concept (for naming)
   - Images from Chinese notes (shared concepts)
   - English TTS audio files (already generated)
4. Stores them in english_word_recognition_notes table

This is for verbal training - focuses on listening and speaking, not reading/writing.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base, ChineseWordRecognitionNote, EnglishWordRecognitionNote

# Configuration
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
AUDIO_DIR = PROJECT_ROOT / "media" / "audio" / "english_naming"


def sanitize_filename(concept: str) -> str:
    """Sanitize concept name for use as filename"""
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', concept)
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized


def get_audio_filename(concept: str) -> str:
    """Get the audio filename for a concept"""
    sanitized = sanitize_filename(concept)
    return f"{sanitized}.english.mp3"


def create_english_fields(chinese_fields: dict, concept: str) -> dict:
    """Create English note fields from Chinese note fields"""
    english_fields = {}
    
    # Word = concept (for naming)
    english_fields['Word'] = concept
    english_fields['Concept'] = concept  # Same as word for naming
    
    # Copy image from Chinese note (shared concept)
    if 'Image' in chinese_fields:
        english_fields['Image'] = chinese_fields['Image']
    elif 'image' in chinese_fields:
        english_fields['Image'] = chinese_fields['image']
    
    # Add English audio
    audio_filename = get_audio_filename(concept)
    audio_path = AUDIO_DIR / audio_filename
    if audio_path.exists():
        # Use Anki sound tag format
        english_fields['Audio'] = f'[sound:{audio_filename}]'
    else:
        print(f"  ⚠️  Warning: Audio file not found for '{concept}': {audio_filename}")
        english_fields['Audio'] = ""
    
    # Copy other fields that might be useful
    # (distractor images, etc.)
    for key in ['DistractorImage1', 'DistractorImage2', 'DistractorImage3']:
        if key in chinese_fields:
            english_fields[key] = chinese_fields[key]
    
    return english_fields


def main():
    """Main function to generate English word recognition notes"""
    import sys
    
    print("🚀 Starting English word recognition note generation...")
    print(f"   Database: {DB_PATH}")
    print(f"   Audio directory: {AUDIO_DIR}")
    
    if not DB_PATH.exists():
        print(f"❌ Error: Database not found at {DB_PATH}")
        return
    
    if not AUDIO_DIR.exists():
        print(f"⚠️  Warning: Audio directory not found at {AUDIO_DIR}")
        print("   Please run generate_english_tts_for_naming.py first")
    
    # Initialize database
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if notes already exist
        existing_count = session.query(EnglishWordRecognitionNote).count()
        if existing_count > 0:
            # Check for --force flag
            force = '--force' in sys.argv or '-f' in sys.argv
            if force:
                response = 'y'
            else:
                try:
                    response = input(f"⚠️  Found {existing_count} existing notes. Delete and re-generate? (y/N): ")
                except EOFError:
                    response = 'y'
                    print(f"⚠️  Found {existing_count} existing notes. Auto-deleting (non-interactive mode)...")
            
            if response.lower() == 'y':
                session.query(EnglishWordRecognitionNote).delete()
                session.commit()
                print("🗑️  Deleted existing notes")
            else:
                print("❌ Aborted")
                return
        
        # Get all Chinese word recognition notes, ordered
        chinese_notes = session.query(ChineseWordRecognitionNote).order_by(
            ChineseWordRecognitionNote.display_order
        ).all()
        
        print(f"\n📚 Found {len(chinese_notes)} Chinese word recognition notes")
        
        # Generate English notes
        english_notes = []
        skipped = 0
        
        for chinese_note in chinese_notes:
            concept = chinese_note.concept.strip()
            if not concept:
                skipped += 1
                continue
            
            # Parse Chinese fields
            chinese_fields = json.loads(chinese_note.fields) if chinese_note.fields else {}
            
            # Create English fields
            english_fields = create_english_fields(chinese_fields, concept)
            
            # Generate note ID (use concept + display_order to ensure uniqueness)
            # Some concepts might be duplicated (e.g., "Thirteen" appears multiple times)
            note_id = f"eng_naming_{chinese_note.display_order}_{sanitize_filename(concept)}"
            
            english_notes.append({
                'note_id': note_id,
                'word': concept,  # Word = concept for naming
                'concept': concept,
                'display_order': chinese_note.display_order,  # Maintain same order
                'fields': english_fields
            })
        
        print(f"📝 Generated {len(english_notes)} English word recognition notes")
        if skipped > 0:
            print(f"   ⚠️  Skipped {skipped} notes (no concept)")
        
        # Store in database
        print("\n💾 Storing notes in database...")
        for note_data in english_notes:
            db_note = EnglishWordRecognitionNote(
                note_id=note_data['note_id'],
                word=note_data['word'],
                concept=note_data['concept'],
                display_order=note_data['display_order'],
                fields=json.dumps(note_data['fields'], ensure_ascii=False)
            )
            session.add(db_note)
        
        session.commit()
        print(f"✅ Successfully stored {len(english_notes)} notes in database")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()

