#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch Anki deck with business logic from fix_pinyin_deck.py

This script:
1. Reads Pinyin_Sample_Deck.apkg
2. Applies normalization and stage assignment from fix_pinyin_deck.py
3. Fills missing combinations
4. Outputs patched CSV for Anki import
"""

import sys
import os
import sqlite3
import zipfile
import tempfile
import json
import csv
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple

# Add scripts directory to path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(script_dir))

# Import valid pinyin combinations
from pinyin_valid_combinations import is_valid_pinyin_syllable as check_valid_syllable

# Business logic constants and functions from fix_pinyin_deck.py
# (Copied here to ensure availability and avoid import issues)
STAGE_ORDER = {
    'a': 1, 'o': 1, 'e': 1, 'i': 1, 'u': 1, 'ü': 1, 'b': 1, 'p': 1, 'm': 1, 'f': 1, # Lips
    'ai': 2, 'ei': 2, 'ui': 2, 'ao': 2, 'ou': 2, 'iu': 2, 'd': 2, 't': 2, 'n': 2, 'l': 2, # Tip
    'an': 3, 'en': 3, 'in': 3, 'un': 3, 'ün': 3, 'g': 3, 'k': 3, 'h': 3, # Root
    'ang': 4, 'eng': 4, 'ing': 4, 'ong': 4, 'z': 4, 'c': 4, 's': 4, 'zh': 4, 'ch': 4, 'sh': 4, 'r': 4, # Teeth/Curl
    'y': 5, 'w': 5, 'j': 5, 'q': 5, 'x': 5, # Magic
    # Complex finals
    'ia': 5, 'ie': 5, 'iao': 5, 'ian': 5, 'iang': 5, 'iong': 5,
    'ua': 5, 'uo': 5, 'uai': 5, 'uan': 5, 'uang': 5,
    'ue': 5, 'üe': 5, 'üan': 5 # 've' -> 'üe', 'van' -> 'üan'
}

STANDARD_FINALS = [
    'a', 'o', 'e', 'i', 'u', 'ü',
    'ai', 'ei', 'ui', 'ao', 'ou', 'iu', 'ie', 'üe', 'er',
    'an', 'en', 'in', 'un', 'ün',
    'ang', 'eng', 'ing', 'ong',
    'ia', 'ua', 'uo', 'uai', 'uan', 'uang', 'ue', 'iang', 'iong', 'iao', 'ian', 'üan'
]

def normalize_pinyin(text):
    """
    Converts input hacks (v) to proper Pinyin (ü).
    e.g. 'lv' -> 'lü', 'nv' -> 'nü', 've' -> 'üe'
    """
    if not text:
        return text
    return text.replace('v', 'ü')

# Configuration
APKG_PATH = project_root / "data" / "pinyin_sample_deck" / "Pinyin_Sample_Deck.apkg"
OUTPUT_CSV = project_root / "data" / "pinyin_deck_patched.csv"

# Stage names for tagging
STAGE_NAMES = {
    1: "Stage1_Lips",
    2: "Stage2_Tip",
    3: "Stage3_Root",
    4: "Stage4_TeethCurl",
    5: "Stage5_Magic"
}


def normalize_text_with_media(text: str) -> str:
    """
    Normalize pinyin in text while preserving media tags.
    Media tags: [sound:...] and <img src...>
    """
    if not text:
        return text
    
    # Extract media tags to preserve them
    media_tags = []
    
    # Find all [sound:...] tags
    sound_pattern = r'\[sound:([^\]]+)\]'
    sounds = re.findall(sound_pattern, text)
    for sound in sounds:
        placeholder = f"__SOUND_{len(media_tags)}__"
        media_tags.append(('[sound:', sound, ']'))
        text = text.replace(f'[sound:{sound}]', placeholder)
    
    # Find all <img src="..."> tags
    img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
    imgs = re.findall(img_pattern, text)
    for img in imgs:
        placeholder = f"__IMG_{len(media_tags)}__"
        img_tag = re.search(f'<img[^>]*src=["\']{re.escape(img)}["\'][^>]*>', text).group(0)
        media_tags.append((img_tag.split('src=')[0] + 'src="', img, '">'))
        text = text.replace(img_tag, placeholder)
    
    # Normalize pinyin in the text
    text = normalize_pinyin(text)
    
    # Restore media tags
    for i, (prefix, content, suffix) in enumerate(media_tags):
        placeholder = f"__SOUND_{i}__" if '[sound:' in prefix else f"__IMG_{i}__"
        # Normalize content if it's a filename (might contain v -> ü)
        normalized_content = normalize_pinyin(content)
        restored = prefix + normalized_content + suffix
        text = text.replace(placeholder, restored)
    
    return text


def get_stage_tag(element: str) -> str:
    """Get stage tag for an element based on STAGE_ORDER"""
    normalized = normalize_pinyin(element)
    stage = STAGE_ORDER.get(normalized, 99)
    return STAGE_NAMES.get(stage, "Stage_Unknown")


def extract_notes_from_apkg(apkg_path: Path) -> Tuple[List[Dict], List[Dict]]:
    """Extract element and syllable notes from apkg file"""
    element_notes = []
    syllable_notes = []
    
    with zipfile.ZipFile(apkg_path, 'r') as z:
        # Extract database to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.anki21') as tmp_db:
            tmp_db.write(z.read('collection.anki21'))
            tmp_db_path = tmp_db.name
        
        try:
            # Connect to database
            conn = sqlite3.connect(tmp_db_path)
            cursor = conn.cursor()
            
            # Get note models
            cursor.execute("SELECT models FROM col")
            col_data = cursor.fetchone()
            models = json.loads(col_data[0]) if col_data else {}
            
            # Get all notes ordered by ID (to maintain deck order)
            cursor.execute("SELECT id, mid, flds, tags FROM notes ORDER BY id")
            all_notes = cursor.fetchall()
            
            for note_id, mid, flds, tags in all_notes:
                fields = flds.split('\x1f')
                note_tags = tags.split(' ') if tags else []
                
                # Get model to understand field structure
                model = models.get(str(mid), {})
                model_name = model.get('name', '')
                field_names = [f.get('name', f'Field{i}') for i, f in enumerate(model.get('flds', []))]
                
                # Build fields dictionary
                note_fields = {}
                for i, field_value in enumerate(fields):
                    field_name = field_names[i] if i < len(field_names) else f'Field{i}'
                    # Normalize pinyin while preserving media tags
                    if field_value and isinstance(field_value, str):
                        note_fields[field_name] = normalize_text_with_media(field_value)
                    else:
                        note_fields[field_name] = field_value or ""
                
                # Determine note type and extract data
                if model_name == "CUMA - Pinyin Element":
                    element = note_fields.get('Element', '').strip()
                    if not element:
                        continue
                    
                    element_notes.append({
                        'note_id': str(note_id),
                        'element': normalize_pinyin(element),
                        'fields': note_fields,
                        'tags': list(note_tags)
                    })
                
                elif model_name == "CUMA - Pinyin Syllable":
                    syllable = note_fields.get('Syllable', '').strip()
                    if not syllable:
                        syllable = note_fields.get('Pinyin', '').strip()
                    if not syllable:
                        continue
                    
                    # Extract element to learn
                    element_to_learn = note_fields.get('ElementToLearn', '').strip()
                    
                    syllable_notes.append({
                        'note_id': str(note_id),
                        'syllable': normalize_pinyin(syllable),
                        'element_to_learn': normalize_pinyin(element_to_learn) if element_to_learn else '',
                        'fields': note_fields,
                        'tags': list(note_tags)
                    })
            
            conn.close()
        finally:
            os.unlink(tmp_db_path)
    
    print(f"✅ Extracted {len(element_notes)} element notes and {len(syllable_notes)} syllable notes")
    return element_notes, syllable_notes


def strip_tone_marks(pinyin: str) -> str:
    """Remove tone marks from pinyin to get base syllable"""
    tone_replacements = {
        'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
        'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
        'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
        'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
        'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
        'ǖ': 'ü', 'ǘ': 'ü', 'ǚ': 'ü', 'ǜ': 'ü'
    }
    result = pinyin
    for tone, base in tone_replacements.items():
        result = result.replace(tone, base)
    return result


def normalize_syllable_spelling(syllable: str) -> str:
    """
    Normalize syllable spelling to standard pinyin form.
    Rules:
    - b/p/m/f + uo -> bo/po/mo/fo (not buo/puo/muo/fuo)
    - j/q/x + ü -> ju/qu/xu (not jü/qü/xü)
    - j/q/x + üe -> jue/que/xue (not jüe/qüe/xüe)
    - j/q/x + üan -> juan/quan/xuan (not jüan/qüan/xüan)
    - j/q/x + ün -> jun/qun/xun (not jün/qün/xün)
    - y + ü -> yu (not yü)
    - y + üe -> yue (not yüe)
    - y + üan -> yuan (not yüan)
    - y + ün -> yun (not yün)
    """
    if not syllable or len(syllable) < 2:
        return syllable
    
    # Handle bo/po/mo/fo special case
    if syllable in ['buo', 'puo', 'muo', 'fuo']:
        return syllable[0] + 'o'  # buo -> bo, etc.
    
    # Handle j/q/x + ü cases
    if syllable[0] in ['j', 'q', 'x']:
        # Replace ü with u after j/q/x
        normalized = syllable.replace('ü', 'u')
        return normalized
    
    # Handle y + ü cases
    if syllable.startswith('y') and 'ü' in syllable:
        normalized = syllable.replace('ü', 'u')
        return normalized
    
    return syllable


def _is_valid_pinyin_syllable_old(initial: str, final: str) -> bool:
    """
    Validate if an initial-final combination is a valid pinyin syllable.
    Based on Standard Chinese pinyin table rules from Wikipedia.
    Reference: https://en.wikipedia.org/wiki/Pinyin_table
    
    Returns True if the combination is valid in Standard Chinese.
    """
    # Handle standalone finals (no initial)
    if not initial or initial == '∅':
        # Valid standalone finals: a, o, e, ai, ei, ao, ou, an, en, ang, eng, er
        valid_standalone = {'a', 'o', 'e', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'er'}
        return final in valid_standalone
    
    # Special rules for j, q, x: can only combine with i or ü (or finals starting with i/ü)
    if initial in ['j', 'q', 'x']:
        # j, q, x can combine with:
        # - i, ia, iao, ian, iang, ie, iu, in, ing, iong
        # - ü, üe, üan, ün (written as u after j/q/x)
        valid_finals = {'i', 'ia', 'iao', 'ian', 'iang', 'ie', 'iu', 'in', 'ing', 'iong',
                       'ü', 'üe', 'üan', 'ün', 'ue', 'uan', 'un'}  # u variants after j/q/x
        return final in valid_finals or final.startswith('i') or final.startswith('ü')
    
    # Special rules for zh, ch, sh, r: cannot combine with i
    if initial in ['zh', 'ch', 'sh', 'r']:
        # zh, ch, sh, r cannot combine with i (they combine with -i instead, like zhi, chi, shi, ri)
        # Also can't combine with ü
        if final == 'i' or final.startswith('ü'):
            return False
        # But they can combine with most other finals
        return True
    
    # Special rules for z, c, s: cannot combine with i (except -i for zi, ci, si)
    if initial in ['z', 'c', 's']:
        # z, c, s combine with -i (special -i sound) for zi, ci, si
        # But regular i combinations are not standard
        if final == 'i':
            return True  # zi, ci, si are valid
        if final.startswith('ü') or final.startswith('i') and final != 'i':
            return False
        return True
    
    # Special rules for b, p, m, f
    if initial in ['b', 'p', 'm', 'f']:
        # b, p, m, f cannot combine with u (except for some rare cases)
        # They combine with o instead: bo, po, mo, fo
        if final == 'u':
            return False  # bu, pu, mu, fu are not standard (use bo, po, mo, fo)
        # They also cannot combine with ü
        if final.startswith('ü'):
            return False
        # b, p, m, f cannot combine with e (except me for 麼/么)
        if final == 'e' and initial != 'm':
            return False  # be, pe, fe are not standard
        # b, p, m, f cannot combine with ui, ou, er
        if final in ['ui', 'ou', 'er']:
            return False  # bui, pou, ber are not standard
        return True
    
    # Special rules for g, k, h
    if initial in ['g', 'k', 'h']:
        # g, k, h cannot combine with i or ü
        # But ge, ke, he are valid (e is not i)
        if final.startswith('i') or final.startswith('ü') or final == 'ia' or final == 'iao' or final == 'ian' or final == 'iang' or final == 'ie' or final == 'iu' or final == 'in' or final == 'ing' or final == 'iong':
            return False
        return True
    
    # Special rules for d, t
    if initial in ['d', 't']:
        # d, t cannot combine with ü
        if final.startswith('ü'):
            return False
        return True
    
    # Special rules for n, l
    if initial in ['n', 'l']:
        # n, l can combine with ü (nü, lü, nüe, lüe, nüan, lüan, nün, lün)
        # But some combinations are rare or non-standard
        return True
    
    # Rules for standalone vowels as "initials"
    if initial in ['a', 'o', 'e']:
        # These are finals, not initials - only valid if final matches
        return initial == final
    
    # y and w are used for no-initial syllables starting with i/u/ü
    # They're not real initials, so we handle them separately
    if initial in ['y', 'w']:
        # y is used for syllables starting with i or ü: yi, ya, yao, yan, yang, ye, you, yin, ying, yong
        # w is used for syllables starting with u: wu, wa, wo, wai, wei, wan, wen, wang, weng
        if initial == 'y':
            valid_y_finals = {'i', 'ia', 'iao', 'ian', 'iang', 'ie', 'iu', 'in', 'ing', 'iong',
                            'ü', 'üe', 'üan', 'ün'}
            return final in valid_y_finals
        elif initial == 'w':
            valid_w_finals = {'u', 'ua', 'uo', 'uai', 'ui', 'uan', 'un', 'uang', 'eng'}  # weng
            return final in valid_w_finals
    
    # Default: allow the combination
    # Most initial-final combinations are valid if they pass the above checks
    return True


def find_missing_combinations(element_notes: List[Dict], syllable_notes: List[Dict]) -> List[Dict]:
    """
    Find missing syllable combinations using fill_missing_combinations logic.
    Returns list of placeholder notes with Status::Missing tag.
    """
    # Build set of existing syllables
    existing_syllables = set()
    
    # Add elements (standalone)
    for note in element_notes:
        element = note['element']
        existing_syllables.add(element)
    
    # Add syllables from syllable notes
    for note in syllable_notes:
        syllable = strip_tone_marks(note['syllable'])
        existing_syllables.add(syllable)
    
    # Generate initials list from STAGE_ORDER
    initials = [k for k, v in STAGE_ORDER.items() if len(k) <= 2 and k not in STANDARD_FINALS]
    initials += ['a', 'o', 'e']
    
    # Track which element groups exist
    element_groups = {note['element'] for note in element_notes}
    
    missing_notes = []
    
    for init in initials:
        if init not in element_groups:
            continue
        
        for fin in STANDARD_FINALS:
            # Build the syllable
            if init in ['a', 'o', 'e']:
                syllable = init
                if fin != init:
                    continue
            else:
                syllable = init + fin
            
            # Normalize to standard spelling (bo not buo, ju not jü, etc.)
            syllable = normalize_syllable_spelling(syllable)
            
            # Check if this syllable is valid using the complete pinyin table
            if not check_valid_syllable(syllable):
                continue
            
            # Check if this combination exists
            if syllable not in existing_syllables:
                # Create placeholder syllable note
                placeholder_note = {
                    'note_id': f'missing_{init}_{fin}',
                    'syllable': syllable,
                    'element_to_learn': fin if init in ['a', 'o', 'e'] else init,
                    'fields': {
                        'ElementToLearn': fin if init in ['a', 'o', 'e'] else init,
                        'Syllable': syllable,
                        'WordPinyin': f'{syllable} [MISSING]',
                        'WordHanzi': '[缺失]',
                        'WordPicture': '[MISSING]',
                        '_Remarks': 'Auto-generated Missing Combo',
                        '_KG_Map': '{}'
                    },
                    'tags': ['Status::Missing', get_stage_tag(init if init not in ['a', 'o', 'e'] else fin)]
                }
                missing_notes.append(placeholder_note)
                existing_syllables.add(syllable)  # Avoid duplicates
    
    print(f"✅ Found {len(missing_notes)} missing combinations")
    return missing_notes


def write_csv_output(
    element_notes: List[Dict],
    syllable_notes: List[Dict],
    missing_notes: List[Dict],
    output_path: Path
):
    """
    Write all notes to CSV file in Anki import format.
    Format: Type, Fields..., Tags
    """
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        
        # Write header (Anki CSV format: #separator:tab)
        writer.writerow(['#separator:tab'])
        writer.writerow(['#html:true'])
        
        # Element note fields
        element_field_names = [
            'Element', 'ExampleChar', 'Picture', 'Tone1', 'Tone2', 'Tone3', 'Tone4',
            '_Remarks', '_KG_Map'
        ]
        
        # Syllable note fields
        syllable_field_names = [
            'ElementToLearn', 'Syllable', 'WordPinyin', 'WordHanzi', 'WordPicture',
            '_Remarks', '_KG_Map'
        ]
        
        # Write element notes
        for note in element_notes:
            fields = note['fields']
            tags = note['tags'].copy()
            
            # Add stage tag
            stage_tag = get_stage_tag(note['element'])
            if stage_tag not in tags:
                tags.append(stage_tag)
            
            # Build row: Type, Fields..., Tags
            row = ['Element']  # Note type indicator
            for field_name in element_field_names:
                row.append(fields.get(field_name, ''))
            row.append(' '.join(tags))
            writer.writerow(row)
        
        # Write syllable notes (existing)
        for note in syllable_notes:
            fields = note['fields']
            tags = note['tags'].copy()
            
            # Add stage tag based on element to learn
            if note['element_to_learn']:
                stage_tag = get_stage_tag(note['element_to_learn'])
                if stage_tag not in tags:
                    tags.append(stage_tag)
            
            # Build row: Type, Fields..., Tags
            row = ['Syllable']
            for field_name in syllable_field_names:
                row.append(fields.get(field_name, ''))
            row.append(' '.join(tags))
            writer.writerow(row)
        
        # Write missing placeholder notes
        for note in missing_notes:
            fields = note['fields']
            tags = note['tags']
            
            # Build row: Type, Fields..., Tags
            row = ['Syllable']
            for field_name in syllable_field_names:
                row.append(fields.get(field_name, ''))
            row.append(' '.join(tags))
            writer.writerow(row)
    
    print(f"✅ Wrote {len(element_notes) + len(syllable_notes) + len(missing_notes)} notes to {output_path}")


def main():
    """Main processing function"""
    print("=" * 80)
    print("Patch Anki Deck with Pinyin Curriculum Logic")
    print("=" * 80)
    
    if not APKG_PATH.exists():
        print(f"❌ Error: APKG file not found at {APKG_PATH}")
        return
    
    # Extract notes from apkg
    print("\n1. Extracting notes from apkg...")
    element_notes, syllable_notes = extract_notes_from_apkg(APKG_PATH)
    
    # Assign stage tags to existing notes
    print("\n2. Normalizing pinyin and assigning stage tags...")
    # Normalization already done in extract_notes_from_apkg
    # Tags will be added during CSV writing
    
    # Find missing combinations
    print("\n3. Finding missing combinations...")
    missing_notes = find_missing_combinations(element_notes, syllable_notes)
    
    # Write output CSV
    print("\n4. Writing patched CSV...")
    output_path = Path(OUTPUT_CSV)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv_output(element_notes, syllable_notes, missing_notes, output_path)
    
    print("\n" + "=" * 80)
    print("✅ Patching complete!")
    print(f"   - Element notes: {len(element_notes)}")
    print(f"   - Syllable notes: {len(syllable_notes)}")
    print(f"   - Missing placeholders: {len(missing_notes)}")
    print(f"   - Output: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()

