#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify that audio files are properly set up for Anki import.

This checks:
1. Audio files are in .apkg
2. Media mapping is correct
3. Template references are correct
4. Notes have WordAudio field populated
"""

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

print("=" * 80)
print("Verifying .apkg Audio Setup")
print("=" * 80)

with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    
    with zipfile.ZipFile(APKG_PATH, 'r') as z:
        z.extractall(tmpdir_path)
    
    # 1. Check media mapping
    print("\n1. Media Mapping:")
    media_file = tmpdir_path / "media"
    with open(media_file, 'r', encoding='utf-8') as f:
        media_map = json.loads(f.read())
    
    audio_files = ['妈妈.mp3', '爸爸.mp3', '摸.mp3', '妹妹.mp3', '米.mp3']
    all_good = True
    
    for audio_file in audio_files:
        found = False
        for num_id, filename in media_map.items():
            if filename == audio_file:
                # Check if file exists
                numeric_file = tmpdir_path / num_id
                if numeric_file.exists():
                    size = numeric_file.stat().st_size
                    print(f"   ✅ {audio_file} -> {num_id} ({size} bytes)")
                else:
                    print(f"   ❌ {audio_file} -> {num_id} (FILE MISSING)")
                    all_good = False
                found = True
                break
        if not found:
            print(f"   ❌ {audio_file} (NOT IN MAPPING)")
            all_good = False
    
    # 2. Check template
    print("\n2. Card 1 Back Template:")
    db = tmpdir_path / "collection.anki21"
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("SELECT models FROM col")
    models = json.loads(cursor.fetchone()[0])
    
    for mid, model in models.items():
        if model.get('name') == 'CUMA - Pinyin Syllable':
            for tmpl in model.get('tmpls', []):
                if tmpl.get('ord') == 1 or 'Word to Pinyin' in tmpl.get('name', ''):
                    back_template = tmpl.get('afmt', '')
                    if '[sound:{{WordAudio}}]' in back_template:
                        print("   ✅ Contains [sound:{{WordAudio}}]")
                        print(f"   Template start: {back_template[:100]}...")
                    else:
                        print("   ❌ Missing [sound:{{WordAudio}}]")
                        all_good = False
                    break
    
    # 3. Check notes
    print("\n3. Notes WordAudio Field:")
    field_names = [f.get('name') for f in model.get('flds', [])]
    cursor.execute("SELECT id, flds FROM notes WHERE mid = ?", (int(mid),))
    notes = cursor.fetchall()
    
    for note_id, flds in notes:
        fields = flds.split('\x1f')
        note_dict = dict(zip(field_names, fields))
        word_audio = note_dict.get('WordAudio', '')
        word_hanzi = note_dict.get('WordHanzi', '')
        
        if word_audio:
            # Check if it matches media mapping
            in_mapping = word_audio in media_map.values()
            status = "✅" if in_mapping else "⚠️"
            print(f"   {status} {word_hanzi}: WordAudio = '{word_audio}' (in mapping: {in_mapping})")
        else:
            print(f"   ❌ {word_hanzi}: WordAudio is EMPTY")
            all_good = False
    
    conn.close()
    
    # Summary
    print("\n" + "=" * 80)
    if all_good:
        print("✅ All checks passed! The .apkg should work correctly.")
        print("\n📝 To use in Anki:")
        print("   1. File → Import → Select Pinyin_Sample_Deck.apkg")
        print("   2. Choose 'Update' when asked about note type")
        print("   3. Anki will extract media files automatically")
        print("   4. Audio should play when Card 1 back is shown")
    else:
        print("❌ Some issues found. Please fix before importing.")
    print("=" * 80)


