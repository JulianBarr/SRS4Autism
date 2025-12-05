#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate TTS audio files for pinyin sample deck using Google Cloud TTS.

This script generates audio files for:
- Element "a": a1.mp3, a2.mp3, a3.mp3, a4.mp3, a.mp3
- Syllable "ma1": mo1.mp3, mā.mp3, mā mā.mp3
- Bell sound: bell.wav (needs to be provided separately)

Uses Google Cloud TTS with Chinese strings (not pinyin).
For element tones, uses Chinese characters/words that have "a" sound with those tones.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Try to load .env file
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
OUTPUT_DIR = PROJECT_ROOT / "media" / "audio" / "pinyin"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Google Cloud TTS Configuration
LANGUAGE_CODE = "cmn-CN"
VOICE_NAME = "cmn-CN-Wavenet-A"
AUDIO_ENCODING = texttospeech.AudioEncoding.MP3


def generate_audio(client, text: str, filename: str) -> bool:
    """Generate TTS audio using Google Cloud TTS with Chinese string"""
    output_path = OUTPUT_DIR / filename
    
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
        print(f"  ❌ Error: {e}")
        return False


def main():
    print("=" * 80)
    print("Generate Pinyin TTS Audio Files (Google Cloud TTS)")
    print("=" * 80)
    print("   Method: Chinese strings (not pinyin)")
    
    if not TTS_AVAILABLE:
        print("❌ Google Cloud TTS not available")
        print("   Please install: pip install google-cloud-texttospeech")
        return
    
    # Check credentials
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        cred_path = PROJECT_ROOT / "backend" / "google-credentials.json"
        if cred_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(cred_path)
            print(f"   ✅ Found credentials: {cred_path}")
        else:
            print("❌ Credentials not found")
            return
    
    try:
        client = texttospeech.TextToSpeechClient()
        print("   ✅ TTS client initialized\n")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print("🎤 Generating audio files...\n")
    success = 0
    total = 0
    
    # Element audio: Per Pinyin Review.md, audio is "don't do this now"
    # Caregiver will read element tones manually
    print("1. Element 'a' tones - SKIPPED")
    print("   ℹ️  Per requirements: 'don't do this now' - caregiver will read")
    # Skip element audio generation
    
    print("\n2. Syllable 'ma1' (using Chinese characters)...")
    syllable_audios = [
        ('摸', 'mo1.mp3'),      # mo1 (摸)
        ('妈', 'mā.mp3'),       # mā (妈)
        ('妈妈', 'mā mā.mp3'),  # mā mā (妈妈)
    ]
    
    for text, filename in syllable_audios:
        total += 1
        if generate_audio(client, text, filename):
            success += 1
    
    print(f"\n{'='*60}")
    print(f"✅ Generated {success}/{total} files")
    print(f"{'='*60}")
    print("\n📝 Summary:")
    print("   - Element audio: Skipped (caregiver reads)")
    print("   - Syllable audio: Generated using Chinese characters (TTS)")


if __name__ == "__main__":
    main()
