#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time script to extract character recognition data from apkg file and store in database.

This script:
1. Extracts notes from the apkg file
2. Extracts media files and fixes image references
3. Stores everything in the database
4. Maintains the original order of characters
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

from backend.database.db import get_db_session, init_db
from backend.database.models import CharacterRecognitionNote, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "content_db" / "语言语文__识字__全部.apkg"
MEDIA_DIR = PROJECT_ROOT / "media" / "character_recognition"
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"


def fix_image_references(html_content: str, media_map: dict) -> str:
    """Replace Anki media references with local media directory paths"""
    if not html_content:
        return html_content
    
    # Pattern to match <img src="filename">, <img src='filename'>, or <img src=filename>
    # This handles both quoted and unquoted src attributes
    img_pattern = r'<img[^>]*src=(["\']?)([^"\'>\s]+)\1[^>]*>'
    
    def replace_img(match):
        img_tag = match.group(0)
        quote_char = match.group(1)  # " or ' or empty
        filename = match.group(2)
        
        # If it's already a full URL or absolute path, keep it
        if filename.startswith('http') or filename.startswith('/'):
            return img_tag
        
        # Determine the correct quote character to use (default to double quote)
        new_quote = quote_char if quote_char else '"'
        
        # Preserve original case - check media_map with case-insensitive lookup but use original key
        # First try exact match
        if filename in media_map:
            new_path = media_map[filename]
            # Replace src with proper quoting
            if quote_char:
                return img_tag.replace(f'src={quote_char}{filename}{quote_char}', f'src={new_quote}{new_path}{new_quote}')
            else:
                return img_tag.replace(f'src={filename}', f'src={new_quote}{new_path}{new_quote}')
        
        # Try case-insensitive lookup in media_map
        filename_lower = filename.lower()
        for key, path in media_map.items():
            if key.lower() == filename_lower:
                new_path = path
                # Use the original key (preserving case) in the path
                if quote_char:
                    return img_tag.replace(f'src={quote_char}{filename}{quote_char}', f'src={new_quote}{new_path}{new_quote}')
                else:
                    return img_tag.replace(f'src={filename}', f'src={new_quote}{new_path}{new_quote}')
        
        # Check if file exists in character_recognition media directory (case-insensitive)
        # But preserve the original filename case
        for existing_file in MEDIA_DIR.iterdir():
            if existing_file.is_file() and existing_file.name.lower() == filename.lower():
                new_path = f"/media/character_recognition/{existing_file.name}"  # Use actual filename with correct case
                if quote_char:
                    return img_tag.replace(f'src={quote_char}{filename}{quote_char}', f'src={new_quote}{new_path}{new_quote}')
                else:
                    return img_tag.replace(f'src={filename}', f'src={new_quote}{new_path}{new_quote}')
        
        return img_tag
    
    # Strategy: First fix existing img tags, then handle plain filenames ONLY in text parts
    # Split by img tags to avoid processing filenames that are already in img src attributes
    img_tag_pattern = r'(<img[^>]*>)'
    parts = re.split(img_tag_pattern, html_content)
    
    def process_text_part(text):
        """Process text that's not inside img tags - convert plain filenames to img tags"""
        if not text:
            return text
        
        # Pattern to match image filenames (but not if they're part of an existing img tag)
        filename_pattern = r'\b([a-zA-Z0-9_-]+\.(?:png|jpg|jpeg|gif|webp))\b'
        
        def replace_filename(match):
            filename = match.group(1)
            # Preserve case - check media_map with case-insensitive lookup
            if filename in media_map:
                return f'<img src="{media_map[filename]}" alt="{filename}">'
            
            # Try case-insensitive lookup in media_map
            filename_lower = filename.lower()
            for key, path in media_map.items():
                if key.lower() == filename_lower:
                    return f'<img src="{path}" alt="{key}">'  # Use original key for alt
            
            # Check if file exists in character_recognition media directory (case-insensitive)
            for existing_file in MEDIA_DIR.iterdir():
                if existing_file.is_file() and existing_file.name.lower() == filename.lower():
                    return f'<img src="/media/character_recognition/{existing_file.name}" alt="{existing_file.name}">'
            
            return filename
        
        return re.sub(filename_pattern, replace_filename, text)
    
    # Process each part: img tags get their src fixed, text parts get plain filenames converted
    processed_parts = []
    for part in parts:
        if part.startswith('<img'):
            # This is an img tag - fix its src attribute using replace_img
            match = re.search(img_pattern, part)
            if match:
                processed_parts.append(replace_img(match))
            else:
                processed_parts.append(part)
        else:
            # This is text - convert plain filenames to img tags
            processed_parts.append(process_text_part(part))
    
    html_content = ''.join(processed_parts)
    
    return html_content


