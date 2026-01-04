#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Pinyin Deck v2 - Self-contained, idempotent deck generator.

This script:
1. Uses genanki to build the deck from scratch (NO zip manipulation)
2. Loads templates from scripts/templates/pinyin/
3. Generates audio using Google TTS (idempotent - skips existing files)
4. Creates notes with all 18 fields populated
5. Exports to Pinyin_Deck_v2.apkg
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import genanki
except ImportError:
    print("❌ genanki not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "genanki"])
    import genanki

try:
    from google.cloud import texttospeech
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("⚠️  Google Cloud TTS not available. Audio generation will be skipped.")

try:
    from dotenv import load_dotenv
    backend_env = project_root / "backend" / ".env"
    if backend_env.exists():
        load_dotenv(backend_env)
except ImportError:
    pass

# Configuration
PROJECT_ROOT = project_root
TEMPLATE_DIR = PROJECT_ROOT / "scripts" / "templates" / "pinyin"
AUDIO_DIR = PROJECT_ROOT / "media" / "audio" / "pinyin"
OUTPUT_DIR = PROJECT_ROOT / "data" / "pinyin_sample_deck"
OUTPUT_APKG = OUTPUT_DIR / "Pinyin_Deck_v2.apkg"

# Ensure directories exist
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Fixed IDs for note types (to avoid conflicts)
SYLLABLE_MODEL_ID = 1985090402
DECK_ID = 1985090403

# Google Cloud TTS Configuration
LANGUAGE_CODE = "cmn-CN"
VOICE_NAME = "cmn-CN-Wavenet-A"
AUDIO_ENCODING = texttospeech.AudioEncoding.MP3


def read_template(filename: str) -> str:
    """
    Load a template file from scripts/templates/pinyin/.
    
    Args:
        filename: Name of the template file (e.g., 'pinyin_syllable.css')
    
    Returns:
        Content of the template file as string
    
    Raises:
        FileNotFoundError: If template file doesn't exist
    """
    template_path = TEMPLATE_DIR / filename
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")
    return template_path.read_text(encoding='utf-8')


def generate_audio(text: str, filename: str, client: Optional[texttospeech.TextToSpeechClient] = None) -> Tuple[bool, Optional[Path]]:
    """
    Generate TTS audio using Google Cloud TTS.
    
    Idempotent: Checks if file exists before generating.
    
    Args:
        text: Chinese text to synthesize (e.g., "妈妈" for "mā mā")
        filename: Output filename (e.g., "mā mā.mp3")
        client: Google TTS client (if None, will skip generation)
    
    Returns:
        Tuple of (success: bool, file_path: Optional[Path])
    """
    output_path = AUDIO_DIR / filename
    
    # Idempotency check
    if output_path.exists():
        print(f"  ⏭️  Skipping '{text}' - file already exists: {filename}")
        return True, output_path
    
    if not TTS_AVAILABLE or client is None:
        print(f"  ⚠️  Skipping '{text}' - TTS not available: {filename}")
        return False, None
    
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
        return True, output_path
        
    except Exception as e:
        print(f"  ❌ Error generating '{text}': {e}")
        return False, None


def create_syllable_model() -> genanki.Model:
    """
    Create CUMA - Pinyin Syllable note type model with 6 cards.
    
    Uses the complete 18-field schema:
    ElementToLearn, Syllable, WordPinyin, WordHanzi, WordPicture, WordAudio,
    Tone1..4, Confusor1..3, ConfusorPicture1..3, _Remarks, _KG_Map
    """
    
    # Define all 18 fields
    fields = [
        {'name': 'ElementToLearn'},
        {'name': 'Syllable'},
        {'name': 'WordPinyin'},
        {'name': 'WordHanzi'},
        {'name': 'WordPicture'},
        {'name': 'WordAudio'},
        {'name': 'Tone1'},
        {'name': 'Tone2'},
        {'name': 'Tone3'},
        {'name': 'Tone4'},
        {'name': 'Confusor1'},
        {'name': 'ConfusorPicture1'},
        {'name': 'Confusor2'},
        {'name': 'ConfusorPicture2'},
        {'name': 'Confusor3'},
        {'name': 'ConfusorPicture3'},
        {'name': '_Remarks'},
        {'name': '_KG_Map'},
    ]
    
    # Load CSS from pinyin_syllable.css
    try:
        css = read_template('pinyin_syllable.css')
    except FileNotFoundError:
        print("⚠️  pinyin_syllable.css not found, using styles.css as fallback")
        css = read_template('styles.css')
    
    # Load all card templates
    templates = []
    
    # Card 0: Element Card (Teaching)
    try:
        card0_front = read_template('pinyin_syllable_card_element_front.html')
        card0_back = read_template('pinyin_syllable_card_element_back.html')
    except FileNotFoundError:
        print("⚠️  Element card templates not found, using simple fallback")
        card0_front = '<div class="pinyin-syllable-card"><p class="syllable-pinyin">{{Syllable}}</p></div>'
        card0_back = '{{FrontSide}}<hr id="answer"><div class="answer-section"><p><strong>Element:</strong> {{ElementToLearn}}</p></div>'
    
    templates.append({
        'name': 'Element Card',
        'qfmt': card0_front,
        'afmt': card0_back,
    })
    
    # Card 1: Word to Pinyin (Teaching)
    card1_front = read_template('pinyin_syllable_card_word_to_pinyin_front.html')
    card1_back = read_template('pinyin_syllable_card_word_to_pinyin_back.html')
    templates.append({
        'name': 'Word to Pinyin',
        'qfmt': card1_front,
        'afmt': card1_back,
    })
    
    # Card 2: MCQ Recent
    mcq_recent_front = read_template('pinyin_syllable_card_mcq_recent_front.html')
    mcq_recent_back = read_template('pinyin_syllable_card_mcq_recent_back.html')
    templates.append({
        'name': 'MCQ Recent',
        'qfmt': mcq_recent_front,
        'afmt': mcq_recent_back,
    })
    
    # Card 3: MCQ Tone
    mcq_tone_front = read_template('pinyin_syllable_card_mcq_tone_front.html')
    mcq_tone_back = read_template('pinyin_syllable_card_mcq_tone_back.html')
    templates.append({
        'name': 'MCQ Tone',
        'qfmt': mcq_tone_front,
        'afmt': mcq_tone_back,
    })
    
    # Card 4: MCQ Confusor
    mcq_confusor_front = read_template('pinyin_syllable_card_mcq_confusor_front.html')
    mcq_confusor_back = read_template('pinyin_syllable_card_mcq_confusor_back.html')
    templates.append({
        'name': 'MCQ Confusor',
        'qfmt': mcq_confusor_front,
        'afmt': mcq_confusor_back,
    })
    
    # Card 5: Pinyin to Word
    card5_front = read_template('pinyin_syllable_card_pinyin_to_word_front.html')
    card5_back = read_template('pinyin_syllable_card_pinyin_to_word_back.html')
    templates.append({
        'name': 'Pinyin to Word',
        'qfmt': card5_front,
        'afmt': card5_back,
    })
    
    model = genanki.Model(
        SYLLABLE_MODEL_ID,
        'CUMA - Pinyin Syllable',
        fields=fields,
        templates=templates,
        css=css,
    )
    
    return model


def get_syllable_data() -> List[Dict]:
    """
    Get syllable data for deck generation.
    
    This is a placeholder function. Replace with your actual data source.
    
    Returns:
        List of dictionaries, each containing syllable data with all required fields
    """
    # Example data structure - replace with your actual data source
    return [
        {
            'ElementToLearn': 'a',
            'Syllable': 'mā',
            'WordPinyin': 'mā mā',
            'WordHanzi': '妈妈',
            'WordPicture': '<img src="mommy.png">',
            'WordAudioText': '妈妈',  # Chinese text for TTS
            'Tone1': 'mā',
            'Tone2': 'má',
            'Tone3': 'mǎ',
            'Tone4': 'mà',
            'Confusor1': 'mē',
            'ConfusorPicture1': '<img src="ahh.png">',
            'Confusor2': 'mō',
            'ConfusorPicture2': '<img src="ahh.png">',
            'Confusor3': 'mī',
            'ConfusorPicture3': '<img src="ahh.png">',
            '_Remarks': 'Sample syllable note for review',
            '_KG_Map': {
                "0": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}],
                "1": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 1.0}],
                "2": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "3": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "4": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "5": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}]
            }
        },
        # Add more syllables here...
    ]


