#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deploy Pinyin Typing Deck - Level 2

This script:
1. Reads balanced_typing_course.json
2. Creates/updates "CUMA - Pinyin Typing" note type in Anki
3. Generates Anki cards for all lessons
4. Exports to pinyin_typing_level2.apkg
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Optional

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

# Configuration
PROJECT_ROOT = project_root
TEMPLATE_DIR = PROJECT_ROOT / "scripts" / "templates" / "typing"
OUTPUT_DIR = PROJECT_ROOT / "data" / "typing_deck"
COURSE_JSON = PROJECT_ROOT / "data" / "cloze_typing_course.json"
OUTPUT_APKG = OUTPUT_DIR / "pinyin_typing_level2.apkg"

# Ensure directories exist
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Fixed IDs (avoid conflicts with existing models)
TYPING_MODEL_ID = 1985090501
DECK_ID = 1985090502


def read_template(filename: str) -> str:
    """Load a template file from the templates directory."""
    template_path = TEMPLATE_DIR / filename
    if not template_path.exists():
        # Return minimal fallback template
        if 'front' in filename.lower():
            return '<div class="typing-card">{{Image}}<br>{{FullPinyinRaw}} (Masked at index {{TargetIndex}})<br>{{Audio}}</div>'
        elif 'back' in filename.lower():
            return '{{FrontSide}}<hr id="answer"><div class="answer-section"><strong>Answer:</strong> {{TargetSyllable}}</div>'
        elif 'css' in filename.lower():
            return '''
.card {
    font-family: Arial, sans-serif;
    font-size: 20px;
}
.typing-card {
    text-align: center;
    padding: 20px;
}
.answer-section {
    margin-top: 20px;
    font-size: 24px;
    font-weight: bold;
}
'''
        return ""
    return template_path.read_text(encoding='utf-8')


def create_typing_model() -> genanki.Model:
    """Create CUMA - Pinyin Typing note type model."""
    
    # Fields as specified: Front, Back, Sound, Image, TypingInput
    # But we'll map from the actual data structure
    fields = [
        {'name': 'Front'},      # Pinyin with missing letter (generated from FullPinyinRaw + TargetIndex)
        {'name': 'Back'},       # Full Pinyin + Hanzi
        {'name': 'Sound'},      # Audio file
        {'name': 'Image'},      # Image file
        {'name': 'TypingInput'}, # The target syllable to type (answer)
        # Additional fields for data integrity
        {'name': 'Hanzi'},
        {'name': 'FullPinyinRaw'},
        {'name': 'TargetIndex'},
        {'name': 'LessonID'},
    ]
    
    # Load CSS
    css = read_template('typing.css')
    
    # Load templates
    front_template = read_template('typing_card_front.html')
    back_template = read_template('typing_card_back.html')
    
    templates = [{
        'name': 'Typing Card',
        'qfmt': front_template,
        'afmt': back_template,
    }]
    
    model = genanki.Model(
        TYPING_MODEL_ID,
        'CUMA - Pinyin Typing',
        fields=fields,
        templates=templates,
        css=css
    )
    
    return model


