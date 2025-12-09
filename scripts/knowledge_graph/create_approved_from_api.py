#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Get approved items from API endpoint and create missing ones in database.
The API shows the actual approved state (105 items), not the CSV.
"""

import sys
import json
import requests
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.db import get_db_session
from backend.database.models import PinyinSyllableNote
from scripts.knowledge_graph.pinyin_parser import extract_tone, add_tone_to_final, parse_pinyin
import shutil
from datetime import datetime

PROJECT_ROOT = project_root
API_URL = "http://localhost:8000/pinyin/gap-fill-suggestions"
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


def get_approved_from_api() -> list:
    """Get approved suggestions from API"""
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        suggestions = data.get('suggestions', [])
        approved = []
        
        for s in suggestions:
            # UI counts items where approved is truthy (non-empty string)
            # This matches the "105 approved" shown in UI
            approved_val = s.get('approved', '')
            if approved_val:  # Truthy check - includes "True", "False", any non-empty string
                syllable = s.get('Syllable', '').strip()
                word = s.get('Suggested Word', '').strip()
                if syllable and word and word != 'NONE':
                    approved.append({
                        'syllable': syllable,
                        'word': word,
                        'pinyin': s.get('Word Pinyin', '').strip(),
                        'image_file': s.get('Image File', '').strip()
                    })
        
        return approved
    
    except Exception as e:
        print(f"❌ Error fetching from API: {e}")
        return []


def create_approved_from_api():
    """Create approved items from API"""
    print("=" * 80)
    print("Create Approved Items from API")
    print("=" * 80)
    print()
    
    # Create backup
    print("💾 Creating database backup...")
    try:
        backup_path = create_database_backup()
    except Exception as e:
        print(f"   ❌ Error creating backup: {e}")
        return
    print()
    
    # Get approved items from API
    print("📡 Fetching approved suggestions from API...")
    approved_items = get_approved_from_api()
    print(f"   Found {len(approved_items)} approved items from API")
    print()
    
    if not approved_items:
        print("⚠️  No approved items found from API")
        return
    
    # Check which are missing from database
    missing_items = []
    with get_db_session() as db:
        for item in approved_items:
            existing = db.query(PinyinSyllableNote).filter(
                PinyinSyllableNote.syllable == item['syllable'],
                PinyinSyllableNote.word == item['word']
            ).first()
            
            if not existing:
                existing = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.syllable == item['syllable']
                ).first()
            
            if not existing:
                missing_items.append(item)
    
    print(f"📋 Missing from database: {len(missing_items)}")
    print()
    
    if not missing_items:
        print("✅ All approved items are already in the database!")
        return
    
    # Create the missing items
    created_count = 0
    
    with get_db_session() as db:
        # Get highest display_order
        max_order = db.query(PinyinSyllableNote.display_order).order_by(
            PinyinSyllableNote.display_order.desc()
        ).first()
        next_order = (max_order[0] if max_order else 0) + 1
        
        for item in missing_items:
            try:
                syllable = item['syllable']
                word = item['word']
                pinyin = item.get('pinyin', '')
                image_file = item.get('image_file', '')
                
                # Fetch concept
                concept = word
                
                # Generate all required fields
                tone_variations = generate_tone_variations(syllable)
                confusors = generate_confusors(syllable)
                element_to_learn = get_element_to_learn(syllable)
                word_audio = generate_word_audio(word)
                fixed_pinyin = pinyin or ''
                
                # Format WordPicture
                word_picture = f'<img src="{image_file}">' if image_file else ''
                
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
                print(f"  ✅ Created: {syllable} ({word}) - {word_picture}")
            
            except Exception as e:
                print(f"  ❌ Error creating {item.get('syllable', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    print()
    print(f"✅ Successfully created {created_count} new notes")
    print()
    
    # Final count
    with get_db_session() as db:
        final_count = db.query(PinyinSyllableNote).count()
        print(f"📊 Final count in database: {final_count}")
        print(f"   Expected: ~376 (271 original + 105 approved)")
        print(f"   Difference: {376 - final_count}")
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        create_approved_from_api()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        raise

