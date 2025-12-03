#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time script to extract Chinese word recognition data from apkg file and store in database.

VERBAL TRAINING FOCUS:
- No reading/writing required
- Focus: Listening comprehension and verbal production
- Audio files are critical (users listen and respond verbally)
- Pictures for visual concept representation
- Pinyin is optional, only for non-verbal users to reply

This script:
1. Extracts notes from the apkg file (认知__普通话基础词汇.apkg)
2. Extracts media files (images and audio) and fixes references
3. Stores everything in the database
4. Maintains the original order of words
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

from backend.database.models import ChineseWordRecognitionNote, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "content_db" / "认知__普通话基础词汇.apkg"
MEDIA_DIR = PROJECT_ROOT / "media" / "chinese_word_recognition"
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"


def fix_image_references(html_content: str, media_map: dict) -> str:
    """Replace Anki media references with local media directory paths"""
    if not html_content:
        return html_content
    
    # Pattern to match <img src="filename">, <img src='filename'>, or <img src=filename>
    img_pattern = r'<img[^>]*src=(["\']?)([^"\'>\s]+)\1[^>]*>'
    
    def replace_img(match):
        img_tag = match.group(0)
        quote_char = match.group(1)
        filename = match.group(2)
        
        if filename.startswith('http') or filename.startswith('/'):
            return img_tag
        
        new_quote = quote_char if quote_char else '"'
        
        # Try exact match first
        if filename in media_map:
            new_path = media_map[filename]
            if quote_char:
                return img_tag.replace(f'src={quote_char}{filename}{quote_char}', f'src={new_quote}{new_path}{new_quote}')
            else:
                return img_tag.replace(f'src={filename}', f'src={new_quote}{new_path}{new_quote}')
        
        # Try case-insensitive lookup
        filename_lower = filename.lower()
        for key, path in media_map.items():
            if key.lower() == filename_lower:
                new_path = path
                if quote_char:
                    return img_tag.replace(f'src={quote_char}{filename}{quote_char}', f'src={new_quote}{new_path}{new_quote}')
                else:
                    return img_tag.replace(f'src={filename}', f'src={new_quote}{new_path}{new_quote}')
        
        # Check if file exists in media directory
        for existing_file in MEDIA_DIR.iterdir():
            if existing_file.is_file() and existing_file.name.lower() == filename.lower():
                new_path = f"/media/chinese_word_recognition/{existing_file.name}"
                if quote_char:
                    return img_tag.replace(f'src={quote_char}{filename}{quote_char}', f'src={new_quote}{new_path}{new_quote}')
                else:
                    return img_tag.replace(f'src={filename}', f'src={new_quote}{new_path}{new_quote}')
        
        return img_tag
    
    # Split by img tags to avoid double-processing
    img_tag_pattern = r'(<img[^>]*>)'
    parts = re.split(img_tag_pattern, html_content)
    
    def process_text_part(text):
        """Process text that's not inside img tags - convert plain filenames to img tags"""
        if not text:
            return text
        
        filename_pattern = r'\b([a-zA-Z0-9_-]+\.(?:png|jpg|jpeg|gif|webp))\b'
        
        def replace_filename(match):
            filename = match.group(1)
            if filename in media_map:
                return f'<img src="{media_map[filename]}" alt="{filename}">'
            
            filename_lower = filename.lower()
            for key, path in media_map.items():
                if key.lower() == filename_lower:
                    return f'<img src="{path}" alt="{key}">'
            
            for existing_file in MEDIA_DIR.iterdir():
                if existing_file.is_file() and existing_file.name.lower() == filename.lower():
                    return f'<img src="/media/chinese_word_recognition/{existing_file.name}" alt="{existing_file.name}">'
            
            return filename
        
        return re.sub(filename_pattern, replace_filename, text)
    
    processed_parts = []
    for part in parts:
        if part.startswith('<img'):
            match = re.search(img_pattern, part)
            if match:
                processed_parts.append(replace_img(match))
            else:
                processed_parts.append(part)
        else:
            processed_parts.append(process_text_part(part))
    
    return ''.join(processed_parts)


