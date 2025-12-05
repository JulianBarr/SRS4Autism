#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate TTS audio files for pinyin learning in CUMA using Google TTS.
Follows media file management guidelines: cm_tts_zh_[word].mp3

This script:
1. Extracts all unique syllables and words from the pinyin deck
2. Generates TTS audio files using Google Cloud TTS with proper naming
3. Updates WordAudio fields in notes to use new naming convention
4. Adds audio files to the .apkg media folder
"""

import sys
import os
import sqlite3
import zipfile
import tempfile
import json
import re
import hashlib
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    backend_env = project_root / "backend" / ".env"
    if backend_env.exists():
        load_dotenv(backend_env)
except ImportError:
    pass

try:
    from google.cloud import texttospeech
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
TEMP_AUDIO_DIR = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "temp_audio"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Google Cloud TTS Configuration
LANGUAGE_CODE = "cmn-CN"
VOICE_NAME = "cmn-CN-Wavenet-A"  # High-quality Chinese voice
AUDIO_ENCODING = texttospeech.AudioEncoding.MP3

# Media naming prefix
PROJECT_PREFIX = "cm"


def sanitize_for_filename(text: str) -> str:
    """Sanitize text for use in filename"""
    # Remove [sound:] tags if present
    text = re.sub(r'\[sound:([^\]]+)\]', r'\1', text)
    # Remove file extension if present
    text = re.sub(r'\.(mp3|wav|ogg)$', '', text, flags=re.IGNORECASE)
    # Replace spaces and special characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', text)
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized


def get_file_hash(filepath: Path) -> str:
    """Calculate MD5 hash of a file to check for duplicates"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()


def generate_audio_file(client, text: str, semantic_name: str, max_retries: int = 3) -> tuple[Path, str]:
    """
    Generate TTS audio file with proper naming convention.
    Returns: (file_path, final_filename)
    """
    # Create semantic filename: cm_tts_zh_[name].mp3
    sanitized_name = sanitize_for_filename(semantic_name)
    base_filename = f"{PROJECT_PREFIX}_tts_zh_{sanitized_name}.mp3"
    output_path = TEMP_AUDIO_DIR / base_filename
    
    # Check if file already exists
    if output_path.exists():
        print(f"  ⏭️  File already exists: {base_filename}")
        return output_path, base_filename
    
    # Retry logic for network issues
    for attempt in range(max_retries):
        try:
            # Set the text input to be synthesized
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Build the voice request
            voice = texttospeech.VoiceSelectionParams(
                language_code=LANGUAGE_CODE,
                name=VOICE_NAME
            )
            
            # Select the type of audio file
            audio_config = texttospeech.AudioConfig(
                audio_encoding=AUDIO_ENCODING
            )
            
            # Perform the text-to-speech request
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            # Write the response to the output file
            with open(output_path, "wb") as out:
                out.write(response.audio_content)
            
            return output_path, base_filename
            
        except Exception as e:
            if attempt < max_retries - 1:
                import time
                wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                print(f"  ⚠️  Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ Error generating audio for '{text}' after {max_retries} attempts: {e}")
                return None, None
    
    return None, None


