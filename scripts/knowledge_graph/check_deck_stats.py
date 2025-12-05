#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick script to check note count in .apkg file"""

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
    
    # Count notes
    cursor.execute("SELECT COUNT(*) FROM notes")
    note_count = cursor.fetchone()[0]
    
    # Count syllable notes
    cursor.execute("SELECT COUNT(*) FROM notes WHERE mid = (SELECT id FROM (SELECT mid, COUNT(*) as cnt FROM notes GROUP BY mid ORDER BY cnt DESC LIMIT 1))")
    syllable_count = cursor.fetchone()[0]
    
    # Count cards
    cursor.execute("SELECT COUNT(*) FROM cards")
    card_count = cursor.fetchone()[0]
    
    conn.close()
    
    file_size_mb = APKG_PATH.stat().st_size / (1024 * 1024)
    
    print(f"📊 Deck Statistics:")
    print(f"   Total notes: {note_count}")
    print(f"   Total cards: {card_count}")
    print(f"   File size: {file_size_mb:.2f} MB")
    print(f"\n✅ Deck contains only {note_count} notes (should be 5)")