def extract_media_files(apkg_path: Path, media_dir: Path) -> dict:
    """
    Extract media files (images and audio) from apkg and return mapping of filename to URL path.
    Audio files are important for verbal training - users listen and respond verbally.
    """
    media_map = {}
    media_dir.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(apkg_path, 'r') as z:
        # Check if media is a directory or JSON file
        if 'media' in z.namelist():
            media_info = z.getinfo('media')
            
            if media_info.is_dir():
                # Media is a directory - extract all files
                for file_info in z.infolist():
                    if file_info.filename.startswith('media/') and not file_info.is_dir():
                        filename = os.path.basename(file_info.filename)
                        z.extract(file_info, media_dir)
                        # Move to media_dir root
                        extracted_path = media_dir / file_info.filename.replace('media/', '')
                        if extracted_path.exists():
                            target_path = media_dir / filename
                            if target_path != extracted_path:
                                shutil.move(str(extracted_path), str(target_path))
                            media_map[filename] = f"/media/chinese_word_recognition/{filename}"
            else:
                # Media is a JSON file mapping: numeric_id -> original_filename
                try:
                    media_content = z.read('media').decode('utf-8')
                    media_json = json.loads(media_content)
                    
                    # The mapping is: numeric_id (as string) -> original_filename
                    # Files in zip are stored as numeric names (0, 1, 2, etc.)
                    # Extract numeric-named files and rename to original filenames
                    for numeric_id_str, original_filename in media_json.items():
                        # Try to find the numeric-named file in the zip
                        numeric_name = numeric_id_str  # e.g., "65", "459"
                        
                        # Check if this numeric file exists in zip
                        if numeric_name in z.namelist():
                            file_info = z.getinfo(numeric_name)
                            if not file_info.is_dir():
                                # Extract with numeric name
                                z.extract(file_info, media_dir)
                                extracted_path = media_dir / numeric_name
                                
                                # Rename to original filename
                                target_path = media_dir / original_filename
                                if extracted_path.exists():
                                    if target_path != extracted_path:
                                        shutil.move(str(extracted_path), str(target_path))
                                    media_map[original_filename] = f"/media/chinese_word_recognition/{original_filename}"
                    
                    print(f"  ✅ Extracted {len(media_map)} media files using JSON mapping")
                except (json.JSONDecodeError, KeyError, Exception) as e:
                    print(f"  ⚠️  Error extracting media with JSON mapping: {e}")
                    # Fallback: search zip directly for image and audio files
                    for file_info in z.infolist():
                        if file_info.filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp3', '.ogg', '.wav', '.m4a')):
                            filename = os.path.basename(file_info.filename)
                            if filename not in media_map:
                                z.extract(file_info, media_dir)
                                extracted_path = media_dir / filename
                                if extracted_path.exists():
                                    media_map[filename] = f"/media/chinese_word_recognition/{filename}"
    
    print(f"📁 Extracted {len(media_map)} media files to {media_dir}")
    return media_map


def extract_notes_from_apkg(apkg_path: Path, media_map: dict) -> list:
    """Extract notes from apkg file"""
    notes = []
    
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
            
            # Get all notes ordered by ID (to maintain order)
            cursor.execute("SELECT id, mid, flds FROM notes ORDER BY id")
            all_notes = cursor.fetchall()
            
            for note_id, mid, flds in all_notes:
                fields = flds.split('\x1f')
                
                # Get model to understand field structure
                model = models.get(str(mid), {})
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
                
                # Extract word and concept
                # Based on the structure: English, Chinese, Pinyin, Audio, Image, ...
                word = note_fields.get('Chinese', '').strip()
                concept = note_fields.get('English', '').strip()
                
                if word and concept:
                    notes.append({
                        'note_id': str(note_id),
                        'word': word,
                        'concept': concept,
                        'fields': note_fields,
                        'display_order': len(notes)  # Maintain order
                    })
            
            conn.close()
        finally:
            os.unlink(tmp_db_path)
    
    print(f"📚 Extracted {len(notes)} notes from apkg")
    return notes


def main():
    """Main extraction function"""
    import sys
    
    print("🚀 Starting Chinese word recognition extraction...")
    print(f"   APKG: {APKG_PATH}")
    print(f"   Media dir: {MEDIA_DIR}")
    print(f"   Database: {DB_PATH}")
    
    if not APKG_PATH.exists():
        print(f"❌ Error: APKG file not found: {APKG_PATH}")
        return
    
    # Initialize database
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if notes already exist
        existing_count = session.query(ChineseWordRecognitionNote).count()
        if existing_count > 0:
            # Check for --force flag to skip prompt
            force = '--force' in sys.argv or '-f' in sys.argv
            if force:
                response = 'y'
            else:
                try:
                    response = input(f"⚠️  Found {existing_count} existing notes. Delete and re-extract? (y/N): ")
                except EOFError:
                    # Non-interactive mode - default to yes
                    response = 'y'
                    print(f"⚠️  Found {existing_count} existing notes. Auto-deleting (non-interactive mode)...")
            
            if response.lower() == 'y':
                session.query(ChineseWordRecognitionNote).delete()
                session.commit()
                print("🗑️  Deleted existing notes")
            else:
                print("❌ Aborted")
                return
        
        # Extract media files
        print("\n📁 Extracting media files...")
        media_map = extract_media_files(APKG_PATH, MEDIA_DIR)
        
        # Extract notes
        print("\n📚 Extracting notes...")
        notes = extract_notes_from_apkg(APKG_PATH, media_map)
        
        # Store in database
        print("\n💾 Storing notes in database...")
        for note_data in notes:
            db_note = ChineseWordRecognitionNote(
                note_id=note_data['note_id'],
                word=note_data['word'],
                concept=note_data['concept'],
                display_order=note_data['display_order'],
                fields=json.dumps(note_data['fields'], ensure_ascii=False)
            )
            session.add(db_note)
        
        session.commit()
        print(f"✅ Successfully stored {len(notes)} notes in database")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()

