#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Match pending pinyin syllables with English vocabulary from Anki decks.
Use Google Translate for English-to-Chinese translation, then match to syllables.
Prioritize by concreteness.
Save results to JSON for the API to serve.
"""

import sys
import sqlite3
import json
import zipfile
import tempfile
from pathlib import Path
from collections import defaultdict
import re
import csv
import time

# Google Translate (free library)
try:
    from googletrans import Translator
    GOOGLE_TRANSLATE_AVAILABLE = True
except ImportError:
    GOOGLE_TRANSLATE_AVAILABLE = False
    print("⚠️  googletrans not available, install with: pip install googletrans==4.0.0rc1")

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

PROJECT_ROOT = project_root
CEDICT_FILE = PROJECT_ROOT / "data" / "content_db" / "cedict_1_0_ts_utf-8_mdbg.txt"
CONCRETENESS_FILE = PROJECT_ROOT / "data" / "content_db" / "Concreteness_ratings_Brysbaert_et_al_BRM.txt"
APKG_FILES = [
    PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__1. Basic.apkg",
    PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"
]
SUGGESTIONS_FILE = PROJECT_ROOT / "data" / "pinyin_gap_fill_suggestions.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "pending_syllable_english_matches.json"
TRANSLATION_CACHE_FILE = PROJECT_ROOT / "data" / "english_to_chinese_translations.json"


def load_cedict():
    """Load CEDICT dictionary"""
    cedict = defaultdict(list)
    
    if not CEDICT_FILE.exists():
        print(f"⚠️  CEDICT file not found: {CEDICT_FILE}")
        return cedict
    
    print(f"Loading CEDICT from {CEDICT_FILE.name}...")
    line_count = 0
    with open(CEDICT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line_count += 1
            if line_count % 50000 == 0:
                print(f"  Processed {line_count:,} lines...", end='\r', flush=True)
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            
            # CEDICT format: traditional simplified [pinyin] /english1/english2/
            match = re.match(r'(\S+)\s+(\S+)\s+\[(.*?)\]\s+/(.*)', line)
            if match:
                chinese = match.group(2)  # Use simplified
                pinyin = match.group(3)   # Pinyin is in brackets
                english_part = match.group(4)  # English part (may have multiple /separated/values)
                
                # Split by / and clean
                english_words = [e.strip().lower() for e in english_part.split('/') if e.strip()]
                
                for eng in english_words:
                    eng_clean = re.sub(r'\s*\([^)]*\)', '', eng).strip()
                    eng_clean = re.sub(r'\[.*?\]', '', eng_clean).strip()
                    if eng_clean:
                        cedict[eng_clean].append((chinese, pinyin))
    
    print(f"  ✅ Loaded {len(cedict)} English words from CEDICT")
    return cedict


def load_concreteness_ratings():
    """Load concreteness ratings from file"""
    ratings = {}
    
    if not CONCRETENESS_FILE.exists():
        print(f"⚠️  Concreteness file not found: {CONCRETENESS_FILE}")
        return ratings
    
    print(f"Loading concreteness ratings...")
    with open(CONCRETENESS_FILE, 'r', encoding='utf-8') as f:
        next(f)  # Skip header
        line_count = 0
        for line in f:
            line_count += 1
            if line_count % 10000 == 0:
                print(f"  Processed {line_count:,} lines...", end='\r', flush=True)
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                word = parts[0].lower().strip()
                try:
                    rating = float(parts[2])  # Conc.M column
                    ratings[word] = rating
                except (ValueError, IndexError):
                    continue
    
    print(f"  ✅ Loaded {len(ratings)} concreteness ratings")
    return ratings


def extract_english_words_from_apkg(apkg_path: Path):
    """Extract English words from Anki .apkg file"""
    words = set()
    
    if not apkg_path.exists():
        print(f"⚠️  File not found: {apkg_path}")
        return words
    
    print(f"Extracting words from {apkg_path.name}...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract .apkg (it's a zip file)
        with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir_path)
        
        # Open the SQLite database
        db_path = tmpdir_path / "collection.anki21"
        if not db_path.exists():
            db_path = tmpdir_path / "collection.anki2"
        
        if not db_path.exists():
            print(f"  ⚠️  No database found")
            return words
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all notes
        try:
            cursor.execute("SELECT flds FROM notes")
            for row in cursor.fetchall():
                fields = row[0].split('\x1f')  # Anki uses \x1f as field separator
                
                # Try to find English words in all fields
                for field in fields:
                    # Clean HTML
                    field = re.sub(r'<[^>]+>', '', field).strip()
                    field = field.replace('&nbsp;', ' ').strip()
                    
                    # Check if it looks like an English word
                    if field and re.match(r'^[a-zA-Z\s]+$', field):
                        # Split by spaces and take individual words
                        for word in field.split():
                            word = word.lower().strip('.,!?;:"()[]{}')
                            if len(word) > 1 and word.isalpha():
                                words.add(word)
        except Exception as e:
            print(f"  ⚠️  Error reading notes: {e}")
        
        conn.close()
    
    print(f"  ✅ Extracted {len(words)} unique words")
    return words


def normalize_syllable(syllable: str):
    """Normalize syllable for matching (remove tone, lowercase)"""
    return syllable.lower().strip()


def split_pinyin_to_syllables(pinyin: str):
    """Split pinyin string into individual syllables"""
    pinyin = re.sub(r'[1-5]', '', pinyin)
    syllables = []
    for s in pinyin.split():
        s = s.strip()
        # Remove tone marks but keep letters
        s = re.sub(r'[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]', lambda m: {
            'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
            'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
            'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
            'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
            'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
            'ǖ': 'u', 'ǘ': 'u', 'ǚ': 'u', 'ǜ': 'u'
        }.get(m.group(0), m.group(0)), s)
        if s:
            syllables.append(s.lower())
    return syllables


def translate_english_to_chinese(english_word: str, translator=None):
    """Translate English word to Chinese using Google Translate (free library)"""
    if not GOOGLE_TRANSLATE_AVAILABLE or not translator:
        return None
    
    try:
        result = translator.translate(english_word, src='en', dest='zh-cn')
        chinese = result.text.strip()
        return chinese
    except Exception as e:
        print(f"    ⚠️  Translation failed for '{english_word}': {str(e)[:100]}")
        return None


def get_pinyin_for_chinese(chinese_word: str, cedict_dict: dict):
    """Get pinyin for Chinese word from CEDICT"""
    # Search CEDICT for this Chinese word
    for eng, translations in cedict_dict.items():
        for chinese, pinyin in translations:
            if chinese == chinese_word or chinese_word in chinese:
                return pinyin
    return None


def load_translation_cache():
    """Load translation cache from file"""
    cache = {}
    if TRANSLATION_CACHE_FILE.exists():
        try:
            with open(TRANSLATION_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            print(f"  ✅ Loaded {len(cache)} cached translations")
        except Exception as e:
            print(f"  ⚠️  Error loading cache: {e}")
    return cache


def save_translation_cache(cache: dict):
    """Save translation cache to file"""
    try:
        with open(TRANSLATION_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"  ✅ Saved {len(cache)} translations to cache")
    except Exception as e:
        print(f"  ⚠️  Error saving cache: {e}")


def build_syllable_index_with_google_translate(pending_syllables: list, english_words: set, cedict_dict: dict, concreteness_ratings: dict):
    """
    NEW APPROACH using Google Translate:
    1. For each English vocabulary word, translate to Chinese using Google Translate (with caching)
    2. Get pinyin from CEDICT for the Chinese word
    3. Check if pinyin contains any pending syllables
    4. Prioritize by concreteness
    """
    syllable_index = defaultdict(list)
    
    if not GOOGLE_TRANSLATE_AVAILABLE:
        print("❌ Google Translate not available. Install: pip install googletrans==4.0.0rc1")
        return syllable_index
    
    # Initialize Google Translate client
    try:
        translator = Translator()
    except Exception as e:
        print(f"❌ Failed to initialize Google Translate: {e}")
        return syllable_index
    
    # Load translation cache
    print(f"\nLoading translation cache...")
    translation_cache = load_translation_cache()
    cache_hits = 0
    cache_misses = 0
    
    print(f"\nTranslating {len(english_words)} English words to Chinese using Google Translate...")
    print(f"  Then matching to {len(pending_syllables)} pending syllables")
    print()
    
    # Translate each English word and check for syllable matches
    processed = 0
    matches_found = 0
    
    # Sort by concreteness (highest first) to prioritize better matches
    sorted_words = sorted(english_words, key=lambda w: concreteness_ratings.get(w, 0.0), reverse=True)
    
    print(f"  Translating and matching {len(sorted_words)} words...")
    print()
    
    for eng_word in sorted_words:
        concreteness = concreteness_ratings.get(eng_word, 0.0)
        
        # Translate to Chinese (use cache if available)
        if eng_word not in translation_cache:
            print(f"  [{processed+1}/{len(sorted_words)}] Translating '{eng_word}'...")
            sys.stdout.flush()
            chinese = translate_english_to_chinese(eng_word, translator)
            if chinese:
                translation_cache[eng_word] = chinese
                cache_misses += 1
                print(f"    → {chinese}")
                sys.stdout.flush()
                # Small delay to avoid rate limits
                time.sleep(0.2)
            else:
                processed += 1
                continue
        else:
            chinese = translation_cache[eng_word]
            cache_hits += 1
        
        # Get pinyin from CEDICT
        pinyin = get_pinyin_for_chinese(chinese, cedict_dict)
        if not pinyin:
            # If not in CEDICT, skip (we need pinyin to match syllables)
            processed += 1
            continue
        
        # Check if pinyin contains any pending syllables
        pinyin_syllables = split_pinyin_to_syllables(pinyin)
        word_matched = False
        for syllable in pending_syllables:
            syllable_normalized = normalize_syllable(syllable)
            if syllable_normalized in pinyin_syllables:
                syllable_index[syllable_normalized].append({
                    'english': eng_word,
                    'chinese': chinese,
                    'pinyin': pinyin,
                    'matched_syllable': syllable_normalized,
                    'concreteness': concreteness
                })
                if not word_matched:
                    matches_found += 1
                    word_matched = True
        
        processed += 1
        
        # Show progress every 5 words or when matches are found
        if processed % 5 == 0 or word_matched:
            percent = (processed / len(sorted_words)) * 100
            # Print on new line so progress is visible
            print(f"  [{percent:5.1f}%] Processed {processed}/{len(sorted_words)} words, {matches_found} matches found, {cache_hits} cache hits, {cache_misses} new translations")
            sys.stdout.flush()
    
    print()  # New line after progress
    print(f"  ✅ Completed translation: {processed} words processed, {matches_found} total matches")
    print(f"  📊 Cache: {cache_hits} hits, {cache_misses} new translations")
    
    # Save translation cache
    print(f"\nSaving translation cache...")
    save_translation_cache(translation_cache)
    print()
    
    # Sort and limit to top 3 per syllable
    print("  Organizing matches by syllable...")
    for syllable in pending_syllables:
        syllable_normalized = normalize_syllable(syllable)
        candidates = syllable_index.get(syllable_normalized, [])
        candidates.sort(key=lambda x: x.get('concreteness', 0.0), reverse=True)
        syllable_index[syllable_normalized] = candidates[:3]
        
        if candidates:
            print(f"    ✅ {syllable_normalized}: {len(candidates)} matches (top 3 shown)")
        else:
            print(f"    ⚠️  {syllable_normalized}: No matches")
    
    print()
    matched_syllables = len([s for s in syllable_index if syllable_index[s]])
    print(f"  ✅ Built index for {matched_syllables}/{len(pending_syllables)} syllables with matches")
    return syllable_index


def find_chinese_words_for_syllable(syllable: str, syllable_index: dict, limit=3):
    """Find Chinese words for a syllable using pre-built index, prioritized by concreteness"""
    syllable_normalized = normalize_syllable(syllable)
    candidates = syllable_index.get(syllable_normalized, [])
    
    # Remove duplicates based on (chinese, english) combination
    seen_combinations = set()
    unique_candidates = []
    for candidate in candidates:
        key = (candidate['chinese'], candidate['english'])
        if key not in seen_combinations:
            seen_combinations.add(key)
            unique_candidates.append(candidate)
    
    # Sort by concreteness (higher is better, more concrete)
    unique_candidates.sort(key=lambda x: x.get('concreteness', 0.0), reverse=True)
    
    # Return top N
    return unique_candidates[:limit]


def main():
    """Main function"""
    print("=" * 80)
    print("Match Pending Syllables with English Vocabulary")
    print("=" * 80)
    print()
    
    # Load data
    cedict_dict = load_cedict()
    print()
    
    concreteness_ratings = load_concreteness_ratings()
    print()
    
    # Extract English words from .apkg files
    print("Step 3: Extracting English words from vocabulary decks...", flush=True)
    all_english_words = set()
    for apkg_file in APKG_FILES:
        words = extract_english_words_from_apkg(apkg_file)
        all_english_words.update(words)
    print(f"Total unique English words: {len(all_english_words)}", flush=True)
    print(flush=True)
    
    # Get ALL pending syllables (including those with existing words that need to be replaced)
    pending = []
    pending_syllables_list = []
    if SUGGESTIONS_FILE.exists():
        with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                approved_val = row.get('approved', '').strip().lower()
                if not approved_val or approved_val == 'false':
                    syllable = row.get('Syllable', '').strip()
                    word = row.get('Suggested Word', '').strip()
                    if syllable:
                        # Include ALL pending items (even if they have words - we'll find new ones)
                        pending.append({
                            'syllable': syllable,
                            'existing_word': word if word and word != 'NONE' else None,
                            'row': row
                        })
                        if syllable not in pending_syllables_list:
                            pending_syllables_list.append(syllable)
    
    print(f"Step 4: Found {len(pending)} pending items ({len(pending_syllables_list)} unique syllables)", flush=True)
    print(f"  (Including items with existing words that need new suggestions)", flush=True)
    print(flush=True)
    
    # Build syllable index using Google Translate
    syllable_index = build_syllable_index_with_google_translate(
        pending_syllables_list, all_english_words, cedict_dict, concreteness_ratings
    )
    print()
    
    # Extract matches from index (already sorted and limited to top 3)
    matches = {}
    for syllable in pending_syllables_list:
        suggestions = syllable_index.get(normalize_syllable(syllable), [])
        if suggestions:
            matches[syllable] = suggestions
    
    # Save to JSON
    output_data = {
        'matches': matches,
        'total_pending': len(pending),
        'matched': len(matches),
        'generated_at': str(Path(__file__).stat().st_mtime)
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Matched {len(matches)} syllables")
    print(f"   Saved to: {OUTPUT_FILE}")
    print()
    
    # Show summary
    print("Matches found:")
    for syllable, suggestions in sorted(matches.items()):
        print(f"  {syllable}: {len(suggestions)} suggestions")
        for i, sug in enumerate(suggestions, 1):
            conc_str = f" (concreteness: {sug['concreteness']:.2f})" if sug.get('concreteness', 0) > 0 else ""
            print(f"    {i}. {sug['chinese']} ({sug['pinyin']}) - {sug['english']}{conc_str}")
    
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        raise

