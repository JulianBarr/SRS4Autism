#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix the 28 out-of-sync syllables that are in database but not approved in CSV.
Ensure they have WordPicture in correct format, WordAudio, Tone1-4, and Confusors.
"""

import sys
import json
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


def generate_word_audio(word: str) -> str:
    """Generate WordAudio field in format: [sound:cm_tts_zh_<word>.mp3]"""
    if not word:
        return ''
    return f"[sound:cm_tts_zh_{word}.mp3]"


def fix_word_picture_format(word_picture: str, image_file: str = None) -> str:
    """Fix WordPicture field to be in <img src="somepicture.jpg"> format."""
    if not word_picture and not image_file:
        return ''
    
    # If already in correct format, return as is
    if word_picture and word_picture.strip().startswith('<img'):
        return word_picture.strip()
    
    # Extract filename from word_picture or use image_file
    filename = None
    if word_picture:
        filename = Path(word_picture).name
    elif image_file:
        filename = Path(image_file).name
    
    if filename:
        return f'<img src="{filename}">'
    
    return ''


def get_out_of_sync_items() -> list:
    """Get the 28 items that are in database but not approved in CSV"""
    out_of_sync = []
    
    # Load CSV to get image files
    csv_data = {}
    if SUGGESTIONS_FILE.exists():
        with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                syllable = row.get('Syllable', '').strip()
                word = row.get('Suggested Word', '').strip()
                if syllable and word:
                    key = f"{syllable}:{word}"
                    csv_data[key] = {
                        'image_file': row.get('Image File', '').strip(),
                        'pinyin': row.get('Word Pinyin', '').strip()
                    }
    
    # The 28 items identified
    out_of_sync_items = [
        ('biao', '手表'),
        ('bin', '宾馆'),
        ('nian', '新年'),
        ('niu', '牛'),
        ('nong', '农民'),
        ('nu', '发怒'),
        ('pao', '跑步'),
        ('piao', '漂亮'),
        ('qiang', '墙'),
        ('reng', '扔'),
        ('shao', '勺子'),
        ('shen', '身体'),
        ('sheng', '声音'),
        ('shua', '牙刷'),
        ('shuang', '双手'),
        ('tian', '今天'),
        ('tiao', '跳'),
        ('tong', '同学'),
        ('tui', '腿'),
        ('wei', '座位'),
        ('wen', '语文'),
        ('xiong', '熊'),
        ('ye', '夜里'),
        ('ying', '影子'),
        ('yue', '月亮'),
        ('zhe', '这里'),
        ('zhong', '种子'),
        ('zhuo', '桌子')
    ]
    
    for syllable, word in out_of_sync_items:
        key = f"{syllable}:{word}"
        csv_info = csv_data.get(key, {})
        out_of_sync.append({
            'syllable': syllable,
            'word': word,
            'image_file': csv_info.get('image_file', ''),
            'pinyin': csv_info.get('pinyin', '')
        })
    
    return out_of_sync


def fix_out_of_sync_syllables():
    """Fix the 28 out-of-sync syllables"""
    print("=" * 80)
    print("Fix Out-of-Sync Syllables (28 items)")
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
    
    # Get the 28 out-of-sync items
    out_of_sync_items = get_out_of_sync_items()
    print(f"📋 Found {len(out_of_sync_items)} out-of-sync items to fix")
    print()
    
    fixed_count = 0
    populated_count = 0
    
    with get_db_session() as db:
        for item in out_of_sync_items:
            syllable = item['syllable']
            word = item['word']
            image_file = item.get('image_file', '')
            
            # Find the note
            note = db.query(PinyinSyllableNote).filter(
                PinyinSyllableNote.syllable == syllable,
                PinyinSyllableNote.word == word
            ).first()
            
            if not note:
                # Try by syllable only
                note = db.query(PinyinSyllableNote).filter(
                    PinyinSyllableNote.syllable == syllable
                ).first()
            
            if not note:
                print(f"  ⚠️  Note not found for '{syllable}' ({word})")
                continue
            
            try:
                # Parse fields
                fields = json.loads(note.fields) if isinstance(note.fields, str) else note.fields
                if not isinstance(fields, dict):
                    continue
                
                updated = False
                
                # Fix WordPicture format
                current_word_picture = fields.get('WordPicture', '')
                fixed_word_picture = fix_word_picture_format(current_word_picture, image_file)
                
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
                
                # Populate ConfusorPicture fields if missing
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
                print(f"  ❌ Error processing '{syllable}' ({word}): {e}")
                import traceback
                traceback.print_exc()
                continue
    
    print()
    print(f"✅ Successfully fixed {fixed_count} notes")
    print(f"   - Fixed WordPicture format: {populated_count} notes")
    print(f"   - Populated missing fields (WordAudio, Tone1-4, Confusors): {fixed_count} notes")
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        fix_out_of_sync_syllables()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        raise

