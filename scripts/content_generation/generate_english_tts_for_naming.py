#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate English TTS audio files for concepts from Chinese Word Recognition notes.

This script:
1. Extracts unique English concepts from chinese_word_recognition_notes table
2. Generates TTS audio files using Google Cloud Text-to-Speech API
3. Saves audio files to media/audio/english_naming/ directory
4. Uses naming convention: {concept}.english.mp3

This is the first step for generating English naming deck later.
"""

import os
import sys
import sqlite3
from pathlib import Path
from google.cloud import texttospeech

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
OUTPUT_DIR = PROJECT_ROOT / "media" / "audio" / "english_naming"

# Google Cloud TTS Configuration
LANGUAGE_CODE = "en-US"
VOICE_NAME = "en-US-Neural2-F"  # High-quality female voice, can be changed to "en-US-Neural2-M" for male
AUDIO_ENCODING = texttospeech.AudioEncoding.MP3


def get_unique_concepts():
    """Extract unique English concepts from chinese_word_recognition_notes table"""
    if not DB_PATH.exists():
        print(f"❌ Error: Database not found at {DB_PATH}")
        return []
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Get all unique concepts (non-null, non-empty)
        cursor.execute("""
            SELECT DISTINCT concept 
            FROM chinese_word_recognition_notes 
            WHERE concept IS NOT NULL AND concept != ''
            ORDER BY concept
        """)
        concepts = [row[0] for row in cursor.fetchall()]
        print(f"📚 Found {len(concepts)} unique English concepts")
        return concepts
    finally:
        conn.close()


def sanitize_filename(concept: str) -> str:
    """Sanitize concept name for use as filename"""
    # Replace spaces and special characters with underscores
    # Keep alphanumeric and underscores only
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', concept)
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized


def generate_audio_for_concept(client, concept: str) -> bool:
    """Generate TTS audio for a single concept"""
    # Sanitize filename
    filename = f"{sanitize_filename(concept)}.english.mp3"
    output_path = OUTPUT_DIR / filename
    
    # Skip if file already exists
    if output_path.exists():
        print(f"  ⏭️  Skipping '{concept}' - file already exists: {filename}")
        return True
    
    try:
        # Set the text input to be synthesized
        synthesis_input = texttospeech.SynthesisInput(text=concept)
        
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
        
        # Write the audio content to file
        with open(output_path, "wb") as out:
            out.write(response.audio_content)
        
        print(f"  ✅ Generated: {concept} -> {filename}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error generating audio for '{concept}': {e}")
        return False


def main():
    """Main function to generate English TTS audio files"""
    print("🎙️  Starting English TTS generation for naming concepts...")
    print(f"   Database: {DB_PATH}")
    print(f"   Output directory: {OUTPUT_DIR}")
    
    # Check for Google Cloud credentials
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        print("\n❌ ERROR: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        print("   Please set it to the path of your JSON key file before running.")
        print("   Example: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
        return
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   ✅ Output directory ready: {OUTPUT_DIR}")
    
    # Get unique concepts
    concepts = get_unique_concepts()
    if not concepts:
        print("❌ No concepts found in database")
        return
    
    print(f"\n📝 Sample concepts (first 10):")
    for concept in concepts[:10]:
        print(f"   - {concept}")
    
    # Initialize Google Cloud TTS client
    try:
        client = texttospeech.TextToSpeechClient()
        print(f"\n✅ Google Cloud TTS client initialized")
    except Exception as e:
        print(f"\n❌ Error initializing TTS client: {e}")
        print("   Please ensure your credentials are correct and you have enabled the Text-to-Speech API.")
        return
    
    # Generate audio for each concept
    print(f"\n🎤 Generating audio files...")
    print(f"   Total concepts to process: {len(concepts)}")
    print(f"{'='*60}\n")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    import sys
    
    for i, concept in enumerate(concepts, 1):
        # Check if file already exists
        filename = f"{sanitize_filename(concept)}.english.mp3"
        if (OUTPUT_DIR / filename).exists():
            skip_count += 1
            # Only print skip message every 50 files to reduce output
            if i % 50 == 0 or i <= 10:
                print(f"[{i}/{len(concepts)}] ⏭️  Skipping '{concept}' - already exists", flush=True)
            continue
        
        # Print progress for new files
        print(f"[{i}/{len(concepts)}] 🎤 Generating: {concept}", flush=True)
        
        if generate_audio_for_concept(client, concept):
            success_count += 1
        else:
            error_count += 1
        
        # Progress update every 10 files
        if i % 10 == 0:
            print(f"\n📊 Progress: {i}/{len(concepts)} processed | ✅ Generated: {success_count} | ⏭️  Skipped: {skip_count} | ❌ Errors: {error_count}\n", flush=True)
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"✅ Generation complete!")
    print(f"   Total concepts: {len(concepts)}")
    print(f"   Successfully generated: {success_count}")
    print(f"   Skipped (already exists): {skip_count}")
    print(f"   Errors: {error_count}")
    print(f"   Output directory: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

