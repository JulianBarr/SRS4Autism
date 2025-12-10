#!/usr/bin/env python3
"""
Batch extract and rename images from English Vocabulary .apkg files.

Extracts images from:
- English__Vocabulary__1. Basic.apkg
- English__Vocabulary__2. Level 2.apkg

Renaming rules:
- Single file: word.ext
- Multiple files: word_1.ext, word_2.ext, etc.
- Phrases: phrase_word.ext (join with _)
"""

import zipfile
import json
import sqlite3
import shutil
from pathlib import Path
from collections import defaultdict
import re
from html import unescape

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APKG_BASIC = PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__1. Basic.apkg"
APKG_LEVEL = PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"
OUTPUT_DIR = PROJECT_ROOT / "media" / "pinyin"  # Store in pinyin directory as requested


def clean_word(word: str) -> str:
    """Clean word for filename: lowercase, replace spaces with _, remove special chars."""
    # Remove HTML tags
    word = re.sub(r'<[^>]+>', '', word)
    # Unescape HTML entities
    word = unescape(word)
    # Convert to lowercase
    word = word.lower().strip()
    # Replace spaces and multiple spaces with single underscore
    word = re.sub(r'\s+', '_', word)
    # Remove special characters except underscore and hyphen
    word = re.sub(r'[^a-z0-9_-]', '', word)
    # Remove leading/trailing underscores
    word = word.strip('_')
    return word


def extract_media_mapping(apkg_path: Path) -> dict:
    """Extract media mapping from .apkg file (numeric_id -> original_filename)."""
    media_map = {}
    
    if not apkg_path.exists():
        print(f"⚠️  APKG file not found: {apkg_path}")
        return media_map
    
    with zipfile.ZipFile(apkg_path, 'r') as z:
        if 'media' in z.namelist():
            try:
                media_content = z.read('media').decode('utf-8')
                media_json = json.loads(media_content)
                # Mapping: numeric_id (string) -> original_filename
                media_map = {int(k): v for k, v in media_json.items() if k.isdigit()}
                print(f"  📋 Loaded {len(media_map)} media mappings")
            except (json.JSONDecodeError, Exception) as e:
                print(f"  ⚠️  Error reading media mapping: {e}")
    
    return media_map


def extract_notes_with_images(apkg_path: Path) -> list:
    """Extract notes with their associated images from .apkg file."""
    notes = []
    
    if not apkg_path.exists():
        return notes
    
    # Extract media mapping
    media_map = extract_media_mapping(apkg_path)
    
    # Extract database to temp location
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        with zipfile.ZipFile(apkg_path, 'r') as z:
            # Find database file
            db_files = ['collection.anki21', 'collection.anki2']
            db_path = None
            
            for db_file in db_files:
                if db_file in z.namelist():
                    z.extract(db_file, tmpdir_path)
                    db_path = tmpdir_path / db_file
                    break
            
            if not db_path or not db_path.exists():
                print(f"  ⚠️  No database found in {apkg_path.name}")
                return notes
            
            # Read database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Get model field names
            cursor.execute("SELECT models FROM col LIMIT 1")
            row = cursor.fetchone()
            if not row or not row[0]:
                conn.close()
                return notes
            
            models_json = json.loads(row[0])
            model_fields = {}
            
            for model_id_str, model_data in models_json.items():
                fields = [fld.get('name', '') for fld in model_data.get('flds', [])]
                model_fields[int(model_id_str)] = fields
            
            # Get notes with their fields
            cursor.execute("SELECT mid, flds FROM notes")
            rows = cursor.fetchall()
            
            for mid, flds_str in rows:
                fields = flds_str.split('\x1f')  # Anki field separator
                field_names = model_fields.get(mid, [])
                
                # Find English word from BACK field (prioritize "back" field name, then second field)
                english_word = None
                
                # First pass: Look specifically for "back" field
                for i, field_name in enumerate(field_names):
                    if field_name.lower() == 'back' and i < len(fields):
                        field_value = fields[i].strip()
                        # Remove HTML tags
                        field_value = re.sub(r'<[^>]+>', '', field_value)
                        field_value = unescape(field_value).strip()
                        
                        # Skip empty values and sound references
                        if not field_value or field_value.startswith('[sound:') or field_value.startswith('[anki:'):
                            continue
                        
                        if field_value and len(field_value) < 100:
                            # Extract English part if mixed with Chinese (text before Chinese characters)
                            english_part = re.split(r'[\u4e00-\u9fff]', field_value)[0].strip()
                            if english_part:
                                english_word = english_part
                                break
                            # If no Chinese found, use as-is if it has English letters
                            elif re.search(r'[a-zA-Z]', field_value):
                                english_word = field_value
                                break
                
                # Second pass: If no "back" field found, use second field (typically back is second)
                if not english_word:
                    if len(fields) > 1:
                        field_value = fields[1].strip()
                        field_value = re.sub(r'<[^>]+>', '', field_value)
                        field_value = unescape(field_value).strip()
                        
                        if field_value and not field_value.startswith('[sound:') and not field_value.startswith('[anki:') and len(field_value) < 100:
                            english_part = re.split(r'[\u4e00-\u9fff]', field_value)[0].strip()
                            if english_part:
                                english_word = english_part
                            elif re.search(r'[a-zA-Z]', field_value):
                                english_word = field_value
                    # Fallback to first field if no second field
                    elif len(fields) > 0:
                        field_value = fields[0].strip()
                        field_value = re.sub(r'<[^>]+>', '', field_value)
                        field_value = unescape(field_value).strip()
                        
                        if field_value and not field_value.startswith('[sound:') and not field_value.startswith('[anki:') and len(field_value) < 100:
                            english_part = re.split(r'[\u4e00-\u9fff]', field_value)[0].strip()
                            if english_part:
                                english_word = english_part
                            elif re.search(r'[a-zA-Z]', field_value):
                                english_word = field_value
                
                if not english_word:
                    continue
                
                # Find image references in fields (look for <img> tags)
                image_refs = []
                for field in fields:
                    # Extract image filenames from <img> tags
                    img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', field, re.IGNORECASE)
                    for img_src in img_matches:
                        # Remove path prefix if present
                        img_filename = Path(img_src).name
                        image_refs.append(img_filename)
                
                if image_refs:
                    notes.append({
                        'word': english_word,
                        'images': image_refs
                    })
            
            conn.close()
    
    return notes


