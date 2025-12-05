#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate the full pinyin deck with all notes from the original deck.
This script:
1. Extracts all notes from the original deck
2. Converts tone numbers to proper tone marks
3. Generates TTS audio files for all words
4. Updates the sample deck with all notes
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

from scripts.knowledge_graph.pinyin_parser import extract_tone, add_tone_to_final

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
ORIGINAL_APKG = PROJECT_ROOT / "data" / "content_db" / "语言语文__拼音.apkg"
SAMPLE_APKG = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
TEMP_AUDIO_DIR = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "temp_audio"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Google Cloud TTS Configuration
LANGUAGE_CODE = "cmn-CN"
VOICE_NAME = "cmn-CN-Wavenet-A"
AUDIO_ENCODING = texttospeech.AudioEncoding.MP3
PROJECT_PREFIX = "cm"


def sanitize_for_filename(text: str) -> str:
    """Sanitize text for use in filename"""
    text = re.sub(r'\[sound:([^\]]+)\]', r'\1', text)
    text = re.sub(r'\.(mp3|wav|ogg)$', '', text, flags=re.IGNORECASE)
    sanitized = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', text)
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized


def get_file_hash(filepath: Path) -> str:
    """Calculate MD5 hash of a file"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()


def convert_tone_number_to_mark(pinyin: str) -> str:
    """Convert pinyin with tone number to tone mark (e.g., 'ma1' -> 'mā')"""
    pinyin_no_tone, tone = extract_tone(pinyin)
    if tone:
        return add_tone_to_final(pinyin_no_tone, tone)
    return pinyin


def generate_tone_variations(base_syllable: str) -> list:
    """Generate all 4 tone variations"""
    pinyin_no_tone, _ = extract_tone(base_syllable)
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(pinyin_no_tone, tone)
        variations.append(toned)
    return variations


def generate_audio_file(client, text: str, semantic_name: str, max_retries: int = 3) -> tuple[Path, str]:
    """Generate TTS audio file with proper naming"""
    sanitized_name = sanitize_for_filename(semantic_name)
    base_filename = f"{PROJECT_PREFIX}_tts_zh_{sanitized_name}.mp3"
    output_path = TEMP_AUDIO_DIR / base_filename
    
    if output_path.exists():
        return output_path, base_filename
    
    for attempt in range(max_retries):
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=LANGUAGE_CODE,
                name=VOICE_NAME
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=AUDIO_ENCODING)
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            with open(output_path, "wb") as out:
                out.write(response.audio_content)
            
            return output_path, base_filename
            
        except Exception as e:
            if attempt < max_retries - 1:
                import time
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
            else:
                print(f"  ❌ Error for '{text}': {e}")
                return None, None
    
    return None, None


def extract_notes_from_original(original_apkg: Path) -> list:
    """Extract all notes from original deck"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        with zipfile.ZipFile(original_apkg, 'r') as z:
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
            print("❌ Syllable model not found in original deck")
            conn.close()
            return []
        
        # Get original field names
        original_field_names = [f['name'] for f in syllable_model.get('flds', [])]
        
        # Get all notes
        cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (syllable_model_id,))
        notes = cursor.fetchall()
        
        extracted_notes = []
        for note_id, flds_str in notes:
            fields = flds_str.split('\x1f')
            while len(fields) < len(original_field_names):
                fields.append('')
            field_dict = dict(zip(original_field_names, fields))
            extracted_notes.append(field_dict)
        
        conn.close()
        return extracted_notes


