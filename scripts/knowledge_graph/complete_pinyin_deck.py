#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete pinyin deck by identifying missing elements and generating notes for them.
Based on 5-stage curriculum from "Ask Gemini to complete and reorg current pinyin deck.md"
"""

import sys
import sqlite3
import zipfile
import tempfile
import json
import time
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.pinyin_parser import parse_pinyin, extract_tone, add_tone_to_final

def generate_tone_variations(base_syllable: str) -> list:
    """Generate all 4 tone variations"""
    pinyin_no_tone, _ = extract_tone(base_syllable)
    variations = []
    for tone in [1, 2, 3, 4]:
        toned = add_tone_to_final(pinyin_no_tone, tone)
        variations.append(toned)
    return variations

PROJECT_ROOT = project_root
APKG_PATH = PROJECT_ROOT / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"

# 5-Stage Curriculum - Complete
STAGES = {
    1: {
        'name': 'Lips & Simple Vowels',
        'initials': ['b', 'p', 'm', 'f'],
        'finals': ['a', 'o', 'e', 'i', 'u'],
        'order': 1
    },
    2: {
        'name': 'Tip of Tongue',
        'initials': ['d', 't', 'n', 'l'],
        'finals': ['ai', 'ei', 'ao', 'ou'],
        'order': 2
    },
    3: {
        'name': 'Root of Tongue',
        'initials': ['g', 'k', 'h'],
        'finals': ['an', 'en', 'in', 'un'],
        'order': 3
    },
    4: {
        'name': 'Teeth & Curl',
        'initials': ['z', 'c', 's', 'zh', 'ch', 'sh', 'r'],
        'finals': ['ang', 'eng', 'ing', 'ong', 'er'],
        'order': 4
    },
    5: {
        'name': 'Magic Palatals',
        'initials': ['j', 'q', 'x', 'y', 'w'],
        'finals': ['i', 'u', 'ü', 'ia', 'ie', 'iao', 'iu', 'ian', 'iang', 'iong', 
                   'ua', 'uo', 'uai', 'ui', 'uan', 'uang', 'ue', 'üe', 'üan', 'ün'],
        'order': 5
    }
}

# Valid pinyin combinations (simplified - some combinations don't exist)
VALID_COMBINATIONS = {
    # Stage 1
    ('b', 'a'), ('b', 'o'), ('b', 'i'), ('b', 'u'),
    ('p', 'a'), ('p', 'o'), ('p', 'i'), ('p', 'u'),
    ('m', 'a'), ('m', 'o'), ('m', 'e'), ('m', 'i'), ('m', 'u'),
    ('f', 'a'), ('f', 'o'), ('f', 'u'),
    # Stage 2
    ('d', 'ai'), ('d', 'ao'), ('d', 'ou'),
    ('t', 'ai'), ('t', 'ao'), ('t', 'ou'),
    ('n', 'ai'), ('n', 'ao'), ('n', 'ou'),
    ('l', 'ai'), ('l', 'ao'), ('l', 'ou'),
    # Stage 3
    ('g', 'an'), ('g', 'en'),
    ('k', 'an'), ('k', 'en'),
    ('h', 'an'), ('h', 'en'),
    # Stage 4
    ('z', 'ang'), ('z', 'eng'), ('z', 'ong'),
    ('c', 'ang'), ('c', 'eng'), ('c', 'ong'),
    ('s', 'ang'), ('s', 'eng'), ('s', 'ong'),
    ('zh', 'ang'), ('zh', 'eng'), ('zh', 'ong'),
    ('ch', 'ang'), ('ch', 'eng'), ('ch', 'ong'),
    ('sh', 'ang'), ('sh', 'eng'), ('sh', 'ong'),
    ('r', 'ang'), ('r', 'eng'), ('r', 'ong'),
    # Stage 5 - simplified, many more combinations exist
    ('j', 'i'), ('j', 'ia'), ('j', 'ie'), ('j', 'iao'), ('j', 'iu'), ('j', 'ian'), ('j', 'iang'), ('j', 'iong'),
    ('q', 'i'), ('q', 'ia'), ('q', 'ie'), ('q', 'iao'), ('q', 'iu'), ('q', 'ian'), ('q', 'iang'), ('q', 'iong'),
    ('x', 'i'), ('x', 'ia'), ('x', 'ie'), ('x', 'iao'), ('x', 'iu'), ('x', 'ian'), ('x', 'iang'), ('x', 'iong'),
    ('y', 'a'), ('y', 'e'), ('y', 'i'), ('y', 'o'), ('y', 'u'),
    ('w', 'a'), ('w', 'e'), ('w', 'o'), ('w', 'u'),
}

def get_existing_syllables(apkg_path: Path) -> set:
    """Get set of existing syllables in the deck"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        with zipfile.ZipFile(apkg_path, 'r') as z:
            z.extractall(tmpdir_path)
        
        db = tmpdir_path / "collection.anki21"
        if not db.exists():
            db = tmpdir_path / "collection.anki2"
        
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT models FROM col")
        models = json.loads(cursor.fetchone()[0])
        
        existing = set()
        for mid_str, model in models.items():
            if model.get('name') == 'CUMA - Pinyin Syllable':
                field_names = [f['name'] for f in model.get('flds', [])]
                cursor.execute("SELECT flds FROM notes WHERE mid = ?", (int(mid_str),))
                notes = cursor.fetchall()
                
                for flds_str, in notes:
                    fields = flds_str.split('\x1f')
                    while len(fields) < len(field_names):
                        fields.append('')
                    field_dict = dict(zip(field_names, fields))
                    syllable = field_dict.get('Syllable', '').strip()
                    if syllable:
                        # Normalize: remove tone for comparison
                        pinyin_no_tone, _ = extract_tone(syllable)
                        existing.add(pinyin_no_tone)
                break
        
        conn.close()
        return existing

def identify_missing_syllables():
    """Identify missing syllables according to curriculum"""
    print("=" * 80)
    print("Identify Missing Pinyin Syllables")
    print("=" * 80)
    
    # Get existing syllables
    print("\n📋 Analyzing existing deck...")
    existing = get_existing_syllables(APKG_PATH)
    print(f"   Found {len(existing)} existing syllable bases")
    
    # Generate all possible syllables from curriculum
    print("\n🔍 Generating curriculum syllables...")
    missing_by_stage = defaultdict(list)
    all_curriculum = set()
    
    for stage_num, stage_config in STAGES.items():
        for initial in stage_config['initials']:
            for final in stage_config['finals']:
                # Check if combination is valid
                if (initial, final) in VALID_COMBINATIONS or not initial:
                    syllable_base = initial + final if initial else final
                    all_curriculum.add(syllable_base)
                    
                    if syllable_base not in existing:
                        missing_by_stage[stage_num].append((initial, final, syllable_base))
    
    print(f"\n📊 Analysis:")
    print(f"   Curriculum syllables: {len(all_curriculum)}")
    print(f"   Existing syllables: {len(existing)}")
    print(f"   Missing syllables: {len(all_curriculum) - len(existing)}")
    
    print(f"\n📋 Missing by stage:")
    for stage_num in [1, 2, 3, 4, 5]:
        missing = missing_by_stage[stage_num]
        if missing:
            print(f"\n   Stage {stage_num} ({STAGES[stage_num]['name']}): {len(missing)} missing")
            print(f"   Examples: {', '.join([s[2] for s in missing[:10]])}")
    
    return missing_by_stage

if __name__ == "__main__":
    identify_missing_syllables()

