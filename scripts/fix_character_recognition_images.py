#!/usr/bin/env python3
"""
Fix malformed image references in character_recognition_notes database.

This script fixes image references that are missing quotes or paths,
e.g., <img src=want2.png> -> <img src="/media/character_recognition/want2.png">
"""

import sys
import json
import re
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import get_db_session
from backend.database.models import CharacterRecognitionNote

MEDIA_DIR = PROJECT_ROOT / "media" / "character_recognition"


def fix_image_references_in_html(html_content: str) -> str:
    """Fix malformed image references in HTML content"""
    if not html_content:
        return html_content
    
    # Pattern to match <img src="filename">, <img src='filename'>, or <img src=filename>
    img_pattern = r'<img[^>]*src=(["\']?)([^"\'>\s]+)\1[^>]*>'
    
    def replace_img(match):
        img_tag = match.group(0)
        quote_char = match.group(1)  # " or ' or empty
        filename = match.group(2)
        
        # If it's already a full URL or absolute path, keep it
        if filename.startswith('http') or filename.startswith('/'):
            return img_tag
        
        # Check if file exists in character_recognition media directory (case-insensitive)
        new_path = None
        for existing_file in MEDIA_DIR.iterdir():
            if existing_file.is_file() and existing_file.name.lower() == filename.lower():
                new_path = f"/media/character_recognition/{existing_file.name}"
                break
        
        if new_path:
            # Replace src with proper quoting
            if quote_char:
                return img_tag.replace(f'src={quote_char}{filename}{quote_char}', f'src="{new_path}"')
            else:
                return img_tag.replace(f'src={filename}', f'src="{new_path}"')
        
        return img_tag
    
    # Replace all img tags
    fixed_html = re.sub(img_pattern, replace_img, html_content)
    
    return fixed_html


def fix_database_entries():
    """Fix all malformed image references in the database"""
    print("=" * 80)
    print("Fixing malformed image references in character_recognition_notes")
    print("=" * 80)
    print()
    
    if not MEDIA_DIR.exists():
        print(f"❌ Media directory not found: {MEDIA_DIR}")
        return
    
    print(f"📁 Media directory: {MEDIA_DIR}")
    print()
    
    fixed_count = 0
    total_count = 0
    
    with get_db_session() as db:
        # Get all notes
        notes = db.query(CharacterRecognitionNote).all()
        total_count = len(notes)
        
        print(f"📊 Found {total_count} notes to check")
        print()
        
        for note in notes:
            if not note.fields:
                continue
            
            # Parse JSON fields
            try:
                fields = json.loads(note.fields) if isinstance(note.fields, str) else note.fields
            except:
                continue
            
            # Check each field for image references
            updated = False
            for field_name, field_value in fields.items():
                if isinstance(field_value, str) and ('<img' in field_value or field_value.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))):
                    fixed_value = fix_image_references_in_html(field_value)
                    if fixed_value != field_value:
                        fields[field_name] = fixed_value
                        updated = True
            
            # Update database if any field was fixed
            if updated:
                note.fields = json.dumps(fields, ensure_ascii=False)
                fixed_count += 1
                print(f"  ✅ Fixed images in note {note.note_id} (character: {note.character})")
        
        # Commit all changes
        if fixed_count > 0:
            db.commit()
            print()
            print(f"✅ Fixed {fixed_count} notes")
        else:
            print()
            print("ℹ️  No malformed image references found")
    
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)


if __name__ == "__main__":
    fix_database_entries()






