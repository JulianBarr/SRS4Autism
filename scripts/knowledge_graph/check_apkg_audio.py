#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check if audio files are properly set up in .apkg"""

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
    syllable_model = None
    for mid, model in models.items():
        if model.get('name') == 'CUMA - Pinyin Syllable':
            syllable_model = model
            break
    
    if syllable_model:
        print("📋 Syllable Model Fields:")
        for i, field in enumerate(syllable_model.get('flds', [])):
            print(f"   {i}: {field.get('name')}")
        
        # Check Card 1 back template
        tmpls = syllable_model.get('tmpls', [])
        for tmpl in tmpls:
            if 'Word to Pinyin' in tmpl.get('name', '') or tmpl.get('ord', -1) == 1:
                print(f"\n📄 Card 1 Back Template:")
                back_template = tmpl.get('afmt', '')
                if 'WordAudio' in back_template:
                    print("   ✅ Contains WordAudio reference")
                    # Show relevant part
                    lines = back_template.split('\n')
                    for i, line in enumerate(lines):
                        if 'WordAudio' in line or 'sound:' in line:
                            print(f"   Line {i}: {line.strip()}")
                else:
                    print("   ❌ No WordAudio reference found")
                    print("   Template preview:")
                    print(back_template[:500])
    
    # Check notes
    print("\n📝 Notes with WordAudio field:")
    cursor.execute("SELECT id, flds FROM notes WHERE mid = (SELECT mid FROM notes WHERE flds LIKE '%妈妈%' LIMIT 1) LIMIT 5")
    notes = cursor.fetchall()
    
    field_names = [f.get('name') for f in syllable_model.get('flds', [])]
    
    for note_id, flds in notes:
        fields = flds.split('\x1f')
        print(f"\n   Note {note_id}:")
        for i, (field_name, field_value) in enumerate(zip(field_names, fields)):
            if field_name == 'WordAudio' or 'Audio' in field_name:
                print(f"      {field_name}: '{field_value}'")
            if field_name == 'WordHanzi':
                print(f"      {field_name}: '{field_value}'")
    
    # Check media mapping
    print("\n📦 Media Files:")
    media_file = tmpdir_path / "media"
    if media_file.exists():
        with open(media_file, 'r', encoding='utf-8') as f:
            media_map = json.loads(f.read())
        
        # Find our audio files
        audio_files = ['妈妈.mp3', '爸爸.mp3', '摸.mp3', '妹妹.mp3', '米.mp3']
        print(f"   Total media entries: {len(media_map)}")
        for audio_file in audio_files:
            found = False
            for num_id, filename in media_map.items():
                if filename == audio_file:
                    print(f"   ✅ {audio_file} -> {num_id}")
                    # Check if file exists in zip
                    numeric_file = tmpdir_path / num_id
                    if numeric_file.exists():
                        size = numeric_file.stat().st_size
                        print(f"      File exists: {size} bytes")
                    else:
                        print(f"      ⚠️  File not found in extracted directory")
                    found = True
                    break
            if not found:
                print(f"   ❌ {audio_file} not found in media mapping")
    
    conn.close()


