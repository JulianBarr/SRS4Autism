#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2: Update Syllable Card - Word to Pinyin

This script:
1. Adds WordAudio field to syllable note type
2. Updates Card 1 (Word to Pinyin) back template to:
   - Play WordAudio when back is displayed
   - Fix pinyin dark mode compatibility
3. Creates 5 sample syllable notes with WordAudio field

Requirements:
- When back card is displayed, play WordAudio (e.g., "妈妈.mp3")
- Pinyin should be dark mode compatible
- WordHanzi should be optionally configurable
"""

import sys
import os
import sqlite3
import zipfile
import tempfile
import json
import shutil
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
INPUT_APKG = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
OUTPUT_APKG = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
MEDIA_DIR = PROJECT_ROOT / "media" / "pinyin"


def update_syllable_model_and_templates(apkg_path: Path, output_path: Path):
    """Update syllable note type to add WordAudio field and update templates"""
    
    if not apkg_path.exists():
        print(f"❌ Error: APKG file not found at {apkg_path}")
        return False
    
    print(f"📦 Opening .apkg file: {apkg_path}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg
        print("\n1. Extracting .apkg file...")
        with zipfile.ZipFile(apkg_path, 'r') as z:
            z.extractall(tmpdir_path)
        
        db_path = tmpdir_path / "collection.anki21"
        if not db_path.exists():
            db_path = tmpdir_path / "collection.anki2"
        
        if not db_path.exists():
            print("❌ Error: No database found in .apkg file")
            return False
        
        # Connect to database
        print("\n2. Updating note type model...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get note models
        cursor.execute("SELECT models FROM col")
        col_data = cursor.fetchone()
        models = json.loads(col_data[0]) if col_data else {}
        
        # Find syllable model
        syllable_model_id = None
        syllable_model = None
        
        for mid_str, model in models.items():
            if model.get('name') == 'CUMA - Pinyin Syllable':
                syllable_model_id = int(mid_str)
                syllable_model = model
                break
        
        if not syllable_model:
            print("❌ Error: CUMA - Pinyin Syllable model not found")
            conn.close()
            return False
        
        print(f"   ✅ Found syllable model (ID: {syllable_model_id})")
        
        # Check if WordAudio field exists, add if not
        field_names = [f.get('name', '') for f in syllable_model.get('flds', [])]
        
        if 'WordAudio' not in field_names:
            print("   ➕ Adding WordAudio field...")
            # Find position after WordPicture
            word_picture_idx = -1
            for i, field in enumerate(syllable_model['flds']):
                if field.get('name') == 'WordPicture':
                    word_picture_idx = i
                    break
            
            # Add new field after WordPicture (or at end if WordPicture not found)
            new_field = {
                'name': 'WordAudio',
                'rtl': False,
                'sticky': False,
                'font': 'Arial',
                'size': 20,
                'media': []
            }
            
            if word_picture_idx >= 0:
                syllable_model['flds'].insert(word_picture_idx + 1, new_field)
                field_names.insert(word_picture_idx + 1, 'WordAudio')
            else:
                syllable_model['flds'].append(new_field)
                field_names.append('WordAudio')
            
            print("   ✅ WordAudio field added")
        else:
            print("   ℹ️  WordAudio field already exists")
        
        # Update Card 1 (Word to Pinyin) back template
        print("\n3. Updating Card 1 (Word to Pinyin) templates...")
        
        tmpls = syllable_model.get('tmpls', [])
        card1_found = False
        
        for tmpl in tmpls:
            # Find Card 1 - usually named "Word to Pinyin" or index 1
            tmpl_name = tmpl.get('name', '')
            if 'Word to Pinyin' in tmpl_name or tmpl.get('ord', -1) == 1:
                card1_found = True
                
                # Update back template to play WordAudio and fix pinyin styling
                back_template = tmpl.get('afmt', '')
                
                # Check if already updated (has WordAudio reference)
                if '[sound:{{WordAudio}}]' not in back_template:
                    # Add WordAudio playback at the start of back template
                    audio_section = """{{FrontSide}}

<hr id="answer">