def main():
    """Main execution flow."""
    print("=" * 80)
    print("Generate Pinyin Deck v2")
    print("=" * 80)
    
    # Setup: Initialize Google TTS client
    tts_client = None
    if TTS_AVAILABLE:
        if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
            cred_path = PROJECT_ROOT / "backend" / "google-credentials.json"
            if cred_path.exists():
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(cred_path)
            else:
                print("⚠️  Google credentials not found. Audio generation will be skipped.")
        else:
            try:
                tts_client = texttospeech.TextToSpeechClient()
                print("✅ TTS client initialized")
            except Exception as e:
                print(f"⚠️  Failed to initialize TTS client: {e}")
    else:
        print("⚠️  TTS not available. Audio generation will be skipped.")
    
    # Create model
    print("\n1. Creating note type model...")
    syllable_model = create_syllable_model()
    print("   ✅ Syllable model created (6 cards, 18 fields)")
    
    # Create deck
    print("\n2. Creating deck...")
    deck = genanki.Deck(DECK_ID, '拼音学习 v2 (Pinyin Learning v2)')
    
    # Get syllable data
    print("\n3. Loading syllable data...")
    syllable_data = get_syllable_data()
    print(f"   ✅ Loaded {len(syllable_data)} syllables")
    
    # Data loop: Generate audio and create notes
    print("\n4. Processing syllables...")
    media_files = []
    audio_files_generated = []
    
    for idx, data in enumerate(syllable_data, 1):
        print(f"\n   Processing syllable {idx}/{len(syllable_data)}: {data.get('Syllable', 'N/A')}")
        
        # Generate audio
        word_audio_text = data.get('WordAudioText', '')
        if word_audio_text:
            # Create filename from WordPinyin (sanitize for filename)
            word_pinyin = data.get('WordPinyin', '')
            audio_filename = f"{word_pinyin}.mp3"
            
            success, audio_path = generate_audio(word_audio_text, audio_filename, tts_client)
            if success and audio_path:
                audio_files_generated.append(audio_path)
                # WordAudio field should contain [sound:filename.mp3]
                data['WordAudio'] = f"[sound:{audio_filename}]"
            else:
                data['WordAudio'] = ''
        else:
            data['WordAudio'] = ''
        
        # Create note with all 18 fields
        # Ensure _KG_Map is JSON string
        kg_map = data.get('_KG_Map', {})
        if isinstance(kg_map, dict):
            kg_map_str = json.dumps(kg_map, ensure_ascii=False)
        else:
            kg_map_str = str(kg_map)
        
        note = genanki.Note(
            model=syllable_model,
            fields=[
                data.get('ElementToLearn', ''),
                data.get('Syllable', ''),
                data.get('WordPinyin', ''),
                data.get('WordHanzi', ''),
                data.get('WordPicture', ''),
                data.get('WordAudio', ''),  # Already formatted as [sound:...]
                data.get('Tone1', ''),
                data.get('Tone2', ''),
                data.get('Tone3', ''),
                data.get('Tone4', ''),
                data.get('Confusor1', ''),
                data.get('ConfusorPicture1', ''),
                data.get('Confusor2', ''),
                data.get('ConfusorPicture2', ''),
                data.get('Confusor3', ''),
                data.get('ConfusorPicture3', ''),
                data.get('_Remarks', ''),
                kg_map_str,
            ]
        )
        
        deck.add_note(note)
        print(f"   ✅ Added note for {data.get('Syllable', 'N/A')}")
    
    # Packaging: Add media files
    print("\n5. Packaging deck with media files...")
    
    # Add generated audio files
    for audio_path in audio_files_generated:
        if audio_path and audio_path.exists():
            media_files.append(str(audio_path.resolve()))
            print(f"   ✅ Added audio: {audio_path.name}")
    
    # Note: Add image files here if needed
    # Example:
    # image_dir = PROJECT_ROOT / "media" / "pinyin"
    # for image_file in ['mommy.png', 'ahh.png']:
    #     image_path = image_dir / image_file
    #     if image_path.exists():
    #         media_files.append(str(image_path.resolve()))
    #         print(f"   ✅ Added image: {image_file}")
    
    # Create package
    package = genanki.Package(deck)
    package.models = [syllable_model]
    if media_files:
        package.media_files = media_files
    
    # Write package
    print(f"\n6. Writing .apkg file...")
    OUTPUT_APKG.parent.mkdir(parents=True, exist_ok=True)
    package.write_to_file(str(OUTPUT_APKG))
    
    print(f"\n{'='*80}")
    print(f"✅ Deck generated successfully!")
    print(f"   Location: {OUTPUT_APKG}")
    print(f"   Size: {OUTPUT_APKG.stat().st_size / 1024:.1f} KB")
    print(f"   Notes: {len(syllable_data)}")
    print(f"   Audio files: {len(audio_files_generated)}")
    print(f"\n📋 To import:")
    print(f"   1. Open Anki")
    print(f"   2. File → Import")
    print(f"   3. Select: {OUTPUT_APKG}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

