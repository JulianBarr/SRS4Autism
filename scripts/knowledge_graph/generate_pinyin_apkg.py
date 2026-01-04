#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate .apkg file for pinyin sample deck with templates, notes, and audio files.

This script creates a complete Anki package (.apkg) that includes:
1. Updated note types (Element and Syllable) with proper templates
2. Sample notes (element "a" and syllable "ma1")
3. All TTS audio files
4. Media files (images)

Importing this .apkg will automatically:
- Create/update the note types with correct templates
- Add the sample notes
- Include all audio files
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import genanki
except ImportError:
    print("❌ genanki not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "genanki"])
    import genanki

PROJECT_ROOT = project_root
OUTPUT_DIR = PROJECT_ROOT / "data" / "pinyin_sample_deck"
AUDIO_DIR = PROJECT_ROOT / "media" / "audio" / "pinyin"
MEDIA_DIR = PROJECT_ROOT / "media" / "pinyin"
TEMPLATE_DIR = PROJECT_ROOT / "scripts" / "templates" / "pinyin"

# Fixed IDs for note types (to avoid conflicts)
ELEMENT_MODEL_ID = 1985090401
SYLLABLE_MODEL_ID = 1985090402
DECK_ID = 1985090403


def load_template(filename: str) -> str:
    """Load a template file from the templates directory."""
    template_path = TEMPLATE_DIR / filename
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")
    return template_path.read_text(encoding='utf-8')


def create_element_model():
    """Create CUMA - Pinyin Element note type model"""
    
    fields = [
        {'name': 'Element'},
        {'name': 'ExampleChar'},
        {'name': 'Picture'},
        {'name': 'Tone1'},
        {'name': 'Tone2'},
        {'name': 'Tone3'},
        {'name': 'Tone4'},
        {'name': '_Remarks'},
        {'name': '_KG_Map'},
    ]
    
    # Load CSS and templates from files
    css = load_template('styles.css')
    front_template = load_template('pinyin_element_card_front.html')
    back_template = load_template('pinyin_element_card_back.html')
    
    model = genanki.Model(
        ELEMENT_MODEL_ID,
        'CUMA - Pinyin Element',
        fields=fields,
        templates=[
            {
                'name': 'Element Card',
                'qfmt': front_template,
                'afmt': back_template,
            }
        ],
        css=css,
    )
    
    return model


def create_syllable_model():
    """Create CUMA - Pinyin Syllable note type model with 6 cards"""
    
    fields = [
        {'name': 'ElementToLearn'},
        {'name': 'Syllable'},
        {'name': 'WordPinyin'},
        {'name': 'WordHanzi'},
        {'name': 'WordPicture'},
        {'name': 'WordAudio'},          # Audio
        {'name': 'Tone1'},              # Tone Variation 1
        {'name': 'Tone2'},              # Tone Variation 2
        {'name': 'Tone3'},              # Tone Variation 3
        {'name': 'Tone4'},              # Tone Variation 4
        {'name': 'Confusor1'},          # Distractor Syllable 1
        {'name': 'ConfusorPicture1'},   # Distractor Image 1
        {'name': 'Confusor2'},          # Distractor Syllable 2
        {'name': 'ConfusorPicture2'},   # Distractor Image 2
        {'name': 'Confusor3'},          # Distractor Syllable 3
        {'name': 'ConfusorPicture3'},   # Distractor Image 3
        {'name': '_Remarks'},
        {'name': '_KG_Map'},
    ]
    
    # Load CSS and templates from files
    css = load_template('styles.css')
    
    # Card 0: Element Card (Teaching)
    card0_front = load_template('pinyin_syllable_card_element_front.html')
    card0_back = load_template('pinyin_syllable_card_element_back.html')
    
    # Card 1: Word to Pinyin (Teaching)
    card1_front = load_template('pinyin_syllable_card_word_to_pinyin_front.html')
    card1_back = load_template('pinyin_syllable_card_word_to_pinyin_back.html')
    
    # Card 2-4: MCQ cards
    mcq_recent_front = load_template('pinyin_syllable_card_mcq_recent_front.html')
    mcq_recent_back = load_template('pinyin_syllable_card_mcq_recent_back.html')
    mcq_tone_front = load_template('pinyin_syllable_card_mcq_tone_front.html')
    mcq_tone_back = load_template('pinyin_syllable_card_mcq_tone_back.html')
    mcq_confusor_front = load_template('pinyin_syllable_card_mcq_confusor_front.html')
    mcq_confusor_back = load_template('pinyin_syllable_card_mcq_confusor_back.html')
    
    # Card 5: Pinyin to Word (MCQ with Pictures)
    card5_front = load_template('pinyin_syllable_card_pinyin_to_word_front.html')
    card5_back = load_template('pinyin_syllable_card_pinyin_to_word_back.html')
    
    model = genanki.Model(
        SYLLABLE_MODEL_ID,
        'CUMA - Pinyin Syllable',
        fields=fields,
        templates=[
            {
                'name': 'Element Card',
                'qfmt': card0_front,
                'afmt': card0_back,
            },
            {
                'name': 'Word to Pinyin',
                'qfmt': card1_front,
                'afmt': card1_back,
            },
            {
                'name': 'MCQ Recent',
                'qfmt': mcq_recent_front,
                'afmt': mcq_recent_back,
            },
            {
                'name': 'MCQ Tone',
                'qfmt': mcq_tone_front,
                'afmt': mcq_tone_back,
            },
            {
                'name': 'MCQ Confusor',
                'qfmt': mcq_confusor_front,
                'afmt': mcq_confusor_back,
            },
            {
                'name': 'Pinyin to Word',
                'qfmt': card5_front,
                'afmt': card5_back,
            },
        ],
        css=css,
    )
    
    return model


def create_apkg():
    """Create the complete .apkg file"""
    
    print("=" * 80)
    print("Generate Pinyin Sample Deck .apkg File")
    print("=" * 80)
    
    # Create models
    print("\n1. Creating note type models...")
    element_model = create_element_model()
    syllable_model = create_syllable_model()
    print("   ✅ Element model created")
    print("   ✅ Syllable model created (6 cards)")
    
    # Create deck
    print("\n2. Creating deck...")
    deck = genanki.Deck(DECK_ID, '拼音学习样本 (Pinyin Sample)')
    
    # Add element note
    print("\n3. Adding sample notes...")
    element_note = genanki.Note(
        model=element_model,
        fields=[
            'a',  # Element
            '啊',  # ExampleChar
            '<img src="ahh.png">',  # Picture
            'ā',  # Tone1 (proper tone mark)
            'á',  # Tone2
            'ǎ',  # Tone3
            'à',  # Tone4
            'Sample element note for review',  # _Remarks
            '{"0": [{"kp": "pinyin-element-a", "skill": "form_to_sound", "weight": 1.0}]}',  # _KG_Map
        ]
    )
    deck.add_note(element_note)
    print("   ✅ Added element 'a' note")
    
    # Add syllable note
    syllable_note = genanki.Note(
        model=syllable_model,
        fields=[
            'a',  # ElementToLearn
            'mā',  # Syllable (proper tone mark)
            'mā mā',  # WordPinyin
            '妈妈',  # WordHanzi
            '<img src="mommy.png">',  # WordPicture
            '[sound:mā mā.mp3]',  # WordAudio
            'mā',  # Tone1
            'má',  # Tone2
            'mǎ',  # Tone3
            'mà',  # Tone4
            'mē',  # Confusor1
            '<img src="ahh.png">',  # ConfusorPicture1
            'mō',  # Confusor2
            '<img src="ahh.png">',  # ConfusorPicture2
            'mī',  # Confusor3
            '<img src="ahh.png">',  # ConfusorPicture3
            'Sample syllable note for review',  # _Remarks
            json.dumps({
                "0": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}],
                "1": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 1.0}],
                "2": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "3": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "4": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 0.8}],
                "5": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}]
            }),  # _KG_Map
        ]
    )
    deck.add_note(syllable_note)
    print("   ✅ Added syllable 'ma1' (mā) note")
    
    # Create package
    print("\n4. Packaging deck...")
    package = genanki.Package(deck)
    package.models = [element_model, syllable_model]
    
    # Add media files
    print("\n5. Adding media files...")
    media_files = []
    
    # Audio files - only include syllable audio
    # Element audio skipped per Pinyin Review.md: "don't do this now"
    audio_files = [
        # Syllable audio - using TTS with Chinese characters
        'mo1.mp3', 'mā.mp3', 'mā mā.mp3'
    ]
    
    print("   ℹ️  Note: Pinyin element audio (a1, a2, a3, a4, a) not included")
    print("      - Per requirements: 'don't do this now'")
    print("      - Caregiver will read element tones manually")
    print("      - Only syllable audio included (TTS with Chinese characters)")
    
    for audio_file in audio_files:
        audio_path = AUDIO_DIR / audio_file
        if audio_path.exists():
            # Use absolute path to ensure genanki can find the file
            media_files.append(str(audio_path.resolve()))
            print(f"   ✅ Added audio: {audio_file}")
        else:
            print(f"   ⚠️  Audio file not found: {audio_file}")
    
    # Image files
    image_files = ['ahh.png', 'mommy.png']
    for image_file in image_files:
        image_path = MEDIA_DIR / image_file
        if image_path.exists():
            # Use absolute path to ensure genanki can find the file
            media_files.append(str(image_path.resolve()))
            print(f"   ✅ Added image: {image_file} ({image_path.resolve()})")
        else:
            print(f"   ⚠️  Image file not found: {image_file}")
    
    # Bell sound (optional)
    bell_path = AUDIO_DIR / "bell.wav"
    if bell_path.exists():
        media_files.append(str(bell_path))
        print(f"   ✅ Added bell sound: bell.wav")
    else:
        print(f"   ⚠️  Bell sound not found (optional): bell.wav")
    
    package.media_files = media_files
    
    # Write package
    output_file = OUTPUT_DIR / "Pinyin_Sample_Deck.apkg"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n6. Writing .apkg file...")
    package.write_to_file(str(output_file))
    
    print(f"\n{'='*80}")
    print(f"✅ .apkg file created successfully!")
    print(f"   Location: {output_file}")
    print(f"   Size: {output_file.stat().st_size / 1024:.1f} KB")
    print(f"\n📋 To import:")
    print(f"   1. Open Anki")
    print(f"   2. File → Import")
    print(f"   3. Select: {output_file}")
    print(f"   4. The note types and sample notes will be imported automatically!")
    print(f"   5. All audio files and images will be included")
    print(f"{'='*80}")
    
    return output_file


if __name__ == "__main__":
    create_apkg()

