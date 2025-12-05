#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Restore WordAudio fields from existing TTS audio files in temp_audio directory.
Maps audio files to WordHanzi and updates the deck.
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
import re
import shutil
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
TEMP_AUDIO_DIR = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "temp_audio"
PROJECT_PREFIX = "cm"

def sanitize_for_filename(text: str) -> str:
    """Sanitize text for use in filename"""
    text = re.sub(r'\[sound:([^\]]+)\]', r'\1', text)
    text = re.sub(r'\.(mp3|wav|ogg)$', '', text, flags=re.IGNORECASE)
    sanitized = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', text)
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized

def restore_wordaudio():
    """Restore WordAudio fields from existing audio files"""
    print("=" * 80)
    print("Restore WordAudio from Existing Audio Files")
    print("=" * 80)
    
    # Map audio files to WordHanzi
    print("\n📁 Scanning audio files...")
    audio_files = {}
    
    if TEMP_AUDIO_DIR.exists():
        for audio_file in TEMP_AUDIO_DIR.glob("*.mp3"):
            filename = audio_file.name
            # Extract word from filename: cm_tts_zh_[word].mp3
            if filename.startswith(f"{PROJECT_PREFIX}_tts_zh_"):
                word_part = filename[len(f"{PROJECT_PREFIX}_tts_zh_"):-4]  # Remove prefix and .mp3
                # Try to extract Chinese characters
                # The word might be sanitized, so we need to match by filename
                audio_files[word_part] = (audio_file, filename)
        
        print(f"   Found {len(audio_files)} audio files")
    else:
        print(f"   ⚠️  Audio directory not found: {TEMP_AUDIO_DIR}")
        return
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        print("\n📦 Extracting .apkg...")
        with zipfile.ZipFile(APKG_PATH, 'r') as z:
            z.extractall(tmpdir_path)
        
        db = tmpdir_path / "collection.anki21"
        if not db.exists():
            db = tmpdir_path / "collection.anki2"
        
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT models FROM col")
        models = json.loads(cursor.fetchone()[0])
        
        # Find syllable model
        syllable_model_id = None
        syllable_model = None
        
        for mid_str, model in models.items():
            if model.get('name') == 'CUMA - Pinyin Syllable':
                syllable_model_id = int(mid_str)
                syllable_model = model
                break
        
        if not syllable_model:
            print("❌ Syllable model not found")
            conn.close()
            return
        
        field_names = [f['name'] for f in syllable_model.get('flds', [])]
        word_audio_idx = field_names.index('WordAudio') if 'WordAudio' in field_names else -1
        
        if word_audio_idx < 0:
            print("❌ WordAudio field not found in model")
            conn.close()
            return
        
        # Find or create media folder
        # In Anki .apkg, media files are in the root or in a 'media' folder
        media_dir = tmpdir_path / "media"
        if media_dir.exists() and not media_dir.is_dir():
            # If it's a file, remove it and create directory
            print(f"   ⚠️  Warning: 'media' exists but is not a directory, removing...")
            media_dir.unlink()
        
        if not media_dir.exists():
            media_dir.mkdir()
        
        print(f"\n📁 Copying audio files to media folder...")
        copied_count = 0
        audio_map = {}  # Map WordHanzi to filename
        
        # Get all notes first to build mapping
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
        notes = cursor.fetchall()
        
        for note_id, flds_str in notes:
            fields = flds_str.split('\x1f')
            while len(fields) < len(field_names):
                fields.append('')
            
            field_dict = dict(zip(field_names, fields))
            word_hanzi = field_dict.get('WordHanzi', '').strip()
            
            if word_hanzi:
                # Try to find matching audio file
                # First try exact match
                sanitized_word = sanitize_for_filename(word_hanzi)
                matching_file = None
                matching_filename = None
                
                # Try exact match
                if sanitized_word in audio_files:
                    matching_file, matching_filename = audio_files[sanitized_word]
                else:
                    # Try partial match (word might be in filename)
                    for word_part, (audio_path, filename) in audio_files.items():
                        if sanitized_word in word_part or word_part in sanitized_word:
                            matching_file = audio_path
                            matching_filename = filename
                            break
                
                if matching_file and matching_filename:
                    # Copy to media folder
                    dest_path = media_dir / matching_filename
                    if not dest_path.exists():
                        shutil.copy2(matching_file, dest_path)
                        copied_count += 1
                    
                    audio_map[word_hanzi] = matching_filename
        
        print(f"   ✅ Copied {copied_count} audio files")
        
        # Update WordAudio fields
        print(f"\n🔧 Updating WordAudio fields...")
        updated_count = 0
        
        for note_id, flds_str in notes:
            fields = flds_str.split('\x1f')
            while len(fields) < len(field_names):
                fields.append('')
            
            field_dict = dict(zip(field_names, fields))
            word_hanzi = field_dict.get('WordHanzi', '').strip()
            
            if word_hanzi and word_hanzi in audio_map:
                filename = audio_map[word_hanzi]
                new_word_audio = f"[sound:{filename}]"
                fields[word_audio_idx] = new_word_audio
                updated_flds = '\x1f'.join(fields)
                cursor.execute("UPDATE notes SET flds = ? WHERE id = ?", (updated_flds, note_id))
                updated_count += 1
        
        conn.commit()
        print(f"   ✅ Updated {updated_count} notes with WordAudio")
        
        conn.close()
        
        # Repackage
        print("\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(APKG_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print("✅ WordAudio restored!")

if __name__ == "__main__":
    restore_wordaudio()