def process_apkg_images(apkg_path: Path, output_dir: Path):
    """Extract and rename images from an .apkg file."""
    print(f"\n📦 Processing: {apkg_path.name}")
    
    if not apkg_path.exists():
        print(f"  ❌ File not found: {apkg_path}")
        return
    
    # Extract notes with images
    notes = extract_notes_with_images(apkg_path)
    print(f"  📚 Found {len(notes)} notes with images")
    
    if not notes:
        return
    
    # Extract media mapping
    media_map = extract_media_mapping(apkg_path)
    
    # Group images by word (handle multiple images per word)
    word_images = defaultdict(list)
    for note in notes:
        word = note['word']
        for img_ref in note['images']:
            word_images[word].append(img_ref)
    
    print(f"  🖼️  Found {len(word_images)} unique words with images")
    
    # Extract and rename images
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(apkg_path, 'r') as z:
        extracted_count = 0
        
        for word, image_refs in word_images.items():
            clean_word_name = clean_word(word)
            
            # Get unique image files (remove duplicates)
            unique_images = list(dict.fromkeys(image_refs))
            
            for idx, img_ref in enumerate(unique_images):
                # Find the actual file in zip
                # Image ref might be original filename or numeric ID
                source_file = None
                original_ext = None
                
                # Try to find by original filename first
                if img_ref in z.namelist():
                    source_file = img_ref
                else:
                    # Try to find by numeric ID (reverse lookup in media_map)
                    for numeric_id, orig_filename in media_map.items():
                        if orig_filename == img_ref:
                            numeric_name = str(numeric_id)
                            if numeric_name in z.namelist():
                                source_file = numeric_name
                                img_ref = orig_filename  # Use original filename for extension
                                break
                
                if not source_file:
                    # Try to find any file with similar name
                    for zip_name in z.namelist():
                        if Path(zip_name).stem == Path(img_ref).stem or zip_name.endswith(img_ref):
                            source_file = zip_name
                            break
                
                if not source_file:
                    print(f"  ⚠️  Could not find image file: {img_ref} for word: {word}")
                    continue
                
                # Get file extension
                original_ext = Path(img_ref).suffix or Path(source_file).suffix
                if not original_ext:
                    # Try to determine from file content or default to .jpg
                    original_ext = '.jpg'
                
                # Create base target filename
                if len(unique_images) == 1:
                    # Single image: word.ext
                    base_filename = f"{clean_word_name}{original_ext}"
                else:
                    # Multiple images: word_1.ext, word_2.ext, etc.
                    base_filename = f"{clean_word_name}_{idx + 1}{original_ext}"
                
                # Check if file exists and add postfix if needed
                target_path = output_dir / base_filename
                postfix_counter = 1
                
                # If file exists, add _1, _2, etc. postfix before extension
                while target_path.exists():
                    base_stem = Path(base_filename).stem
                    base_ext = Path(base_filename).suffix
                    new_filename = f"{base_stem}_{postfix_counter}{base_ext}"
                    target_path = output_dir / new_filename
                    postfix_counter += 1
                
                # Use the final target filename (with postfix if needed)
                target_filename = target_path.name
                
                # Extract and copy
                try:
                    z.extract(source_file, output_dir)
                    extracted_file = output_dir / source_file
                    
                    # Move/rename to target
                    if extracted_file != target_path:
                        if extracted_file.exists():
                            shutil.move(str(extracted_file), str(target_path))
                    
                    extracted_count += 1
                    print(f"  ✅ {target_filename} <- {word}")
                except Exception as e:
                    print(f"  ❌ Error extracting {img_ref}: {e}")
    
    print(f"  ✅ Extracted {extracted_count} images to {output_dir}")


def main():
    """Main function to process both .apkg files."""
    print("=" * 80)
    print("English Vocabulary Image Extraction")
    print("=" * 80)
    print(f"Output directory: {OUTPUT_DIR}")
    print()
    
    # Process Basic .apkg
    if APKG_BASIC.exists():
        process_apkg_images(APKG_BASIC, OUTPUT_DIR)
    else:
        print(f"⚠️  Basic .apkg not found: {APKG_BASIC}")
    
    # Process Level 2 .apkg
    if APKG_LEVEL.exists():
        process_apkg_images(APKG_LEVEL, OUTPUT_DIR)
    else:
        print(f"⚠️  Level 2 .apkg not found: {APKG_LEVEL}")
    
    print("\n" + "=" * 80)
    print("✅ Image extraction complete!")
    print(f"📁 Images saved to: {OUTPUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()

