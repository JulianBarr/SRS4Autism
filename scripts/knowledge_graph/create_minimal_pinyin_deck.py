#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create a minimal pinyin deck with only 5 sample notes for testing.

This creates a fresh .apkg file with:
- Updated note type models (with WordAudio field)
- Updated templates
- Only 5 sample syllable notes
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
ORIGINAL_APKG = PROJECT_ROOT / "data" / "content_db" / "语言语文__拼音.apkg"
OUTPUT_APKG = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"


def create_minimal_deck(original_apkg: Path, output_apkg: Path):
    """Create a minimal deck with only 5 sample notes"""
    
    if not original_apkg.exists():
        print(f"❌ Error: Original APKG file not found at {original_apkg}")
        return False
    
    print(f"📦 Reading original .apkg file: {original_apkg}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract original .apkg to get models and templates
        print("\n1. Extracting original .apkg to get models...")
        with zipfile.ZipFile(original_apkg, 'r') as z:
            z.extractall(tmpdir_path)
        
        db_path = tmpdir_path / "collection.anki21"
        if not db_path.exists():
            db_path = tmpdir_path / "collection.anki2"
        
        if not db_path.exists():
            print("❌ Error: No database found in .apkg file")
            return False
        
        # Connect to database
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
                syllable_model = model.copy()  # Make a copy to modify
                break
        
        if not syllable_model:
            print("❌ Error: CUMA - Pinyin Syllable model not found")
            conn.close()
            return False
        
        print(f"   ✅ Found syllable model (ID: {syllable_model_id})")
        
        # Add WordAudio field if not present
        field_names = [f.get('name', '') for f in syllable_model.get('flds', [])]
        
        if 'WordAudio' not in field_names:
            print("   ➕ Adding WordAudio field...")
            # Find position after WordPicture
            word_picture_idx = -1
            for i, field in enumerate(syllable_model['flds']):
                if field.get('name') == 'WordPicture':
                    word_picture_idx = i
                    break
            
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
            else:
                syllable_model['flds'].append(new_field)
            
            print("   ✅ WordAudio field added")
        
        # Update Card 1 back template to play WordAudio
        print("\n2. Updating Card 1 templates...")
        tmpls = syllable_model.get('tmpls', [])
        card1_found = False
        
        for tmpl in tmpls:
            tmpl_name = tmpl.get('name', '')
            if 'Word to Pinyin' in tmpl_name or tmpl.get('ord', -1) == 1:
                card1_found = True
                
                # Update back template
                back_template = tmpl.get('afmt', '')
                if '[sound:{{WordAudio}}]' not in back_template:
                    audio_section = """{{FrontSide}}

<hr id="answer">

{{#WordAudio}}
<div style="display: none;">[sound:{{WordAudio}}]</div>
{{/WordAudio}}"""
                    
                    if back_template.startswith('{{FrontSide}}'):
                        back_template = back_template.replace(
                            '{{FrontSide}}\n\n<hr id="answer">',
                            audio_section
                        )
                    else:
                        back_template = audio_section + '\n\n' + back_template
                    
                    tmpl['afmt'] = back_template
                    print("   ✅ Updated Card 1 back template to play WordAudio")
                break
        
        # Update CSS for dark mode
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
            print("   ✅ Updated CSS for dark mode")
        
        # Update models
        models[str(syllable_model_id)] = syllable_model
        
        # DELETE ALL EXISTING NOTES (all note types)
        print("\n3. Removing all existing notes (keeping only models)...")
        cursor.execute("DELETE FROM notes")
        cursor.execute("DELETE FROM cards")
        deleted_notes = cursor.rowcount
        print(f"   ✅ Deleted all existing notes")
        
        # Create 5 new sample notes
        print("\n4. Creating 5 sample syllable notes...")
        
        field_order = [f.get('name', '') for f in syllable_model.get('flds', [])]
        
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
        
        # Get deck ID from existing cards or use default
        deck_id = 1  # Default deck
        
        try:
            cursor.execute("SELECT did FROM cards LIMIT 1")
            card_row = cursor.fetchone()
            if card_row:
                deck_id = card_row[0]
        except:
            pass
        
        print(f"   Using deck ID: {deck_id}")
        
        note_ids_created = []
        
        for note_data in sample_notes:
            note_id = int(time.time() * 1000) + len(note_ids_created)
            
            fields = []
            for field_name in field_order:
                if field_name in note_data:
                    fields.append(str(note_data[field_name]))
                else:
                    fields.append('')
            
            fields_str = '\x1f'.join(fields)
            
            cursor.execute("""
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                note_id,
                str(note_id),
                syllable_model_id,
                int(time.time()),
                -1,
                '',
                fields_str,
                note_data.get('Syllable', ''),
                0,
                0,
                ''
            ))
            
            # Create cards (6 cards per syllable note)
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
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    ''
                ))
            
            note_ids_created.append(note_id)
            print(f"   ✅ Created note: {note_data.get('WordHanzi')} ({note_data.get('Syllable')})")
        
        # Save updated models
        cursor.execute("UPDATE col SET models = ?", (json.dumps(models),))
        conn.commit()
        conn.close()
        
        # Repackage .apkg
        print("\n5. Creating minimal .apkg file...")
        output_apkg.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(output_apkg, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_path in tmpdir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    z.write(file_path, arcname)
        
        file_size = output_apkg.stat().st_size / (1024 * 1024)  # Size in MB
        print(f"   ✅ Created minimal .apkg: {output_apkg}")
        print(f"   📦 File size: {file_size:.2f} MB (should be much smaller now)")
        return True


def main():
    """Main function"""
    print("=" * 80)
    print("Create Minimal Pinyin Deck (5 notes only)")
    print("=" * 80)
    
    success = create_minimal_deck(ORIGINAL_APKG, OUTPUT_APKG)
    
    if success:
        print("\n✅ Minimal deck created!")
        print(f"\n📦 Output: {OUTPUT_APKG}")
        print("   - Contains only 5 sample notes")
        print("   - Updated models and templates")
        print("   - Ready for testing")
    else:
        print("\n❌ Failed to create minimal deck")


if __name__ == "__main__":
    main()

