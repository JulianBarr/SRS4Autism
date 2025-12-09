#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix pinyin syllables list in cuma for words curated from the missing list:
1. Fix WordPicture field to be in <img src="somepicture.jpg"> format
2. Populate WordAudio, tone1-4, Confusors fields for words from missing list
   (similar to what was done for 屏幕)
"""

import sys
import json
import re
import csv
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.db import get_db_session
from backend.database.models import PinyinSyllableNote
from scripts.knowledge_graph.pinyin_parser import extract_tone, add_tone_to_final, parse_pinyin
import shutil
from datetime import datetime

PROJECT_ROOT = project_root
SUGGESTIONS_FILE = PROJECT_ROOT / "data" / "pinyin_gap_fill_suggestions.csv"
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def create_database_backup():
    """Create a backup of the SQLite database"""
    if not DB_PATH.exists():
        print("⚠️  Database file does not exist, nothing to backup")
        return None
    
    # Create backup directory if it doesn't exist
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped backup filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f"srs4autism_{timestamp}.db"
    
    # Copy database file
    shutil.copy2(DB_PATH, backup_path)
    
    # Get file size
    size_mb = backup_path.stat().st_size / (1024 * 1024)
    
    print(f"✅ Database backup created: {backup_path}")
    print(f"   Size: {size_mb:.2f} MB")
    return backup_path


def generate_tone_variations(syllable: str) -> list:
    """Generate all 4 tone variations of a syllable."""
    syllable_no_tone, _ = extract_tone(syllable)
    if not syllable_no_tone:
        return ['', '', '', '']
    
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(syllable_no_tone, tone)
        variations.append(toned)
    return variations


def generate_confusors(syllable: str) -> list:
    """Generate confusor syllables (similar syllables that might be confused)."""
    syllable_no_tone, _ = extract_tone(syllable)
    if not syllable_no_tone or len(syllable_no_tone) < 2:
        return ['', '', '']
    
    # Extract initial and final
    initial = syllable_no_tone[0]
    final = syllable_no_tone[1:] if len(syllable_no_tone) > 1 else ''
    
    # Generate confusors: b+final (tone 1), p+final (tone 2), original with different tone
    confusors = []
    if final:
        confusors.append(add_tone_to_final('b' + final, 1))
        confusors.append(add_tone_to_final('p' + final, 2))
    else:
        confusors.append(add_tone_to_final('ba', 1))
        confusors.append(add_tone_to_final('pa', 2))
    
    # Third confusor: original syllable with tone 3 or 4 (if original wasn't tone 3)
    original_toned = add_tone_to_final(syllable_no_tone, 3)
    if original_toned == syllable:
        original_toned = add_tone_to_final(syllable_no_tone, 4)
    confusors.append(original_toned)
    
    return confusors


def generate_word_audio(word: str) -> str:
    """Generate WordAudio field in format: [sound:cm_tts_zh_<word>.mp3]"""
    if not word:
        return ''
    return f"[sound:cm_tts_zh_{word}.mp3]"


def fix_word_picture_format(word_picture: str, image_file: str = None) -> str:
    """
    Fix WordPicture field to be in <img src="somepicture.jpg"> format.
    Handles cases where WordPicture might be:
    - Just a filename (e.g., "screen.png")
    - A path (e.g., "/media/pinyin/screen.png")
    - Already in correct format (e.g., '<img src="screen.png">')
    - Empty or None
    """
    if not word_picture and not image_file:
        return ''
    
    # If already in correct format, return as is
    if word_picture and word_picture.strip().startswith('<img'):
        return word_picture.strip()
    
    # Extract filename from word_picture or use image_file
    filename = None
    if word_picture:
        # Remove any path prefixes
        filename = Path(word_picture).name
    elif image_file:
        filename = Path(image_file).name
    
    if filename:
        return f'<img src="{filename}">'
    
    return ''


def normalize_syllable_for_matching(syllable: str) -> str:
    """Normalize syllable for matching (handle tone variations)"""
    if not syllable:
        return ''
    # Convert to lowercase and remove tone numbers
    normalized = syllable.lower()
    normalized = re.sub(r'[1-5]', '', normalized)
    return normalized


def load_suggestions_from_csv() -> dict:
    """Load suggestions from CSV file, indexed by syllable"""
    suggestions = {}
    
    if not SUGGESTIONS_FILE.exists():
        print(f"⚠️  Suggestions file not found: {SUGGESTIONS_FILE}")
        return suggestions
    
    with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            syllable = row.get('Syllable', '').strip()
            if syllable and row.get('Suggested Word', '').strip() != 'NONE':
                # Store both original and normalized syllable for matching
                suggestions[syllable] = {
                    'word': row.get('Suggested Word', '').strip(),
                    'pinyin': row.get('Word Pinyin', '').strip(),
                    'image_file': row.get('Image File', '').strip(),
                    'normalized': normalize_syllable_for_matching(syllable)
                }
    
    return suggestions


def fix_missing_list_syllables():
    """Fix WordPicture format and populate missing fields for words from missing list"""
    print("=" * 80)
    print("Fix Missing List Pinyin Syllables")
    print("=" * 80)
    print()
    
    # Create database backup before making changes
    print("💾 Creating database backup...")
    try:
        backup_path = create_database_backup()
        if not backup_path:
            print("   ⚠️  Backup creation returned None (database may not exist)")
            response = input("   Continue without backup? (yes/no): ")
            if response.lower() != 'yes':
                print("   Exiting...")
                return
    except Exception as e:
        print(f"   ❌ Error creating backup: {e}")
        import traceback
        traceback.print_exc()
        response = input("   Continue without backup? (yes/no): ")
        if response.lower() != 'yes':
            print("   Exiting...")
            return
    print()
    
    # Load suggestions from CSV
    print("📋 Loading suggestions from CSV...")
    suggestions = load_suggestions_from_csv()
    print(f"   Found {len(suggestions)} suggestions from missing list")
    print()
    
    if not suggestions:
        print("⚠️  No suggestions found. Exiting.")
        return
    
    fixed_count = 0
    populated_count = 0
    total_count = 0
    
    with get_db_session() as db:
        # Get all pinyin syllable notes
        all_notes = db.query(PinyinSyllableNote).all()
        total_count = len(all_notes)
        
        print(f"📊 Found {total_count} pinyin syllable notes in database")
        print()
        
        # Process each suggestion
        for syllable, suggestion_data in suggestions.items():
            word = suggestion_data['word']
            image_file = suggestion_data.get('image_file', '')
            normalized_syllable = suggestion_data.get('normalized', '')
            
            # Find matching notes (by syllable and word) - try exact match first
            matching_notes = db.query(PinyinSyllableNote).filter(
                PinyinSyllableNote.syllable == syllable,
                PinyinSyllableNote.word == word
            ).all()
            
            # If no exact match, try by normalized syllable and word
            if not matching_notes and normalized_syllable:
                all_notes = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.word == word
                ).all()
                matching_notes = [
                    note for note in all_notes
                    if normalize_syllable_for_matching(note.syllable) == normalized_syllable
                ]
            
            # If still no match, try by syllable only (exact)
            if not matching_notes:
                matching_notes = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.syllable == syllable
                ).all()
            
            # If still no match, try by normalized syllable only
            if not matching_notes and normalized_syllable:
                all_notes = db.query(PinyinSyllableNote).all()
                matching_notes = [
                    note for note in all_notes
                    if normalize_syllable_for_matching(note.syllable) == normalized_syllable
                ]
            
            if not matching_notes:
                print(f"  ⚠️  No notes found for syllable '{syllable}' with word '{word}'")
                continue
            
            for note in matching_notes:
                try:
                    # Parse fields
                    fields = json.loads(note.fields) if isinstance(note.fields, str) else note.fields
                    if not isinstance(fields, dict):
                        continue
                    
                    updated = False
                    
                    # Fix WordPicture format
                    current_word_picture = fields.get('WordPicture', '')
                    fixed_word_picture = fix_word_picture_format(current_word_picture, image_file)
                    
                    # Only update if WordPicture is empty or in wrong format
                    if fixed_word_picture and fixed_word_picture != current_word_picture:
                        fields['WordPicture'] = fixed_word_picture
                        updated = True
                        print(f"  ✅ Fixed WordPicture for '{syllable}' ({word}): {current_word_picture[:50] if current_word_picture else '(empty)'} -> {fixed_word_picture}")
                    
                    # Populate WordAudio if missing
                    if not fields.get('WordAudio', '').strip():
                        word_audio = generate_word_audio(word)
                        if word_audio:
                            fields['WordAudio'] = word_audio
                            updated = True
                            print(f"  ✅ Added WordAudio for '{syllable}' ({word}): {word_audio}")
                    
                    # Populate Tone1-4 if missing
                    tone_variations = generate_tone_variations(syllable)
                    for i, tone_field in enumerate(['Tone1', 'Tone2', 'Tone3', 'Tone4'], 0):
                        if not fields.get(tone_field, '').strip() and i < len(tone_variations):
                            fields[tone_field] = tone_variations[i]
                            if tone_variations[i]:
                                updated = True
                                print(f"  ✅ Added {tone_field} for '{syllable}' ({word}): {tone_variations[i]}")
                    
                    # Populate Confusors if missing
                    confusors = generate_confusors(syllable)
                    for i, confusor_field in enumerate(['Confusor1', 'Confusor2', 'Confusor3'], 0):
                        if not fields.get(confusor_field, '').strip() and i < len(confusors):
                            fields[confusor_field] = confusors[i]
                            if confusors[i]:
                                updated = True
                                print(f"  ✅ Added {confusor_field} for '{syllable}' ({word}): {confusors[i]}")
                    
                    # Populate ConfusorPicture fields if missing (set to empty string)
                    for pic_field in ['ConfusorPicture1', 'ConfusorPicture2', 'ConfusorPicture3']:
                        if pic_field not in fields:
                            fields[pic_field] = ''
                            updated = True
                    
                    # Update database if any changes were made
                    if updated:
                        note.fields = json.dumps(fields, ensure_ascii=False)
                        fixed_count += 1
                        if fixed_word_picture and fixed_word_picture != current_word_picture:
                            populated_count += 1
                
                except Exception as e:
                    print(f"  ❌ Error processing note {note.note_id} for syllable '{syllable}': {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        # Commit all changes
        if fixed_count > 0:
            db.commit()
            print()
            print(f"✅ Successfully fixed {fixed_count} notes")
            print(f"   - Fixed WordPicture format: {populated_count} notes")
            print(f"   - Populated missing fields (WordAudio, Tone1-4, Confusors): {fixed_count} notes")
        else:
            print()
            print("ℹ️  No notes needed fixing")
    
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        fix_missing_list_syllables()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        print("\nTraceback:")
        traceback.print_exc()
        raise