def load_course_data() -> Dict:
    """Load the cloze typing course JSON."""
    if not COURSE_JSON.exists():
        print(f"❌ Error: Course file not found: {COURSE_JSON}")
        print(f"   Please ensure cloze_typing_course.json exists in the project root.")
        sys.exit(1)
    
    with open(COURSE_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_cards_from_course(course_data: Dict, model: genanki.Model) -> List[genanki.Note]:
    """Create Anki notes from course data."""
    notes = []
    media_files = []
    
    for lesson_id, items in course_data.items():
        if not items:
            continue
        
        for item in items:
            # Extract media files if present
            if item.get('audio'):
                audio_path = PROJECT_ROOT / 'media' / 'audio' / item['audio']
                if audio_path.exists():
                    media_files.append(str(audio_path))
            
            if item.get('image'):
                # Handle image paths - could be relative or absolute
                if item['image'].startswith('http'):
                    # Skip remote URLs
                    image_src = item['image']
                else:
                    image_path = PROJECT_ROOT / 'media' / item['image']
                    if image_path.exists():
                        media_files.append(str(image_path))
                        # Use filename only for Anki media
                        image_src = Path(item['image']).name
                    else:
                        image_src = item['image']
            else:
                image_src = ''
            
            # Format audio for Anki
            audio_field = ''
            if item.get('audio'):
                audio_filename = Path(item['audio']).name if not item['audio'].startswith('http') else item['audio']
                audio_field = f'[sound:{audio_filename}]'
            
            # Format image for Anki
            image_field = ''
            if image_src:
                if image_src.startswith('http'):
                    image_field = f'<img src="{image_src}">'
                else:
                    image_field = f'<img src="{image_src}">'
            
            # Generate Front field: Pinyin with masked target syllable
            full_pinyin = item.get('full_pinyin_raw', '')
            target_index = item.get('target_index', 0)
            syllables = full_pinyin.split()
            front_pinyin = ''
            if target_index < len(syllables):
                masked_syllables = syllables.copy()
                masked_syllables[target_index] = '[____]'
                front_pinyin = ' '.join(masked_syllables)
            else:
                front_pinyin = full_pinyin
            
            # Back field: Full Pinyin + Hanzi
            hanzi = item.get('hanzi', '')
            back_field = f'{full_pinyin}<br><strong>{hanzi}</strong>'
            
            # Create note with field mapping:
            # Front, Back, Sound, Image, TypingInput, Hanzi, FullPinyinRaw, TargetIndex, LessonID
            note = genanki.Note(
                model=model,
                fields=[
                    front_pinyin,                              # Front: Masked pinyin
                    back_field,                                # Back: Full pinyin + hanzi
                    audio_field,                               # Sound: Audio file
                    image_field,                               # Image: Image file
                    item.get('target_syllable', ''),          # TypingInput: The answer
                    hanzi,                                     # Hanzi: Original data
                    full_pinyin,                               # FullPinyinRaw: Original data
                    str(target_index),                         # TargetIndex: Original data
                    lesson_id                                  # LessonID: Original data
                ],
                tags=[f'Lesson_{lesson_id}', 'PinyinTyping', 'Level2']
            )
            
            notes.append(note)
    
    return notes, media_files


def main():
    """Main execution flow."""
    print("=" * 80)
    print("Deploy Pinyin Typing Deck - Level 2")
    print("=" * 80)
    
    # Load course data
    print("\n1. Loading course data...")
    course_data = load_course_data()
    total_items = sum(len(items) for items in course_data.values())
    print(f"   ✅ Loaded {len(course_data)} lessons with {total_items} total items")
    
    # Create model
    print("\n2. Creating note type model...")
    typing_model = create_typing_model()
    print("   ✅ Typing model created")
    
    # Create deck
    print("\n3. Creating deck...")
    deck = genanki.Deck(DECK_ID, 'SRS4Autism::Pinyin::Level2_Typing')
    print("   ✅ Deck created")
    
    # Create notes
    print("\n4. Creating notes...")
    notes, media_files = create_cards_from_course(course_data, typing_model)
    for note in notes:
        deck.add_note(note)
    print(f"   ✅ Created {len(notes)} notes")
    
    # Package deck
    print("\n5. Packaging deck...")
    package = genanki.Package(deck)
    if media_files:
        package.media_files = list(set(media_files))  # Remove duplicates
        print(f"   ✅ Added {len(package.media_files)} media files")
    
    package.write_to_file(str(OUTPUT_APKG))
    print(f"   ✅ Deck exported to: {OUTPUT_APKG}")
    
    print("\n" + "=" * 80)
    print("✅ Success! Deck created successfully.")
    print(f"   Total notes: {len(notes)}")
    print(f"   Media files: {len(media_files)}")
    print(f"   Output: {OUTPUT_APKG}")
    print("=" * 80)


if __name__ == "__main__":
    main()