def extract_media_files(apkg_path: Path, media_dir: Path) -> dict:
    """Extract media files from apkg and return mapping of filename to URL path"""
    media_map = {}
    media_dir.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg (it's a zip file)
        with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir_path)
        
        # Handle media extraction
        media_source = tmpdir_path / "media"
        if media_source.exists() and media_source.is_dir():
            # Case 1: media is a directory
            try:
                for media_file in media_source.iterdir():
                    if media_file.is_file():
                        dest_file = media_dir / media_file.name
                        if not dest_file.exists():
                            shutil.copy2(media_file, dest_file)
                        media_map[media_file.name] = f"/media/character_recognition/{media_file.name}"
            except Exception as e:
                print(f"⚠️  Warning: Could not extract media files from directory: {e}")
        elif media_source.exists() and media_source.is_file():
            # Case 2: media is a JSON file - read it to get the mapping
            try:
                media_json = json.loads(media_source.read_text(encoding='utf-8'))
                # media_json maps hash names (numeric strings) to display names (e.g., "746": "out.png")
                # We need to reverse this to map display names to hash names
                # Then extract files using hash names from the zip
                hash_to_display = media_json  # This is actually hash -> display
                display_to_hash = {v: k for k, v in hash_to_display.items()}  # Reverse: display -> hash
                
                with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
                    zip_names = set(zip_ref.namelist())
                    extracted_count = 0
                    for display_name, hash_name in display_to_hash.items():
                        # hash_name is a string like "746", "1232", etc. - these are the actual filenames in the zip
                        hash_str = str(hash_name)
                        if hash_str in zip_names:
                            dest_file = media_dir / display_name
                            if not dest_file.exists():
                                try:
                                    with zip_ref.open(hash_str) as source_file:
                                        with open(dest_file, 'wb') as dest:
                                            shutil.copyfileobj(source_file, dest)
                                    extracted_count += 1
                                    if extracted_count <= 5 or extracted_count % 100 == 0:
                                        print(f"  ✅ Extracted {display_name} ({extracted_count}/{len(display_to_hash)})")
                                except Exception as e:
                                    print(f"  ⚠️  Error extracting {display_name} (hash: {hash_str}): {e}")
                            media_map[display_name] = f"/media/character_recognition/{display_name}"
                    if extracted_count > 5:
                        print(f"  ✅ Extracted {extracted_count} media files total")
            except Exception as e:
                import traceback
                print(f"⚠️  Warning: Could not extract media files from JSON mapping: {e}")
                traceback.print_exc()
        else:
            # Case 3: Try to find media files directly in the zip
            try:
                with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
                    media_files = [f for f in zip_ref.namelist() 
                                 if f not in ['media', 'collection.anki21', 'collection.anki2'] 
                                 and not f.endswith('/')
                                 and any(f.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'])]
                    for media_path in media_files:
                        filename = Path(media_path).name
                        if filename:
                            dest_file = media_dir / filename
                            if not dest_file.exists():
                                with zip_ref.open(media_path) as source_file:
                                    with open(dest_file, 'wb') as dest:
                                        shutil.copyfileobj(source_file, dest)
                            media_map[filename] = f"/media/character_recognition/{filename}"
            except Exception as e:
                print(f"⚠️  Warning: Could not extract media files from zip: {e}")
    
    print(f"📁 Extracted {len(media_map)} media files to {media_dir}")
    return media_map


def extract_notes_from_apkg(apkg_path: Path, media_map: dict) -> list:
    """Extract character recognition notes from apkg file"""
    notes = []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg (it's a zip file)
        with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir_path)
        
        # Open the SQLite database
        db_path = tmpdir_path / "collection.anki21"
        if not db_path.exists():
            db_path = tmpdir_path / "collection.anki2"
        
        if not db_path.exists():
            raise FileNotFoundError("No database found in apkg file")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get models to understand field structure
        cursor.execute("SELECT models FROM col LIMIT 1")
        row = cursor.fetchone()
        if not row or not row[0]:
            conn.close()
            raise ValueError("No models found in database")
        
        models_json = json.loads(row[0])
        model_fields = {}
        
        for model_id_str, model_data in models_json.items():
            fields = [fld.get('name', '') for fld in model_data.get('flds', [])]
            model_fields[int(model_id_str)] = fields
        
        # Get all notes, ordered by note ID to maintain order
        cursor.execute("SELECT id, mid, flds FROM notes ORDER BY id")
        all_notes = cursor.fetchall()
        
        for idx, (note_id, mid, flds_str) in enumerate(all_notes):
            fields_list = flds_str.split('\x1f')  # Anki uses \x1f as field separator
            field_names = model_fields.get(mid, [])
            
            # Build field dictionary
            note_fields = {}
            for i, field_name in enumerate(field_names):
                if i < len(fields_list):
                    # Unescape HTML entities
                    field_value = unescape(fields_list[i])
                    # Fix image references in all fields
                    if field_value:
                        field_value = fix_image_references(field_value, media_map)
                    note_fields[field_name] = field_value
            
            # Check if this note has a Character field
            if 'Character' not in note_fields:
                continue
            
            character = note_fields['Character'].strip()
            if not character:
                continue
            
            # Store note with display order (use index to maintain original order)
            note_data = {
                'note_id': str(note_id),
                'character': character,
                'display_order': idx,
                'fields': json.dumps(note_fields, ensure_ascii=False)
            }
            notes.append(note_data)
        
        conn.close()
    
    return notes


def main():
    """Main extraction function"""
    print("=" * 80)
    print("Character Recognition Data Extraction")
    print("=" * 80)
    print()
    
    if not APKG_PATH.exists():
        print(f"❌ Error: APKG file not found: {APKG_PATH}")
        return 1
    
    # Initialize database
    print("📊 Initializing database...")
    init_db()
    
    # Extract media files first
    print("\n📁 Step 1: Extracting media files...")
    media_map = extract_media_files(APKG_PATH, MEDIA_DIR)
    
    # Extract notes from apkg
    print("\n📚 Step 2: Extracting notes from apkg...")
    notes = extract_notes_from_apkg(APKG_PATH, media_map)
    print(f"✅ Extracted {len(notes)} character recognition notes")
    
    # Store in database
    print("\n💾 Step 3: Storing notes in database...")
    with get_db_session() as db:
        # Clear existing notes (if re-running)
        db.query(CharacterRecognitionNote).delete()
        db.commit()
        
        # Insert new notes
        for note_data in notes:
            note = CharacterRecognitionNote(
                note_id=note_data['note_id'],
                character=note_data['character'],
                display_order=note_data['display_order'],
                fields=note_data['fields']
            )
            db.add(note)
        
        db.commit()
        print(f"✅ Stored {len(notes)} notes in database")
    
    print("\n" + "=" * 80)
    print("✅ Extraction Complete!")
    print("=" * 80)
    print(f"   Notes stored: {len(notes)}")
    print(f"   Media files: {len(media_map)}")
    print(f"   Media directory: {MEDIA_DIR}")
    print()
    print("   The system will now read from the database instead of the apkg file.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

