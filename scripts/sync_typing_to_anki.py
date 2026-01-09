#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync Pinyin Typing Course to Anki via Anki-Connect

This script:
1. Reads data/cloze_typing_course.json
2. Cleans HTML wrappers from image and audio fields
3. Pushes notes to Anki using the CUMA-Pinyin-Typing-Lv2 model
"""

import sys
import json
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import requests
except ImportError:
    print("❌ requests not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DECK_NAME = "SRS4Autism::Pinyin::Level2_Typing"
MODEL_NAME = "CUMA-Pinyin-Typing-Lv2-v2"
COURSE_JSON = project_root / "data" / "cloze_typing_course.json"


def clean_filename(value: str) -> str:
    """
    Robust filename extraction - removes ALL wrappers and returns just the filename.
    
    Examples:
    - '<img src="foo.png">' -> 'foo.png'
    - '<img src='foo.png'>' -> 'foo.png'
    - '[sound:bar.mp3]' -> 'bar.mp3'
    - '"baz.jpg"' -> 'baz.jpg'
    - "'qux.png'" -> 'qux.png'
    - 'baz.jpg' -> 'baz.jpg' (already clean)
    """
    if not value or not isinstance(value, str):
        return ""
    
    value = value.strip()
    
    # Remove quotes if present
    value = value.strip('"').strip("'")
    
    # Handle image: <img src="filename.png"> or <img src='filename.png'>
    img_match = re.search(r'<img\s+src=["\']([^"\']+)["\']', value, re.IGNORECASE)
    if img_match:
        return img_match.group(1)
    
    # Handle audio: [sound:filename.mp3]
    sound_match = re.search(r'\[sound:([^\]]+)\]', value, re.IGNORECASE)
    if sound_match:
        return sound_match.group(1)
    
    # If no wrapper found, assume it's already a filename
    return value


def format_audio_field(filename: str) -> str:
    """
    Format audio filename for Anki field.
    Always wraps in [sound:...] tag.
    Returns: [sound:filename.mp3]
    """
    if not filename:
        return ""
    filename_clean = clean_filename(filename)
    if not filename_clean:
        return ""
    return f"[sound:{filename_clean}]"


def format_image_field(filename: str) -> str:
    """
    Format image filename for Anki field.
    Always wraps in <img src="..."> tag.
    Returns: <img src="filename.png">
    """
    if not filename:
        return ""
    filename_clean = clean_filename(filename)
    if not filename_clean:
        return ""
    return f'<img src="{filename_clean}">'


def generate_unique_id(lesson_id: str, hanzi: str, target_index: int, target_syllable: str) -> str:
    """
    Generate unique ID for note.
    Format: "{lesson_id}_{hanzi}_{target_index}_{target_syllable}"
    Example: "1_沙发_0_fa" (lesson 1, hanzi 沙发, index 0, syllable fa)
    
    This ensures uniqueness even when the same hanzi appears multiple times
    with different target syllables.
    """
    # Sanitize hanzi and target_syllable for use in ID (remove spaces, special chars)
    clean_hanzi = re.sub(r'[^\w\u4e00-\u9fff]', '', str(hanzi))
    clean_syllable = re.sub(r'[^\w]', '', str(target_syllable))
    return f"{lesson_id}_{clean_hanzi}_{target_index}_{clean_syllable}"


def invoke_anki_connect(action: str, params: dict = None) -> any:
    """Invoke an Anki-Connect action."""
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    
    try:
        response = requests.post(ANKI_CONNECT_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("error"):
            raise Exception(f"Anki-Connect error: {result['error']}")
        
        return result.get("result")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to connect to Anki-Connect: {e}")


def load_course_data() -> dict:
    """Load the course JSON file."""
    if not COURSE_JSON.exists():
        raise FileNotFoundError(
            f"Course file not found: {COURSE_JSON}\n"
            "Please ensure data/cloze_typing_course.json exists."
        )
    
    with open(COURSE_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def sync_course_to_anki(course_data: dict) -> dict:
    """Sync course data to Anki."""
    notes_added = 0
    notes_failed = 0
    errors = []
    
    for lesson_id, items in course_data.items():
        if not items:
            continue
        
        print(f"\nProcessing Lesson {lesson_id} ({len(items)} items)...")
        
        for item in items:
            try:
                # Generate unique ID to prevent duplicates
                # Format: "{lesson_id}_{hanzi}_{target_index}_{target_syllable}"
                unique_id = generate_unique_id(
                    lesson_id=str(lesson_id),
                    hanzi=item.get('hanzi', ''),
                    target_index=item.get('target_index', 0),
                    target_syllable=item.get('target_syllable', '')
                )
                
                # Extract and format media fields
                # First strip any existing wrappers, then apply correct Anki formatting
                audio_field = format_audio_field(item.get('audio', ''))
                image_field = format_image_field(item.get('image', ''))
                
                # Map fields to model structure:
                # UniqueId, Hanzi, TargetSyllable, TargetIndex, FullPinyinRaw, Audio, Image, LessonID
                field_names = [
                    "UniqueId",
                    "Hanzi",
                    "TargetSyllable",
                    "TargetIndex",
                    "FullPinyinRaw",
                    "Audio",
                    "Image",
                    "LessonID"
                ]
                
                fields = [
                    unique_id,                        # UniqueId (first field for uniqueness)
                    item.get('hanzi', ''),           # Hanzi
                    item.get('target_syllable', ''), # TargetSyllable
                    str(item.get('target_index', 0)), # TargetIndex
                    item.get('full_pinyin_raw', ''), # FullPinyinRaw
                    audio_field,                     # Audio (formatted as [sound:...])
                    image_field,                     # Image (formatted as <img src="...">)
                    str(lesson_id)                   # LessonID
                ]
                
                # Create fields dictionary
                fields_dict = dict(zip(field_names, fields))
                
                # Add note to Anki
                note_id = invoke_anki_connect("addNote", {
                    "note": {
                        "deckName": DECK_NAME,
                        "modelName": MODEL_NAME,
                        "fields": fields_dict,
                        "tags": [
                            f"Lesson_{lesson_id}",
                            "PinyinTyping",
                            "Level2"
                        ]
                    }
                })
                
                notes_added += 1
                if notes_added % 10 == 0:
                    print(f"  ✓ Added {notes_added} notes...")
                
            except Exception as e:
                notes_failed += 1
                error_msg = f"Failed to add note for Lesson {lesson_id}: {str(e)}"
                errors.append(error_msg)
                print(f"  ✗ {error_msg}")
    
    return {
        "notes_added": notes_added,
        "notes_failed": notes_failed,
        "errors": errors
    }


def main():
    """Main execution flow."""
    print("=" * 80)
    print("Sync Pinyin Typing Course to Anki")
    print("=" * 80)
    print()
    
    # Check Anki-Connect connection
    try:
        version = invoke_anki_connect("version")
        print(f"✅ Anki-Connect is running (version: {version})")
    except Exception as e:
        print(f"❌ Cannot connect to Anki-Connect: {e}")
        print("\nPlease ensure:")
        print("1. Anki is running")
        print("2. AnkiConnect add-on is installed")
        print("3. Run scripts/setup_anki_env.py first to create deck and model")
        return 1
    
    # Load course data
    print("\n📚 Loading course data...")
    try:
        course_data = load_course_data()
        total_items = sum(len(items) for items in course_data.values())
        print(f"✅ Loaded {len(course_data)} lessons with {total_items} total items")
    except Exception as e:
        print(f"❌ Error loading course data: {e}")
        return 1
    
    # Verify deck and model exist
    print("\n🔍 Verifying Anki environment...")
    try:
        deck_names = invoke_anki_connect("deckNames")
        if DECK_NAME not in deck_names:
            print(f"❌ Deck '{DECK_NAME}' does not exist")
            print(f"   Please run scripts/setup_anki_env.py first")
            return 1
        
        model_names = invoke_anki_connect("modelNames")
        if MODEL_NAME not in model_names:
            print(f"❌ Note type '{MODEL_NAME}' does not exist")
            print(f"   Please run scripts/setup_anki_env.py first")
            return 1
        
        print(f"✅ Deck and note type verified")
    except Exception as e:
        print(f"❌ Error verifying Anki environment: {e}")
        return 1
    
    # Sync to Anki
    print("\n📤 Syncing notes to Anki...")
    try:
        results = sync_course_to_anki(course_data)
        
        print("\n" + "=" * 80)
        print("Sync Summary")
        print("=" * 80)
        print(f"✅ Notes added: {results['notes_added']}")
        if results['notes_failed'] > 0:
            print(f"❌ Notes failed: {results['notes_failed']}")
        print("=" * 80)
        
        if results['errors']:
            print("\nErrors encountered:")
            for error in results['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(results['errors']) > 10:
                print(f"  ... and {len(results['errors']) - 10} more errors")
        
        if results['notes_failed'] == 0:
            print("\n🎉 Success! All notes synced to Anki.")
            return 0
        else:
            print("\n⚠️  Some notes failed to sync. Check errors above.")
            return 1
        
    except Exception as e:
        print(f"\n❌ Error syncing to Anki: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