def update_sample_deck_with_all_notes(original_notes: list, audio_files: dict):
    """Update sample deck with all notes from original deck"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract sample .apkg
        print("\n📦 Extracting sample .apkg...")
        with zipfile.ZipFile(SAMPLE_APKG, 'r') as z:
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
            print("❌ Syllable model not found in sample deck")
            conn.close()
            return
        
        field_names = [f['name'] for f in syllable_model.get('flds', [])]
        
        # Delete existing notes
        print("\n🗑️  Deleting existing notes...")
        cursor.execute("DELETE FROM notes WHERE mid = ?", (syllable_model_id,))
        cursor.execute("DELETE FROM cards WHERE nid NOT IN (SELECT id FROM notes)")
        deleted_count = cursor.rowcount
        print(f"   ✅ Deleted {deleted_count} existing notes")
        
        # Add all notes from original deck
        print(f"\n➕ Adding {len(original_notes)} notes from original deck...")
        
        import time
        current_time = int(time.time() * 1000)
        
        added_count = 0
        for i, original_note in enumerate(original_notes):
            # Convert tone numbers to tone marks
            syllable = original_note.get('Syllable', '').strip()
            if syllable:
                syllable = convert_tone_number_to_mark(syllable)
            
            word_pinyin = original_note.get('WordPinyin', '').strip()
            if word_pinyin:
                # Convert each syllable in word_pinyin
                syllables = word_pinyin.split()
                converted_syllables = [convert_tone_number_to_mark(s) for s in syllables]
                word_pinyin = ' '.join(converted_syllables)
            
            # Generate tone variations
            pinyin_no_tone, _ = extract_tone(syllable)
            tone_variations = generate_tone_variations(pinyin_no_tone) if pinyin_no_tone else ['', '', '', '']
            
            # Generate confusors (simple approach)
            confusors = []
            if pinyin_no_tone:
                base_initial = pinyin_no_tone[0] if pinyin_no_tone else ''
                base_final = pinyin_no_tone[1:] if len(pinyin_no_tone) > 1 else pinyin_no_tone
                confusors = [
                    add_tone_to_final('b' + base_final if base_final else 'ba', 1),
                    add_tone_to_final('p' + base_final if base_final else 'pa', 2),
                    add_tone_to_final(pinyin_no_tone, 3 if syllable != add_tone_to_final(pinyin_no_tone, 3) else 4)
                ]
            
            # Get audio filename
            word_hanzi = original_note.get('WordHanzi', '').strip()
            audio_filename = ''
            if word_hanzi and word_hanzi in audio_files:
                audio_path, filename = audio_files[word_hanzi]
                if filename:
                    audio_filename = f"[sound:{filename}]"
            
            # Build field values
            field_values = {
                'ElementToLearn': original_note.get('ElementToLearn', ''),
                'Syllable': syllable,
                'WordPinyin': word_pinyin,
                'WordHanzi': word_hanzi,
                'WordPicture': original_note.get('WordPicture', ''),
                'WordAudio': audio_filename,
                '_Remarks': original_note.get('_Remarks', ''),
                '_KG_Map': original_note.get('_KG_Map', ''),
                'Tone1': tone_variations[0] if len(tone_variations) > 0 else '',
                'Tone2': tone_variations[1] if len(tone_variations) > 1 else '',
                'Tone3': tone_variations[2] if len(tone_variations) > 2 else '',
                'Tone4': tone_variations[3] if len(tone_variations) > 3 else '',
                'Confusor1': confusors[0] if len(confusors) > 0 else '',
                'ConfusorPicture1': '',
                'Confusor2': confusors[1] if len(confusors) > 1 else '',
                'ConfusorPicture2': '',
                'Confusor3': confusors[2] if len(confusors) > 2 else '',
                'ConfusorPicture3': ''
            }
            
            # Create fields list in correct order
            fields = [field_values.get(name, '') for name in field_names]
            flds_str = '\x1f'.join(fields)
            
            # Create note
            note_id = current_time + i
            cursor.execute(
                "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (note_id, f"guid{note_id}", syllable_model_id, current_time, -1, '', flds_str, fields[field_names.index('WordHanzi')] if 'WordHanzi' in field_names else '', 0, 0, '')
            )
            
            # Create cards for each template
            num_templates = len(syllable_model.get('tmpls', []))
            for ord_val in range(num_templates):
                card_id = current_time + i * 1000 + ord_val
                cursor.execute(
                    "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (card_id, note_id, 1, ord_val, current_time, -1, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
                )
            
            added_count += 1
            if (i + 1) % 50 == 0:
                print(f"   Progress: {i + 1}/{len(original_notes)} notes added...")
        
        conn.commit()
        print(f"   ✅ Added {added_count} notes with {added_count * num_templates} cards")
        
        # Copy audio files to media folder
        media_dir = tmpdir_path
        print(f"\n📁 Copying audio files to media folder...")
        copied_count = 0
        
        for word_hanzi, (audio_path, filename) in audio_files.items():
            if audio_path and audio_path.exists():
                dest_path = media_dir / filename
                if not dest_path.exists():
                    import shutil
                    shutil.copy2(audio_path, dest_path)
                    copied_count += 1
        
        print(f"   ✅ Copied {copied_count} audio files")
        
        conn.close()
        
        # Repackage .apkg
        print(f"\n📦 Repackaging .apkg...")
        with zipfile.ZipFile(SAMPLE_APKG, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print(f"✅ .apkg updated with all notes")


def main():
    print("=" * 80)
    print("Populate Full Pinyin Deck")
    print("=" * 80)
    
    if not ORIGINAL_APKG.exists():
        print(f"❌ Original deck not found: {ORIGINAL_APKG}")
        return
    
    if not SAMPLE_APKG.exists():
        print(f"❌ Sample deck not found: {SAMPLE_APKG}")
        return
    
    # Extract notes from original deck
    print("\n📋 Extracting notes from original deck...")
    original_notes = extract_notes_from_original(ORIGINAL_APKG)
    print(f"   ✅ Extracted {len(original_notes)} notes")
    
    if not original_notes:
        print("⚠️  No notes found in original deck")
        return
    
    # Collect unique words for audio generation
    unique_words = {}
    for note in original_notes:
        word_hanzi = note.get('WordHanzi', '').strip()
        if word_hanzi:
            unique_words[word_hanzi] = note.get('Syllable', '').strip()
    
    print(f"\n📚 Found {len(unique_words)} unique words for audio generation")
    
    # Generate audio files
    audio_files = {}
    if TTS_AVAILABLE:
        if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
            cred_path = PROJECT_ROOT / "backend" / "google-credentials.json"
            if cred_path.exists():
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(cred_path)
        
        try:
            client = texttospeech.TextToSpeechClient()
            print("\n🎤 Generating audio files...")
            
            success_count = 0
            for i, (word_hanzi, syllable) in enumerate(unique_words.items()):
                if (i + 1) % 20 == 0:
                    print(f"   Progress: {i + 1}/{len(unique_words)} words...")
                
                audio_path, filename = generate_audio_file(client, word_hanzi, word_hanzi)
                if audio_path and filename:
                    audio_files[word_hanzi] = (audio_path, filename)
                    success_count += 1
            
            print(f"   ✅ Generated {success_count} audio files")
        except Exception as e:
            print(f"⚠️  TTS error: {e}")
            print("   Continuing without audio files...")
    else:
        print("⚠️  Google TTS not available, skipping audio generation")
    
    # Update sample deck with all notes
    update_sample_deck_with_all_notes(original_notes, audio_files)
    
    print("\n✅ Complete! Deck now has all notes from original deck")


if __name__ == "__main__":
    main()


