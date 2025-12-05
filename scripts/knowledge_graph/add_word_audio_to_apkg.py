#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate WordAudio files using Google TTS and add them to the .apkg file.

This script:
1. Generates audio files for the 5 sample notes using Google TTS
2. Adds them to the .apkg file with proper media mapping
"""

import os
import sys
import sqlite3
import zipfile
import tempfile
import json
import shutil
from pathlib import Path
from google.cloud import texttospeech

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
AUDIO_DIR = PROJECT_ROOT / "media" / "audio" / "pinyin"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Google Cloud TTS Configuration
LANGUAGE_CODE = "cmn-CN"
VOICE_NAME = "cmn-CN-Wavenet-A"
AUDIO_ENCODING = texttospeech.AudioEncoding.MP3


def generate_audio_file(client, text: str, filename: str) -> bool:
    """Generate TTS audio using Google Cloud TTS"""
    output_path = AUDIO_DIR / filename
    
    if output_path.exists():
        print(f"  ⏭️  Skipping '{text}' - file already exists: {filename}")
        return True
    
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
        
        print(f"  ✅ Generated: {text} -> {filename}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error generating {filename}: {e}")
        return False


def add_audio_to_apkg(apkg_path: Path, audio_files: dict):
    """Add audio files to .apkg with proper media mapping"""
    
    print("\n3. Adding audio files to .apkg...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg
        with zipfile.ZipFile(apkg_path, 'r') as z:
            z.extractall(tmpdir_path)
        
        # Read existing media mapping
        media_mapping = {}
        media_file_path = tmpdir_path / "media"
        
        if media_file_path.exists() and media_file_path.is_file():
            try:
                with open(media_file_path, 'r', encoding='utf-8') as f:
                    media_mapping = json.loads(f.read())
                print(f"   📋 Loaded existing media mapping: {len(media_mapping)} entries")
            except:
                media_mapping = {}
        
        # Find next available numeric ID
        max_id = 0
        if media_mapping:
            for key in media_mapping.keys():
                try:
                    num_id = int(key)
                    if num_id > max_id:
                        max_id = num_id
                except:
                    pass
        
        # Add audio files to mapping and copy to tmpdir
        next_id = max_id + 1
        added_files = []
        
        for audio_filename, chinese_text in audio_files.items():
            audio_path = AUDIO_DIR / audio_filename
            
            if not audio_path.exists():
                print(f"   ⚠️  Audio file not found: {audio_filename}")
                continue
            
            # Add to media mapping
            media_mapping[str(next_id)] = audio_filename
            
            # Copy to tmpdir with numeric name
            numeric_name = str(next_id)
            target_path = tmpdir_path / numeric_name
            shutil.copy2(audio_path, target_path)
            
            print(f"   ✅ Added {audio_filename} -> {numeric_name}")
            added_files.append((numeric_name, audio_filename))
            next_id += 1
        
        # Write updated media mapping
        with open(media_file_path, 'w', encoding='utf-8') as f:
            json.dump(media_mapping, f, ensure_ascii=False, indent=2)
        
        print(f"   ✅ Updated media mapping: {len(media_mapping)} entries")
        
        # Repackage .apkg
        print("\n4. Repackaging .apkg with audio files...")
        
        with zipfile.ZipFile(apkg_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print(f"   ✅ Updated .apkg: {apkg_path}")
        return True


def main():
    """Main function"""
    print("=" * 80)
    print("Generate WordAudio Files and Add to .apkg")
    print("=" * 80)
    
    # Check for Google Cloud credentials
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        cred_path = PROJECT_ROOT / "backend" / "google-credentials.json"
        if cred_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(cred_path)
            print(f"✅ Using credentials: {cred_path}")
        else:
            print("❌ ERROR: GOOGLE_APPLICATION_CREDENTIALS not set and credentials file not found")
            print(f"   Expected at: {cred_path}")
            return
    
    # Audio files to generate (filename -> Chinese text)
    audio_files = {
        '妈妈.mp3': '妈妈',      # mom
        '爸爸.mp3': '爸爸',      # dad
        '摸.mp3': '摸',          # touch
        '妹妹.mp3': '妹妹',      # younger sister
        '米.mp3': '米'           # rice
    }
    
    # Initialize Google Cloud TTS client
    try:
        client = texttospeech.TextToSpeechClient()
        print("✅ Google Cloud TTS client initialized\n")
    except Exception as e:
        print(f"❌ Error initializing TTS client: {e}")
        print("   Please ensure your credentials are correct and you have enabled the Text-to-Speech API.")
        return
    
    # Generate audio files
    print("1. Generating audio files with Google TTS...")
    success_count = 0
    
    for filename, chinese_text in audio_files.items():
        print(f"   🎤 Generating: {chinese_text} -> {filename}")
        if generate_audio_file(client, chinese_text, filename):
            success_count += 1
    
    if success_count == 0:
        print("\n❌ No audio files generated. Cannot proceed.")
        return
    
    print(f"\n   ✅ Generated {success_count}/{len(audio_files)} audio files")
    
    # Add audio files to .apkg
    if not APKG_PATH.exists():
        print(f"\n❌ .apkg file not found: {APKG_PATH}")
        return
    
    print(f"\n2. Adding {success_count} audio files to .apkg...")
    add_audio_to_apkg(APKG_PATH, audio_files)
    
    print("\n✅ Complete!")
    print(f"\n📦 Updated .apkg: {APKG_PATH}")
    print("   Audio files are now included and will play when Card 1 back is displayed")


if __name__ == "__main__":
    main()
