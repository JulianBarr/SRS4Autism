#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rename pinyin media files from numeric names to original filenames.

This script reads the media mapping from the .apkg file and renames
the extracted files to their original filenames.
"""

import sys
import json
import zipfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "content_db" / "语言语文__拼音.apkg"
MEDIA_DIR = PROJECT_ROOT / "media" / "pinyin"


def main():
    """Rename media files to their original filenames"""
    print("=" * 80)
    print("Rename Pinyin Media Files")
    print("=" * 80)
    
    if not APKG_PATH.exists():
        print(f"❌ Error: APKG file not found at {APKG_PATH}")
        return
    
    if not MEDIA_DIR.exists():
        print(f"❌ Error: Media directory not found at {MEDIA_DIR}")
        return
    
    # Read media mapping from .apkg
    print("\n1. Reading media mapping from .apkg...")
    anki_media_map = {}
    with zipfile.ZipFile(APKG_PATH, 'r') as z:
        if 'media' in z.namelist():
            try:
                media_data = z.read('media').decode('utf-8')
                anki_media_map = json.loads(media_data)
                print(f"   ✅ Loaded {len(anki_media_map)} mappings")
            except Exception as e:
                print(f"   ❌ Failed to parse media mapping: {e}")
                return
        else:
            print("   ❌ No media mapping file found in .apkg")
            return
    
    # anki_media_map is: numeric_id -> original_filename
    # So we can use it directly
    
    # Rename files
    print("\n2. Renaming files...")
    renamed_count = 0
    skipped_count = 0
    error_count = 0
    
    for numeric_name, original_filename in anki_media_map.items():
        numeric_path = MEDIA_DIR / numeric_name
        original_path = MEDIA_DIR / original_filename
        
        if not numeric_path.exists():
            # File might already be renamed or doesn't exist
            if original_path.exists():
                skipped_count += 1
                continue
            else:
                print(f"   ⚠️  File not found: {numeric_name}")
                error_count += 1
                continue
        
        if original_path.exists() and original_path != numeric_path:
            # Original filename already exists, skip
            print(f"   ⚠️  Skipping {numeric_name} -> {original_filename} (target exists)")
            skipped_count += 1
            continue
        
        try:
            shutil.move(str(numeric_path), str(original_path))
            print(f"   ✅ Renamed: {numeric_name} -> {original_filename}")
            renamed_count += 1
        except Exception as e:
            print(f"   ❌ Failed to rename {numeric_name}: {e}")
            error_count += 1
    
    print(f"\n✅ Renaming complete!")
    print(f"   Renamed: {renamed_count}")
    print(f"   Skipped: {skipped_count}")
    print(f"   Errors: {error_count}")


if __name__ == "__main__":
    main()

