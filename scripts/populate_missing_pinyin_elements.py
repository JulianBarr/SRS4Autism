#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate missing pinyin elements from missing_pinyin_elements.dat file.

Format: element, proper_name, example_char, picture_file
Example: m, mo, 摸, touch.jpeg
"""

import sys
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import get_db_session, create_backup, DB_PATH
from backend.database.models import PinyinElementNote
from scripts.knowledge_graph.pinyin_parser import PINYIN_INITIALS, add_tone_to_final


def generate_tone_variations(proper_name: str) -> list:
    """Generate all 4 tone variations using the proper name.
    
    Args:
        proper_name: The proper pinyin name (e.g., 'mo' for element 'm')
    Returns:
        List of 4 tone variations: [mō, mó, mǒ, mò] or ['', '', '', ''] for initials
    """
    # For initials (single character), return empty tones
    if len(proper_name) == 1 and proper_name in PINYIN_INITIALS:
        return ['', '', '', '']
    
    # For finals, generate tones using the proper name
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(proper_name, tone)
        variations.append(toned)
    return variations


def determine_element_type(element: str) -> str:
    """Determine if element is an initial or final."""
    if element in PINYIN_INITIALS:
        return 'initial'
    return 'final'


def parse_data_file(data_file: Path) -> list:
    """Parse the missing_pinyin_elements.dat file."""
    elements_data = []
    
    if not data_file.exists():
        print(f"❌ Data file not found: {data_file}")
        return elements_data
    
    with open(data_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Parse format: element, proper_name, example_char, picture_file
            # Handle both comma and colon separators
            parts = [p.strip() for p in line.replace(':', ',').split(',')]
            
            if len(parts) < 4:
                print(f"⚠️  Line {line_num}: Invalid format (expected 4 parts): {line}")
                continue
            
            element = parts[0]
            proper_name = parts[1]
            example_char = parts[2]
            picture_file = parts[3]
            
            elements_data.append({
                'element': element,
                'proper_name': proper_name,
                'example_char': example_char,
                'picture_file': picture_file
            })
    
    return elements_data


def populate_elements(elements_data: list):
    """Populate pinyin elements in the database."""
    print(f"\n📝 Processing {len(elements_data)} elements...")
    
    with get_db_session() as db:
        updated_count = 0
        created_count = 0
        
        for elem_data in elements_data:
            element = elem_data['element']
            proper_name = elem_data['proper_name']
            example_char = elem_data['example_char']
            picture_file = elem_data['picture_file']
            element_type = determine_element_type(element)
            
            # Generate tone variations
            tone_variations = generate_tone_variations(proper_name)
            
            # Find existing element
            existing = db.query(PinyinElementNote).filter(
                PinyinElementNote.element == element
            ).first()
            
            if existing:
                # Update existing element - always update from data file
                fields = json.loads(existing.fields) if existing.fields else {}
                
                # Always update ExampleChar and Picture from data file
                if example_char:
                    fields['ExampleChar'] = example_char
                if picture_file:
                    fields['Picture'] = picture_file
                
                # Always update tones from proper_name
                fields['Tone1'] = tone_variations[0] if len(tone_variations) > 0 else ''
                fields['Tone2'] = tone_variations[1] if len(tone_variations) > 1 else ''
                fields['Tone3'] = tone_variations[2] if len(tone_variations) > 2 else ''
                fields['Tone4'] = tone_variations[3] if len(tone_variations) > 3 else ''
                
                # Ensure Element field is set
                fields['Element'] = element
                
                existing.fields = json.dumps(fields, ensure_ascii=False)
                updated_count += 1
                print(f"   ✅ Updated: {element} ({element_type}) - ExampleChar: {example_char}, Picture: {picture_file}")
            else:
                # Create new element
                # Determine display order (use a high number for now)
                max_order = db.query(PinyinElementNote.display_order).order_by(
                    PinyinElementNote.display_order.desc()
                ).first()
                next_order = (max_order[0] if max_order else 0) + 1
                
                fields = {
                    'Element': element,
                    'ExampleChar': example_char,
                    'Picture': picture_file,
                    'Tone1': tone_variations[0] if len(tone_variations) > 0 else '',
                    'Tone2': tone_variations[1] if len(tone_variations) > 1 else '',
                    'Tone3': tone_variations[2] if len(tone_variations) > 2 else '',
                    'Tone4': tone_variations[3] if len(tone_variations) > 3 else '',
                    '_Remarks': f'Teaching card for pinyin element {element}',
                    '_KG_Map': json.dumps({
                        "0": [{"kp": f"pinyin-element-{element}", "skill": "form_to_sound", "weight": 1.0}]
                    })
                }
                
                new_note = PinyinElementNote(
                    note_id=f"element_{element}_{next_order}",
                    element=element,
                    element_type=element_type,
                    display_order=next_order,
                    fields=json.dumps(fields, ensure_ascii=False)
                )
                
                db.add(new_note)
                created_count += 1
                print(f"   ➕ Created: {element} ({element_type}) - ExampleChar: {example_char}, Picture: {picture_file}")
        
        print(f"\n✅ Summary:")
        print(f"   - Updated: {updated_count}")
        print(f"   - Created: {created_count}")
        print(f"   - Total processed: {len(elements_data)}")


def main():
    """Main function."""
    print("=" * 80)
    print("Populate Missing Pinyin Elements")
    print("=" * 80)
    
    # Data file path
    data_file = PROJECT_ROOT / "data" / "content_db" / "missing_pinyin_elements.dat"
    
    # Backup database first
    print("\n💾 Creating database backup...")
    try:
        backup_path = create_backup()
        print(f"   ✅ Backup created: {backup_path}")
    except Exception as e:
        print(f"   ⚠️  Warning: Could not create backup: {e}")
        response = input("   Continue without backup? (y/n): ")
        if response.lower() != 'y':
            print("   ❌ Aborted.")
            return
    
    # Parse data file
    print(f"\n📖 Reading data file: {data_file}")
    elements_data = parse_data_file(data_file)
    
    if not elements_data:
        print("   ❌ No elements to process.")
        return
    
    print(f"   ✅ Found {len(elements_data)} elements")
    
    # Populate elements
    try:
        populate_elements(elements_data)
        print("\n✅ Population complete!")
    except Exception as e:
        print(f"\n❌ Error during population: {e}")
        import traceback
        traceback.print_exc()
        print("\n⚠️  Database may be in an inconsistent state. Consider restoring from backup.")


if __name__ == "__main__":
    main()