{{#WordAudio}}
<div style="display: none;">[sound:{{WordAudio}}]</div>
{{/WordAudio}}"""
                    
                    # Update back template
                    if back_template.startswith('{{FrontSide}}'):
                        # Replace the first part to add audio
                        back_template = back_template.replace(
                            '{{FrontSide}}\n\n<hr id="answer">',
                            audio_section
                        )
                    else:
                        # Prepend audio section
                        back_template = audio_section + '\n\n' + back_template
                    
                    tmpl['afmt'] = back_template
                    print("   ✅ Updated Card 1 back template to play WordAudio")
                
                # Update front template to fix pinyin dark mode styling
                front_template = tmpl.get('qfmt', '')
                
                # Update pinyin styling for dark mode compatibility
                if 'WordPinyin' in front_template:
                    import re
                    # Replace any WordPinyin display with dark mode compatible version
                    # Pattern: look for WordPinyin in various contexts
                    dark_mode_pinyin_replacement = '<p class="word-pinyin-hint" style="font-size: 24px; color: #ffffff !important; background-color: rgba(0, 0, 0, 0.5); padding: 8px 12px; border-radius: 4px; font-weight: 500; display: inline-block;">{{WordPinyin}}</p>'
                    
                    # Replace common patterns
                    # Pattern 1: <div style="...color: #666...">{{WordPinyin}}</div>
                    front_template = re.sub(
                        r'<div[^>]*style="[^"]*color:\s*#666[^"]*"[^>]*>{{WordPinyin}}</div>',
                        dark_mode_pinyin_replacement,
                        front_template
                    )
                    # Pattern 2: <p style="...color: #666...">{{WordPinyin}}</p>
                    front_template = re.sub(
                        r'<p[^>]*style="[^"]*color:\s*#666[^"]*"[^>]*>{{WordPinyin}}</p>',
                        dark_mode_pinyin_replacement,
                        front_template
                    )
                    # Pattern 3: Simple {{WordPinyin}} (if not already in a styled element)
                    if '{{WordPinyin}}' in front_template and 'word-pinyin-hint' not in front_template:
                        # Only replace if it's a standalone or in a simple div/p
                        front_template = re.sub(
                            r'(<div[^>]*class="word-display"[^>]*>.*?<p[^>]*class="word-hanzi"[^>]*>.*?</p>\s*)<div[^>]*style="[^"]*font-size:\s*24px[^"]*"[^>]*>{{WordPinyin}}</div>',
                            r'\1' + dark_mode_pinyin_replacement,
                            front_template,
                            flags=re.DOTALL
                        )
                    
                    tmpl['qfmt'] = front_template
                    print("   ✅ Updated Card 1 front template for dark mode compatibility")
                
                break
        
        if not card1_found:
            print("   ⚠️  Warning: Card 1 template not found, skipping template update")
        
        # Update CSS for dark mode pinyin compatibility
        css = syllable_model.get('css', '')
        if '.word-pinyin-hint' not in css or 'color: #ffffff' not in css:
            dark_mode_css = """
.word-pinyin-hint {
  font-size: 24px;
  color: #ffffff !important;
  background-color: rgba(0, 0, 0, 0.5);
  padding: 8px 12px;
  border-radius: 4px;
  font-weight: 500;
  display: inline-block;
}"""
            syllable_model['css'] = css + dark_mode_css
            print("   ✅ Updated CSS for dark mode pinyin compatibility")
        
        # Save updated models
        models[str(syllable_model_id)] = syllable_model
        cursor.execute("UPDATE col SET models = ?", (json.dumps(models),))
        conn.commit()
        
        # Store field order for note creation
        field_order = [f.get('name', '') for f in syllable_model.get('flds', [])]
        
        print("\n4. Creating 5 NEW sample syllable notes...")
        print("   (Not modifying any existing notes - only adding 5 new ones)")
        
        # Sample data for 5 NEW notes only
        sample_notes = [
            {
                'ElementToLearn': 'a',
                'Syllable': 'mā',
                'WordPinyin': 'mā mā',
                'WordHanzi': '妈妈',
                'WordPicture': '<img src="mommy.png">',
                'WordAudio': '妈妈.mp3',
                '_Remarks': 'Sample note 1 - 妈妈 (mom)',
                '_KG_Map': json.dumps({
                    "0": [{"kp": "pinyin-syllable-ma1", "skill": "form_to_sound", "weight": 1.0}],
                    "1": [{"kp": "pinyin-syllable-ma1", "skill": "sound_to_form", "weight": 1.0}]
                })
            },
            {
                'ElementToLearn': 'a',
                'Syllable': 'bà',
                'WordPinyin': 'bà ba',
                'WordHanzi': '爸爸',
                'WordPicture': '<img src="daddy.png">',
                'WordAudio': '爸爸.mp3',
                '_Remarks': 'Sample note 2 - 爸爸 (dad)',
                '_KG_Map': json.dumps({
                    "0": [{"kp": "pinyin-syllable-ba4", "skill": "form_to_sound", "weight": 1.0}],
                    "1": [{"kp": "pinyin-syllable-ba4", "skill": "sound_to_form", "weight": 1.0}]
                })
            },
            {
                'ElementToLearn': 'o',
                'Syllable': 'mō',
                'WordPinyin': 'mō',
                'WordHanzi': '摸',
                'WordPicture': '<img src="touch.png">',
                'WordAudio': '摸.mp3',
                '_Remarks': 'Sample note 3 - 摸 (touch)',
                '_KG_Map': json.dumps({
                    "0": [{"kp": "pinyin-syllable-mo1", "skill": "form_to_sound", "weight": 1.0}],
                    "1": [{"kp": "pinyin-syllable-mo1", "skill": "sound_to_form", "weight": 1.0}]
                })
            },
            {
                'ElementToLearn': 'e',
                'Syllable': 'mèi',
                'WordPinyin': 'mèi mei',
                'WordHanzi': '妹妹',
                'WordPicture': '<img src="sister.png">',
                'WordAudio': '妹妹.mp3',
                '_Remarks': 'Sample note 4 - 妹妹 (younger sister)',
                '_KG_Map': json.dumps({
                    "0": [{"kp": "pinyin-syllable-mei4", "skill": "form_to_sound", "weight": 1.0}],
                    "1": [{"kp": "pinyin-syllable-mei4", "skill": "sound_to_form", "weight": 1.0}]
                })
            },
            {
                'ElementToLearn': 'i',
                'Syllable': 'mǐ',
                'WordPinyin': 'mǐ',
                'WordHanzi': '米',
                'WordPicture': '<img src="rice.png">',
                'WordAudio': '米.mp3',
                '_Remarks': 'Sample note 5 - 米 (rice)',
                '_KG_Map': json.dumps({
                    "0": [{"kp": "pinyin-syllable-mi3", "skill": "form_to_sound", "weight": 1.0}],
                    "1": [{"kp": "pinyin-syllable-mi3", "skill": "sound_to_form", "weight": 1.0}]
                })
            }
        ]
        
        # Reconnect to add notes
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get deck ID - try to find from existing cards or use default
        deck_id = 1  # Default deck
        
        # Try to get deck from existing cards
        try:
            cursor.execute("SELECT did FROM cards LIMIT 1")
            card_row = cursor.fetchone()
            if card_row:
                deck_id = card_row[0]
        except:
            pass
        
        # Try to get deck from decks table if it exists
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='decks'")
            if cursor.fetchone():
                cursor.execute("SELECT id FROM decks WHERE name LIKE '%拼音%' OR name LIKE '%Pinyin%' LIMIT 1")
                deck_row = cursor.fetchone()
                if deck_row:
                    deck_id = deck_row[0]
        except:
            pass
        
        print(f"   Using deck ID: {deck_id}")
        
        import time
        note_ids_created = []
        
        for note_data in sample_notes:
            # Create note
            note_id = int(time.time() * 1000) + len(note_ids_created)
            
            # Build fields array in correct order (matching model field order)
            fields = []
            for field_name in field_order:
                if field_name in note_data:
                    fields.append(str(note_data[field_name]))
                else:
                    fields.append('')
            
            fields_str = '\x1f'.join(fields)
            
            # Insert note
            cursor.execute("""
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                note_id,
                str(note_id),  # guid
                syllable_model_id,  # mid
                int(time.time()),  # mod
                -1,  # usn
                '',  # tags
                fields_str,  # flds
                note_data.get('Syllable', ''),  # sfld (sort field)
                0,  # csum
                0,  # flags
                ''  # data
            ))
            
            # Create cards for this note (6 cards per syllable note)
            for card_ord in range(6):
                card_id = int(time.time() * 1000) + card_ord + len(note_ids_created) * 10
                cursor.execute("""
                    INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    card_id,
                    note_id,
                    deck_id,
                    card_ord,
                    int(time.time()),
                    -1,
                    0,  # type (0 = new)
                    0,  # queue (0 = new)
                    0,  # due
                    0,  # ivl
                    0,  # factor
                    0,  # reps
                    0,  # lapses
                    0,  # left
                    0,  # odue
                    0,  # odid
                    0,  # flags
                    ''  # data
                ))
            
            note_ids_created.append(note_id)
            print(f"   ✅ Created note: {note_data.get('WordHanzi')} ({note_data.get('Syllable')})")
        
        conn.commit()
        conn.close()
        
        # Repackage .apkg
        print("\n5. Repackaging .apkg file...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
            # Add all files from tmpdir
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        print(f"   ✅ Created updated .apkg: {output_path}")
        return True


def main():
    """Main function"""
    print("=" * 80)
    print("Step 2: Update Syllable Card - Word to Pinyin")
    print("=" * 80)
    print("\nUpdates:")
    print("  1. Add WordAudio field to syllable note type")
    print("  2. Card 1 back plays WordAudio when displayed")
    print("  3. Fix pinyin dark mode compatibility")
    print("  4. Create 5 NEW sample syllable notes (only, not modifying existing notes)")
    print("\n⚠️  Note: Adding WordAudio field will make existing notes inconsistent.")
    print("   Run fix_apkg_field_count.py separately if needed to fix all notes.")
    
    success = update_syllable_model_and_templates(INPUT_APKG, OUTPUT_APKG)
    
    if success:
        print("\n✅ Step 2 complete!")
        print(f"\n📦 Updated .apkg file: {OUTPUT_APKG}")
        print("\n📝 Next steps:")
        print("  - Generate WordAudio files using Google TTS (e.g., 妈妈.mp3)")
        print("  - Add audio files to media directory and include in .apkg")
        print("  - Import the updated .apkg file into Anki to verify")
    else:
        print("\n❌ Failed to update .apkg file")


if __name__ == "__main__":
    main()

