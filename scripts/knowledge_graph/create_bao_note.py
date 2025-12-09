#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create note for 宝藏 (bao) from the missing list suggestions.
This is an example of creating a single note for an approved but not-yet-applied suggestion.
"""

import sys
import json
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.db import get_db_session, create_backup
from backend.database.models import PinyinSyllableNote
from scripts.knowledge_graph.pinyin_parser import extract_tone, add_tone_to_final, parse_pinyin
import shutil
from datetime import datetime

PROJECT_ROOT = project_root
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


def create_bao_note():
    """Create note for 宝藏 (bao)"""
    print("=" * 80)
    print("Create Note for 宝藏 (bao)")
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
    
    syllable = 'bao'
    word = '宝藏'
    pinyin = 'bǎo zàng'
    image_file = 'treasure.jpeg'
    concept = 'treasure'  # Default concept
    
    with get_db_session() as db:
        # Check if already exists
        existing = db.query(PinyinSyllableNote).filter(
            PinyinSyllableNote.syllable == syllable,
            PinyinSyllableNote.word == word
        ).first()
        
        if existing:
            print(f"  ℹ️  Note already exists for '{syllable}' ({word})")
            fields = json.loads(existing.fields) if existing.fields else {}
            print(f"     WordHanzi: {fields.get('WordHanzi', '')}")
            print(f"     WordPicture: {fields.get('WordPicture', '')}")
            return
        
        # Get highest display_order
        max_order = db.query(PinyinSyllableNote.display_order).order_by(
            PinyinSyllableNote.display_order.desc()
        ).first()
        next_order = (max_order[0] if max_order else 0) + 1
        
        # Generate fields
        tone_variations = generate_tone_variations(syllable)
        confusors = generate_confusors(syllable)
        element_to_learn = get_element_to_learn(syllable)
        word_audio = generate_word_audio(word)
        word_picture = f'<img src="{image_file}">' if image_file else ''
        
        fields = {
            'ElementToLearn': element_to_learn,
            'Syllable': syllable,
            'WordPinyin': pinyin,
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
        print(f"  ✅ Created note for '{syllable}' ({word})")
        print(f"     WordPicture: {word_picture}")
        print(f"     WordAudio: {word_audio}")
        print(f"     Tone1-4: {tone_variations}")
        print(f"     Confusors: {confusors}")
    
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        create_bao_note()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        raise

