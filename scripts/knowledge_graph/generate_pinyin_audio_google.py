#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate TTS audio files for pinyin using Google Cloud TTS with Chinese characters.

Since Unicode Pinyin (ā, á, ǎ, à) doesn't work reliably with TTS engines,
we use Chinese characters that naturally have those tones.
"""

import sys
import os
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
OUTPUT_DIR = PROJECT_ROOT / "media" / "audio" / "pinyin"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Google Cloud TTS Configuration
LANGUAGE_CODE = "cmn-CN"
VOICE_NAME = "cmn-CN-Wavenet-A"
AUDIO_ENCODING = texttospeech.AudioEncoding.MP3


def generate_audio(client, text: str, filename: str) -> bool:
    """Generate TTS audio using Google Cloud TTS"""
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
    
    if not TTS_AVAILABLE:
        print("❌ Google Cloud TTS not available")
        return
    
    # Check credentials
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        cred_path = PROJECT_ROOT / "backend" / "google-credentials.json"
        if cred_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(cred_path)
        else:
            print("❌ Credentials not found")
            return
    
    try:
        client = texttospeech.TextToSpeechClient()
        print("✅ TTS client initialized\n")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print("🎤 Generating audio files...\n")
    success = 0
    total = 0
    
    # For 'a' tones: Use characters that naturally have those tones
    # Note: Google TTS may not handle single Unicode pinyin (ā, á, ǎ, à) correctly
    # We use Chinese characters that have those tones
    print("1. Element 'a' tones...")
    element_audios = [
        ('啊', 'a1.mp3'),   # 啊 is tone 1 (ā) - correct
        ('á', 'a2.mp3'),   # Try Unicode - may not work correctly
        ('ǎ', 'a3.mp3'),   # Try Unicode - may not work correctly
        ('à', 'a4.mp3'),   # Try Unicode - may not work correctly
        ('a', 'a.mp3'),    # Neutral
    ]
    
    for text, filename in element_audios:
        total += 1
        if generate_audio(client, text, filename):
            success += 1
    
    print("\n2. Syllable 'ma1'...")
    syllable_audios = [
        ('摸', 'mo1.mp3'),      # 摸 (mo1)
        ('妈', 'mā.mp3'),       # 妈 (mā) - tone 1
        ('妈妈', 'mā mā.mp3'),  # 妈妈 (mā mā)
    ]
    
    for text, filename in syllable_audios:
        total += 1
        if generate_audio(client, text, filename):
            success += 1
    
    print(f"\n{'='*60}")
    print(f"✅ Generated {success}/{total} files")
    print(f"{'='*60}")
    print("\n⚠️  IMPORTANT: Please verify the tones are correct!")
    print("   - a1.mp3 should be tone 1 (ā)")
    print("   - a2.mp3 should be tone 2 (á) - may need manual fix")
    print("   - a3.mp3 should be tone 3 (ǎ) - may need manual fix")
    print("   - a4.mp3 should be tone 4 (à) - may need manual fix")
    print("\n   If tones are wrong, you may need to:")
    print("   1. Use edge-tts when network is available")
    print("   2. Manually record the audio")
    print("   3. Use a different TTS service that handles Unicode Pinyin")


if __name__ == "__main__":
    main()