def extract_audio_needs(apkg_path: Path) -> dict:
    """Extract all unique words and syllables that need audio"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        with zipfile.ZipFile(apkg_path, 'r') as z:
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
            return {}
        
        field_names = [f['name'] for f in syllable_model.get('flds', [])]
        
        # Get all notes
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
        notes = cursor.fetchall()
        
        # Collect unique words and syllables
        audio_needs = {}  # {word_hanzi: (syllable, word_pinyin)}
        
        for note_id, flds_str in notes:
            fields = flds_str.split('\x1f')
            while len(fields) < len(field_names):
                fields.append('')
            
            field_dict = dict(zip(field_names, fields))
            word_hanzi = field_dict.get('WordHanzi', '').strip()
            syllable = field_dict.get('Syllable', '').strip()
            word_pinyin = field_dict.get('WordPinyin', '').strip()
            
            if word_hanzi:
                # Use word_hanzi as key to avoid duplicates
                if word_hanzi not in audio_needs:
                    audio_needs[word_hanzi] = (syllable, word_pinyin)
        
        conn.close()
        return audio_needs


def update_apkg_with_audio(apkg_path: Path, audio_files: dict):
    """Update .apkg file with new audio files and update WordAudio fields"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg
        print("\n📦 Extracting .apkg...")
        with zipfile.ZipFile(apkg_path, 'r') as z:
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
        
        # Copy audio files to media folder
        media_dir = tmpdir_path
        print(f"\n📁 Copying audio files to media folder...")
        copied_count = 0
        
        for word_hanzi, (audio_path, filename) in audio_files.items():
            if audio_path and audio_path.exists():
                dest_path = media_dir / filename
                # Check for collisions
                if dest_path.exists():
                    # Check if it's the same file
                    if get_file_hash(audio_path) == get_file_hash(dest_path):
                        print(f"  ⏭️  {filename} already exists (same content)")
                    else:
                        # Different content, append counter
                        counter = 1
                        while True:
                            new_filename = f"{PROJECT_PREFIX}_tts_zh_{sanitize_for_filename(word_hanzi)}_{counter}.mp3"
                            new_dest_path = media_dir / new_filename
                            if not new_dest_path.exists():
                                dest_path = new_dest_path
                                filename = new_filename
                                break
                            counter += 1
                        print(f"  ⚠️  Collision detected, renamed to: {filename}")
                
                # Copy file
                import shutil
                shutil.copy2(audio_path, dest_path)
                copied_count += 1
                print(f"  ✅ Copied: {filename}")
        
        print(f"   ✅ Copied {copied_count} audio files")
        
        # Update WordAudio fields in notes
        print(f"\n🔧 Updating WordAudio fields in notes...")
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
        notes = cursor.fetchall()
        
        updated_count = 0
        for note_id, flds_str in notes:
            fields = flds_str.split('\x1f')
            while len(fields) < len(field_names):
                fields.append('')
            
            field_dict = dict(zip(field_names, fields))
            word_hanzi = field_dict.get('WordHanzi', '').strip()
            
            if word_hanzi and word_hanzi in audio_files:
                audio_path, filename = audio_files[word_hanzi]
                if filename:
                    # Update WordAudio field to use new naming
                    new_word_audio = f"[sound:{filename}]"
                    if word_audio_idx >= 0:
                        fields[word_audio_idx] = new_word_audio
                        updated_flds = '\x1f'.join(fields)
                        cursor.execute("UPDATE notes SET flds = ? WHERE id = ?", (updated_flds, note_id))
                        updated_count += 1
        
        conn.commit()
        print(f"   ✅ Updated {updated_count} notes")
        conn.close()
        
        # Repackage .apkg
        print(f"\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(apkg_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print(f"✅ .apkg updated")


def main():
    print("=" * 80)
    print("Generate Pinyin TTS Audio Files with Proper Naming")
    print("=" * 80)
    
    if not TTS_AVAILABLE:
        print("❌ Google Cloud TTS not available")
        print("   Please install: pip install google-cloud-texttospeech")
        return
    
    # Check credentials
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        cred_path = PROJECT_ROOT / "backend" / "google-credentials.json"
        if cred_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(cred_path)
            print(f"✅ Using credentials: {cred_path}")
        else:
            print("❌ Google credentials not found")
            print(f"   Expected at: {cred_path}")
            return
    
    if not APKG_PATH.exists():
        print(f"❌ APKG file not found: {APKG_PATH}")
        return
    
    try:
        client = texttospeech.TextToSpeechClient()
        print("✅ TTS client initialized\n")
    except Exception as e:
        print(f"❌ Error initializing TTS client: {e}")
        return
    
    # Extract audio needs from .apkg
    print("📋 Extracting audio needs from .apkg...")
    audio_needs = extract_audio_needs(APKG_PATH)
    print(f"   Found {len(audio_needs)} unique words needing audio\n")
    
    if not audio_needs:
        print("⚠️  No words found that need audio")
        return
    
    # Generate audio files
    print("🎤 Generating audio files...\n")
    audio_files = {}  # {word_hanzi: (audio_path, filename)}
    success_count = 0
    skip_count = 0
    
    for word_hanzi, (syllable, word_pinyin) in audio_needs.items():
        # Use word_hanzi for TTS (Chinese characters)
        # Use word_hanzi for filename (semantic name)
        print(f"  Processing: {word_hanzi} ({syllable})")
        
        audio_path, filename = generate_audio_file(client, word_hanzi, word_hanzi)
        
        if audio_path and filename:
            audio_files[word_hanzi] = (audio_path, filename)
            success_count += 1
            print(f"    ✅ Generated: {filename}")
        else:
            skip_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   ✅ Generated: {success_count}")
    print(f"   ⏭️  Skipped: {skip_count}")
    
    if success_count > 0:
        # Update .apkg with audio files
        update_apkg_with_audio(APKG_PATH, audio_files)
        print(f"\n✅ Complete! Audio files generated and added to .apkg")
    else:
        print(f"\n⚠️  No audio files were generated")


if __name__ == "__main__":
    main()

