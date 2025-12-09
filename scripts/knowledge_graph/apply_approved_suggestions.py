#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apply approved suggestions from CSV to create new syllable notes in database.
This script finds approved suggestions that don't exist in the database yet and creates them.
"""

import sys
import json
import csv
import re
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
    
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f"srs4autism_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
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
    """Generate confusor syllables."""
    syllable_no_tone, _ = extract_tone(syllable)
    if not syllable_no_tone or len(syllable_no_tone) < 2:
        return ['', '', '']
    
    initial = syllable_no_tone[0]
    final = syllable_no_tone[1:] if len(syllable_no_tone) > 1 else ''
    
    confusors = []
    if final:
        confusors.append(add_tone_to_final('b' + final, 1))
        confusors.append(add_tone_to_final('p' + final, 2))
    else:
        confusors.append(add_tone_to_final('ba', 1))
        confusors.append(add_tone_to_final('pa', 2))
    
    original_toned = add_tone_to_final(syllable_no_tone, 3)
    if original_toned == syllable:
        original_toned = add_tone_to_final(syllable_no_tone, 4)
    confusors.append(original_toned)
    
    return confusors


def get_element_to_learn(syllable: str) -> str:
    """Determine ElementToLearn from syllable (the final/韵母)."""
    syllable_no_tone, _ = extract_tone(syllable)
    if not syllable_no_tone:
        return ''
    
    parsed = parse_pinyin(syllable_no_tone)
    return parsed.get('final', '') or ''


def generate_word_audio(word: str) -> str:
    """Generate WordAudio field in format: [sound:cm_tts_zh_<word>.mp3]"""
    if not word:
        return ''
    return f"[sound:cm_tts_zh_{word}.mp3]"


def fix_iu_ui_tone_placement(pinyin: str) -> str:
    """Fix tone placement for iu/ui patterns."""
    try:
        # Import the function from main.py if available
        from backend.app.main import fix_iu_ui_tone_placement as fix_pinyin
        return fix_pinyin(pinyin)
    except Exception:
        # Fallback: return as-is
        return pinyin


def get_word_knowledge(word: str) -> dict:
    """Get word knowledge from knowledge graph - simplified version"""
    # In the real implementation, this queries the knowledge graph
    # For now, just return empty dict
    return {}


def load_approved_suggestions() -> list:
    """Load approved suggestions from CSV file"""
    approved = []
    
    if not SUGGESTIONS_FILE.exists():
        print(f"⚠️  Suggestions file not found: {SUGGESTIONS_FILE}")
        return approved
    
    with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Check if approved (last column or explicit 'approved' column)
            approved_val = row.get('approved', '').strip().lower()
            if approved_val == 'true' or approved_val == '1':
                syllable = row.get('Syllable', '').strip()
                word = row.get('Suggested Word', '').strip()
                if syllable and word and word != 'NONE':
                    approved.append({
                        'syllable': syllable,
                        'word': word,
                        'pinyin': row.get('Word Pinyin', '').strip(),
                        'image_file': row.get('Image File', '').strip(),
                        'hsk_level': row.get('HSK Level', '').strip()
                    })
    
    return approved


def apply_approved_suggestions():
    """Apply approved suggestions that don't exist in database yet"""
    print("=" * 80)
    print("Apply Approved Pinyin Suggestions")
    print("=" * 80)
    print()
    
    # Create database backup
    print("💾 Creating database backup...")
    try:
        backup_path = create_database_backup()
        if not backup_path:
            response = input("   Continue without backup? (yes/no): ")
            if response.lower() != 'yes':
                return
    except Exception as e:
        print(f"   ❌ Error creating backup: {e}")
        response = input("   Continue without backup? (yes/no): ")
        if response.lower() != 'yes':
            return
    print()
    
    # Load approved suggestions
    print("📋 Loading approved suggestions from CSV...")
    approved_suggestions = load_approved_suggestions()
    print(f"   Found {len(approved_suggestions)} approved suggestions")
    
    # Also check for unapproved but valid suggestions that might need to be created
    # (e.g., 宝藏 which might be in the list but not marked approved)
    all_valid = load_approved_suggestions(include_all_valid=True)
    unapproved_valid = [s for s in all_valid if not s.get('approved', False)]
    if unapproved_valid:
        print(f"   Note: {len(unapproved_valid)} valid suggestions exist but are not marked as approved")
        print(f"   (These will only be created if explicitly approved or if using --include-all flag)")
    print()
    
    if not approved_suggestions:
        print("⚠️  No approved suggestions found. Exiting.")
        return
    
    created_count = 0
    skipped_count = 0
    
    with get_db_session() as db:
        # Get the highest display_order
        max_order = db.query(PinyinSyllableNote.display_order).order_by(
            PinyinSyllableNote.display_order.desc()
        ).first()
        next_order = (max_order[0] if max_order else 0) + 1
        
        for suggestion in approved_suggestions:
            syllable = suggestion['syllable']
            word = suggestion['word']
            pinyin = suggestion.get('pinyin', '')
            image_file = suggestion.get('image_file', '')
            
            # Check if note already exists
            existing = db.query(PinyinSyllableNote).filter(
                PinyinSyllableNote.syllable == syllable,
                PinyinSyllableNote.word == word
            ).first()
            
            # Also check by syllable only (backward compatibility)
            if not existing:
                existing = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.syllable == syllable
                ).first()
            
            if existing:
                print(f"  ℹ️  Note already exists for '{syllable}' ({word}), skipping...")
                skipped_count += 1
                continue
            
            # Fetch concept from knowledge graph
            concept = word  # Default
            try:
                word_info = get_word_knowledge(word)
                if word_info.get("meanings"):
                    concept = word_info["meanings"][0]
            except Exception:
                concept = word
            
            # Generate all required fields
            tone_variations = generate_tone_variations(syllable)
            confusors = generate_confusors(syllable)
            element_to_learn = get_element_to_learn(syllable)
            word_audio = generate_word_audio(word)
            fixed_pinyin = fix_iu_ui_tone_placement(pinyin or '') if pinyin else ''
            
            # Format WordPicture
            word_picture = ''
            if image_file:
                word_picture = f'<img src="{image_file}">'
            
            fields = {
                'ElementToLearn': element_to_learn,
                'Syllable': syllable,
                'WordPinyin': fixed_pinyin,
                'WordHanzi': word,
                'WordPicture': word_picture,
                'WordAudio': word_audio,
                'Tone1': tone_variations[0] if len(tone_variations) > 0 else '',
                'Tone2': tone_variations[1] if len(tone_variations) > 1 else '',
                'Tone3': tone_variations[2] if len(tone_variations) > 2 else '',
                'Tone4': tone_variations[3] if len(tone_variations) > 3 else '',
                'Confusor1': confusors[0] if len(confusors) > 0 else '',
                'ConfusorPicture1': '',
                'Confusor2': confusors[1] if len(confusors) > 1 else '',
                'ConfusorPicture2': '',
                'Confusor3': confusors[2] if len(confusors) > 2 else '',
                'ConfusorPicture3': '',
                '_Remarks': '',
                '_KG_Map': '{}'
            }
            
            new_note = PinyinSyllableNote(
                note_id=f"syllable_{syllable}_{next_order}",
                syllable=syllable,
                word=word,
                concept=concept,
                fields=json.dumps(fields, ensure_ascii=False),
                display_order=next_order
            )
            
            db.add(new_note)
            next_order += 1
            created_count += 1
            print(f"  ✅ Created note for '{syllable}' ({word})")
    
    print()
    print(f"✅ Successfully created {created_count} new notes")
    print(f"   Skipped {skipped_count} notes (already exist)")
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        apply_approved_suggestions()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        print("\nTraceback:")
        traceback.print_exc()
        raise

