#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix Card 1 back template to include WordAudio playback"""

import sys
import sqlite3
import zipfile
import tempfile
import json
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"

with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    
    print("📦 Extracting .apkg...")
    with zipfile.ZipFile(APKG_PATH, 'r') as z:
        z.extractall(tmpdir_path)
    
    db_path = tmpdir_path / "collection.anki21"
    if not db_path.exists():
        db_path = tmpdir_path / "collection.anki2"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get models
    cursor.execute("SELECT models FROM col")
    models = json.loads(cursor.fetchone()[0])
    
    # Find syllable model
    syllable_model_id = None
    syllable_model = None
    
    for mid_str, model in models.items():
        if model.get('name') == 'CUMA - Pinyin Syllable':
            syllable_model_id = int(mid_str)
            syllable_model = model
            break
    
    if not syllable_model:
        print("❌ Syllable model not found")
        conn.close()
        exit(1)
    
    print("✅ Found syllable model")
    
    # Find Card 1 template (Word to Pinyin)
    tmpls = syllable_model.get('tmpls', [])
    card1_found = False
    
    for tmpl in tmpls:
        tmpl_name = tmpl.get('name', '')
        tmpl_ord = tmpl.get('ord', -1)
        
        # Card 1 is usually ord=1 or contains "Word to Pinyin"
        if tmpl_ord == 1 or 'Word to Pinyin' in tmpl_name or 'word to pinyin' in tmpl_name.lower():
            card1_found = True
            print(f"\n📄 Found Card 1 template: {tmpl_name} (ord: {tmpl_ord})")
            
            back_template = tmpl.get('afmt', '')
            
            # Check if WordAudio is already there
            if '[sound:{{WordAudio}}]' in back_template:
                print("   ✅ WordAudio already in template")
                print("   Current template (first 200 chars):")
                print(back_template[:200])
            else:
                print("   ➕ Adding WordAudio to back template...")
                print("   Original template starts with:")
                print(back_template[:150])
                
                # The actual template starts with {{FrontSide}}<hr> (no newlines)
                # We need to insert the audio right after {{FrontSide}}
                # Anki will process [sound:...] tags even in hidden divs
                
                # Insert audio playback right after {{FrontSide}}
                audio_code = '{{#WordAudio}}[sound:{{WordAudio}}]{{/WordAudio}}'
                
                # Replace {{FrontSide}} with {{FrontSide}} + audio
                if '{{FrontSide}}' in back_template:
                    back_template = back_template.replace(
                        '{{FrontSide}}',
                        f'{{{{FrontSide}}}}{audio_code}',
                        1  # Only replace first occurrence
                    )
                    tmpl['afmt'] = back_template
                    print("   ✅ Updated back template")
                    print("\n   Updated template (first 200 chars):")
                    print(back_template[:200])
                else:
                    print("   ⚠️  Could not find {{FrontSide}} in template")
                    print("   Template starts with:")
                    print(back_template[:200])
            
            break
    
    if not card1_found:
        print("❌ Card 1 template not found")
        print("Available templates:")
        for tmpl in tmpls:
            print(f"   - {tmpl.get('name')} (ord: {tmpl.get('ord')})")
    else:
        # Save updated models
        models[str(syllable_model_id)] = syllable_model
        cursor.execute("UPDATE col SET models = ?", (json.dumps(models),))
        conn.commit()
        print("\n✅ Models updated")
    
    conn.close()
    
    # Repackage
    print("\n📦 Repackaging .apkg...")
    with zipfile.ZipFile(APKG_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
        for file_path in tmpdir_path.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(tmpdir_path)
                z.write(file_path, arcname)
    
    print("✅ .apkg updated")
