#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time script to extract Pinyin learning data from apkg file and store in database.

This script extracts two types of notes:
1. "CUMA - Pinyin Element" - teaching cards for initial/final elements
2. "CUMA - Pinyin Syllable" - whole pinyin syllable with 5 cards

This script:
1. Extracts notes from the apkg file (语言语文__拼音.apkg)
2. Extracts media files (images and audio) and fixes references
3. Stores everything in the database
4. Maintains the original order of notes
"""

import sys
import os
import sqlite3
import zipfile
import tempfile
import json
import shutil
import re
from pathlib import Path
from html import unescape

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.models import PinyinElementNote, PinyinSyllableNote, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = project_root
# Use the new reorganized deck
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
MEDIA_DIR = PROJECT_ROOT / "media" / "pinyin"
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"


def fix_image_references(html_content: str, media_map: dict) -> str:
    """Replace Anki media references with local media directory paths"""
    if not html_content:
        return html_content
    
    # Pattern to match <img src="..."> or <img src='...'>
    pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
    
    def replace_img(match):
        img_tag = match.group(0)
        src_value = match.group(1)
        
        # Skip URLs
        if src_value.startswith('http'):
            return img_tag
        
        # Get filename from Anki media reference (remove any path)
        filename = Path(src_value.strip()).name
        
        # Look up in media_map (media_map uses original filenames as keys)
        if filename in media_map:
            # Get just the filename from the local path
            local_path = Path(media_map[filename])
            # Return just the filename (relative to media/pinyin directory)
            new_src = local_path.name
            return img_tag.replace(src_value, new_src)
        
        # If not found, return original (might be a different reference)
        return img_tag
    
    return re.sub(pattern, replace_img, html_content)


def extract_media_files(apkg_path: Path, media_dir: Path) -> dict:
    """Extract media files from apkg and return mapping of original filename -> local path"""
    media_map = {}
    
    if not apkg_path.exists():
        print(f"⚠️  APKG file not found: {apkg_path}")
        return media_map
    
    # Create media directory
    media_dir.mkdir(parents=True, exist_ok=True)
    
    # Remove any blocking file or nested media directory that might exist
    nested_media = media_dir / 'media'
    if nested_media.exists():
        if nested_media.is_file():
            nested_media.unlink()
        elif nested_media.is_dir():
            import shutil
            shutil.rmtree(nested_media)
    
    with zipfile.ZipFile(apkg_path, 'r') as z:
        # First, read the media mapping file to get original filenames
        anki_media_map = {}
        if 'media' in z.namelist():
            try:
                media_data = z.read('media').decode('utf-8')
                anki_media_map = json.loads(media_data)
                print(f"📋 Loaded media mapping: {len(anki_media_map)} entries")
            except Exception as e:
                print(f"⚠️  Failed to parse media mapping: {e}")
        
        # Get list of files in the zip
        file_list = z.namelist()
        
        # Filter for media files (images and audio) - exclude collection, meta, and media mapping file
        # Files in apkg are like "media/filename" or just numeric names
        media_files = [f for f in file_list if not f.startswith('collection.') and f not in ['media', 'meta']]
        
        print(f"📦 Found {len(media_files)} media files in apkg")
        
        for file_path in media_files:
            try:
                # Handle "media/filename" format - strip "media/" prefix to get actual filename
                if file_path.startswith('media/'):
                    actual_filename = file_path[6:]  # Remove "media/" prefix
                else:
                    actual_filename = file_path
                
                # Get original filename from mapping (try both with and without "media/" prefix)
                original_filename = anki_media_map.get(file_path, anki_media_map.get(actual_filename, actual_filename))
                
                # Extract file - zipfile will create nested "media/" directory if path has it
                # We need to extract to a temp location and then move to final location
                if file_path.startswith('media/'):
                    # Extract to temp location, then move file up one level
                    z.extract(file_path, media_dir)
                    extracted_path = media_dir / file_path
                    # Move from media_dir/media/filename to media_dir/filename
                    target_path = media_dir / original_filename
                    if extracted_path.exists():
                        if target_path.exists():
                            extracted_path.unlink()
                        else:
                            shutil.move(str(extracted_path), str(target_path))
                    # Clean up nested media directory if empty
                    nested_media_dir = media_dir / 'media'
                    if nested_media_dir.exists() and nested_media_dir.is_dir():
                        try:
                            if not any(nested_media_dir.iterdir()):
                                nested_media_dir.rmdir()
                        except:
                            pass
                else:
                    # Extract directly
                    z.extract(file_path, media_dir)
                    extracted_path = media_dir / actual_filename
                    target_path = media_dir / original_filename
                    if extracted_path != target_path:
                        if target_path.exists():
                            extracted_path.unlink()
                        else:
                            shutil.move(str(extracted_path), str(target_path))
                
                # Store mapping (original filename -> local path)
                media_map[original_filename] = str(target_path)
                if file_path != original_filename:
                    print(f"  ✅ Extracted: {file_path} -> {original_filename}")
                else:
                    print(f"  ✅ Extracted: {original_filename}")
                
            except Exception as e:
                print(f"  ⚠️  Failed to extract {file_path}: {e}")
    
    return media_map


def extract_notes_from_apkg(apkg_path: Path, media_map: dict) -> tuple:
    """Extract notes from apkg file, returns (element_notes, syllable_notes)
    Preserves the deck order by using note ID as display_order"""
    element_notes = []
    syllable_notes = []
    
    with zipfile.ZipFile(apkg_path, 'r') as z:
        # Extract database to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.anki21') as tmp_db:
            tmp_db.write(z.read('collection.anki21'))
            tmp_db_path = tmp_db.name
        
        try:
            # Connect to database
            conn = sqlite3.connect(tmp_db_path)
            cursor = conn.cursor()
            
            # Get note models
            cursor.execute("SELECT models FROM col")
            col_data = cursor.fetchone()
            models = json.loads(col_data[0]) if col_data else {}
            
            # Get all notes ordered by ID (to maintain deck order)
            cursor.execute("SELECT id, mid, flds FROM notes ORDER BY id")
            all_notes = cursor.fetchall()
            
            # Use a global counter to preserve deck order across both types
            global_order = 0
            
            for note_id, mid, flds in all_notes:
                fields = flds.split('\x1f')
                
                # Get model to understand field structure
                model = models.get(str(mid), {})
                model_name = model.get('name', '')
                field_names = [f.get('name', f'Field{i}') for i, f in enumerate(model.get('flds', []))]
                
                # Build fields dictionary
                note_fields = {}
                for i, field_value in enumerate(fields):
                    field_name = field_names[i] if i < len(field_names) else f'Field{i}'
                    # Fix image references in field values
                    if field_value and isinstance(field_value, str):
                        note_fields[field_name] = fix_image_references(field_value, media_map)
                    else:
                        note_fields[field_name] = field_value or ""
                
                # Determine note type and extract data
                if model_name == "CUMA - Pinyin Element":
                    # Extract element (initial or final)
                    element = note_fields.get('Element', '').strip()
                    if not element:
                        continue
                    
                    # Determine element type (initial or final)
                    # This is a heuristic - you may need to adjust based on actual data
                    element_type = "initial" if len(element) <= 2 else "final"
                    
                    element_notes.append({
                        'note_id': str(note_id),
                        'element': element,
                        'element_type': element_type,
                        'fields': note_fields,
                        'display_order': global_order  # Use global order to preserve deck order
                    })
                    global_order += 1
                
                elif model_name == "CUMA - Pinyin Syllable":
                    # Extract syllable
                    syllable = note_fields.get('Syllable', '').strip()
                    if not syllable:
                        # Try alternative field names
                        syllable = note_fields.get('Pinyin', '').strip()
                    if not syllable:
                        continue
                    
                    # Extract word (Chinese characters) and concept
                    word = note_fields.get('WordHanzi', '').strip()
                    if not word:
                        word = note_fields.get('Word', '').strip()
                    
                    # Extract concept (try to get from WordPicture or use syllable as fallback)
                    concept = note_fields.get('WordPicture', '').strip()
                    if not concept or concept.startswith('<img'):
                        # Use syllable as concept if no picture description
                        concept = syllable
                    
                    syllable_notes.append({
                        'note_id': str(note_id),
                        'syllable': syllable,
                        'word': word or syllable,  # Fallback to syllable if no word
                        'concept': concept or syllable,  # Fallback to syllable if no concept
                        'fields': note_fields,
                        'display_order': global_order  # Use global order to preserve deck order
                    })
                    global_order += 1
            
            conn.close()
        finally:
            os.unlink(tmp_db_path)
    
    print(f"📚 Extracted {len(element_notes)} element notes and {len(syllable_notes)} syllable notes from apkg")
    return element_notes, syllable_notes


def main():
    """Main extraction function"""
    print("=" * 80)
    print("Extract Pinyin Learning Data from APKG")
    print("=" * 80)
    
    if not APKG_PATH.exists():
        print(f"❌ Error: APKG file not found at {APKG_PATH}")
        return
    
    # Extract media files
    print("\n1. Extracting media files...")
    media_map = extract_media_files(APKG_PATH, MEDIA_DIR)
    print(f"   ✅ Extracted {len(media_map)} media files")
    
    # Extract notes
    print("\n2. Extracting notes...")
    element_notes, syllable_notes = extract_notes_from_apkg(APKG_PATH, media_map)
    
    # Connect to database
    print("\n3. Storing in database...")
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Clear existing data (optional - comment out if you want to keep existing data)
        session.query(PinyinElementNote).delete()
        session.query(PinyinSyllableNote).delete()
        session.commit()
        print("   ✅ Cleared existing pinyin notes")
        
        # Insert element notes
        for note_data in element_notes:
            db_note = PinyinElementNote(
                note_id=note_data['note_id'],
                element=note_data['element'],
                element_type=note_data['element_type'],
                display_order=note_data['display_order'],
                fields=json.dumps(note_data['fields'], ensure_ascii=False)
            )
            session.add(db_note)
        
        # Insert syllable notes
        for note_data in syllable_notes:
            db_note = PinyinSyllableNote(
                note_id=note_data['note_id'],
                syllable=note_data['syllable'],
                word=note_data['word'],
                concept=note_data['concept'],
                display_order=note_data['display_order'],
                fields=json.dumps(note_data['fields'], ensure_ascii=False)
            )
            session.add(db_note)
        
        session.commit()
        print(f"   ✅ Stored {len(element_notes)} element notes")
        print(f"   ✅ Stored {len(syllable_notes)} syllable notes")
        
    except Exception as e:
        session.rollback()
        print(f"   ❌ Error storing notes: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()
    
    print("\n✅ Extraction complete!")


if __name__ == "__main__":
    main()

