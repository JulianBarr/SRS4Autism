#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find Best Words for Missing Pinyin Syllables

This script:
1. Reads pinyin_deck_patched.csv to find syllables marked [MISSING]
2. Queries the Knowledge Graph (world_model.ttl) to find candidate words
3. Ranks candidates by concreteness, AoA, HSK level, frequency, and image availability
4. Outputs suggestions for filling the missing syllables
"""

import csv
import rdflib
from rdflib.namespace import RDF, RDFS
import pandas as pd
import re
import os
import sys
from pathlib import Path

# Add project root to path for importing CEDICT loader
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from scripts.knowledge_graph.load_cc_cedict import (
    find_cedict_file,
    load_cedict_file,
    get_english_translations
)

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl"
INPUT_CSV = PROJECT_ROOT / "data" / "pinyin_deck_patched.csv"
OUTPUT_REPORT = PROJECT_ROOT / "data" / "pinyin_gap_fill_suggestions.csv"
ALL_PICS_FILE = PROJECT_ROOT / "data" / "content_db" / "all_pics.dat"

# Namespaces
SRS_KG = rdflib.Namespace("http://srs4autism.com/schema/")

# Tone mapping for normalization (ü -> v for easier matching)
TONE_MAP = {
    'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
    'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
    'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
    'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
    'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
    'ǖ': 'ü', 'ǘ': 'ü', 'ǚ': 'ü', 'ǜ': 'ü',
    'ü': 'ü',  # Keep ü as is for matching
}

# Special mappings: normalize j/q/x + ü to u, y + ü to yu
SPECIAL_NORMALIZATIONS = {
    'ju': 'jü', 'jue': 'jüe', 'juan': 'jüan', 'jun': 'jün',
    'qu': 'qü', 'que': 'qüe', 'quan': 'qüan', 'qun': 'qün',
    'xu': 'xü', 'xue': 'xüe', 'xuan': 'xüan', 'xun': 'xün',
    'yu': 'yü', 'yue': 'yüe', 'yuan': 'yüan', 'yun': 'yün',
}


def clean_pinyin(pinyin: str) -> str:
    """
    Normalize pinyin by removing tone marks and tone numbers.
    Returns the base syllable for matching.
    """
    s = pinyin.lower()
    # Remove tone marks
    for tone_char, base in TONE_MAP.items():
        s = s.replace(tone_char, base)
    # Remove tone numbers
    s = re.sub(r'[1-5]', '', s)
    return s.strip()


def normalize_syllable_for_query(syllable: str) -> str:
    """
    Normalize syllable to match KG format.
    Handles special cases like bo=buo, ju=jü, etc.
    """
    syllable_clean = clean_pinyin(syllable)
    # Reverse special normalizations for query
    for standard, canonical in SPECIAL_NORMALIZATIONS.items():
        if syllable_clean == standard:
            return canonical
    return syllable_clean


def load_knowledge_graph():
    """Load the Knowledge Graph from Turtle file."""
    if not KG_FILE.exists():
        print(f"Error: Knowledge Graph file not found at {KG_FILE}")
        return None
    print(f"Loading Knowledge Graph from {KG_FILE}... (This might take a moment)")
    g = rdflib.Graph()
    g.parse(str(KG_FILE), format="turtle")
    print(f"Loaded {len(g)} triples.")
    return g


def get_missing_syllables():
    """Read the patched CSV and find syllables marked [MISSING]."""
    missing = []
    if not INPUT_CSV.exists():
        print(f"Error: {INPUT_CSV} not found.")
        return []
    
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        try:
            next(reader)  # Skip #separator:tab
            next(reader)  # Skip #html:true
        except StopIteration:
            return []
        
        for row in reader:
            if len(row) < 3:
                continue
            
            # Check if status is Missing
            row_str = "\t".join(row)
            if "Status::Missing" in row_str or "[MISSING]" in row_str:
                # Column 2 (index 2) is the Syllable field
                syllable = row[2].strip()
                if syllable and syllable != "[MISSING]":
                    missing.append(syllable)
    
    return sorted(list(set(missing)))  # Deduplicate and sort


def load_all_pics_map():
    """Load image mapping from all_pics.dat file."""
    pics_map = {}
    if not ALL_PICS_FILE.exists():
        print(f"   ⚠️  Warning: {ALL_PICS_FILE} not found. Image checking will be limited.")
        return pics_map
    
    try:
        with open(ALL_PICS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(None, 1)  # Split on whitespace, max 2 parts
                if len(parts) >= 2:
                    word = parts[0].strip().lower()  # Normalize to lowercase for matching
                    image_file = parts[1].strip()
                    pics_map[word] = image_file
        print(f"   ✅ Loaded {len(pics_map)} image mappings from all_pics.dat")
    except Exception as e:
        print(f"   ⚠️  Error loading all_pics.dat: {e}")
    
    return pics_map


def load_cedict_data():
    """Load CC-CEDICT dictionary for Chinese-to-English translation."""
    cedict_file = find_cedict_file()
    if not cedict_file:
        print(f"   ⚠️  Warning: CC-CEDICT file not found. Image matching via translations will be limited.")
        return None
    
    try:
        print(f"   Loading CC-CEDICT from {cedict_file}...", end=" ")
        cedict_data = load_cedict_file(cedict_file)
        print(f"✅ Loaded")
        return cedict_data
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def check_image_via_cedict(chinese_word: str, cedict_data: dict, pics_map: dict) -> tuple:
    """
    Check if a Chinese word has an image by translating it via CEDICT and matching against all_pics.dat.
    
    Returns: (has_image: bool, image_file: str)
    """
    if not cedict_data or not chinese_word:
        return (False, "")
    
    # Common stop words and abstract/generic words that are likely false positives
    # These are function words and abstract concepts that shouldn't match concrete images
    STOP_WORDS = {
        # Function words (prepositions, articles, etc.)
        'a', 'an', 'the', 'on', 'in', 'at', 'to', 'for', 'of', 'with', 'by',
        'from', 'up', 'about', 'into', 'through', 'during', 'including',
        'against', 'among', 'throughout', 'despite', 'towards', 'upon',
        'concerning', 'over', 'under', 'below', 'above', 'across', 'around',
        # Abstract/generic words that often appear in translations but aren't concrete
        'what', 'that', 'this', 'which', 'who', 'where', 'when', 'why', 'how',
        'way', 'thing', 'one', 'some', 'any', 'all', 'each', 'every', 'both',
        'other', 'another', 'such', 'same', 'different', 'same', 'very',
        'more', 'most', 'less', 'least', 'much', 'many', 'few', 'little',
        'seems', 'seem', 'apparently', 'deliberately', 'purpose', 'intentionally'
    }
    
    # Get English translations from CEDICT
    english_translations = get_english_translations(cedict_data, chinese_word)
    
    # Check if any English translation matches a key in all_pics.dat
    for translation in english_translations:
        # Normalize translation: lowercase, remove punctuation
        translation_clean = translation.lower().strip()
        # Remove common punctuation but keep spaces for phrase matching
        translation_clean = re.sub(r'[^\w\s]', '', translation_clean)
        
        # Skip if translation is empty or just whitespace
        if not translation_clean:
            continue
        
        # Split into words to check
        words = translation_clean.split()
        
        # PRIORITY 1: Try exact phrase match first (most reliable)
        # BUT skip if it's a single stop word (likely false positive)
        if len(words) == 1 and words[0] in STOP_WORDS:
            continue  # Skip single-word stop words
        if translation_clean in pics_map:
            return (True, pics_map[translation_clean])
        
        # PRIORITY 2: Try exact phrase match with underscores (some entries use underscores)
        translation_underscore = translation_clean.replace(' ', '_')
        if translation_underscore in pics_map:
            return (True, pics_map[translation_underscore])
    
        # PRIORITY 3: For multi-word phrases, only match meaningful words (not stop words)
        # Only split if it's a 2-3 word phrase (longer phrases are less likely to match)
        if len(words) <= 3:
            for word in words:
                # Skip stop words and very short words (likely false positives)
                if len(word) < 3 or word in STOP_WORDS:
                    continue
                if word in pics_map:
                    return (True, pics_map[word])
        # For longer phrases (4+ words), don't split - they're likely abstract and won't match
    
    return (False, "")


def load_all_words(g: rdflib.Graph):
    """
    Pre-load all words with pinyin into memory for fast filtering.
    This is much faster than running individual SPARQL queries.
    Only loads words with HSK 1-6.
    """
    print("   Loading all words from Knowledge Graph (HSK 1-6 only)...", end=" ")
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT ?word ?text ?pinyin ?freq ?hsk ?image ?concreteness ?aoa
    WHERE {
        ?word a srs-kg:Word .
        ?word srs-kg:text ?text .
        ?word srs-kg:pinyin ?pinyin .
        ?word srs-kg:hskLevel ?hsk .
        OPTIONAL { ?word srs-kg:frequencyRank ?freq } .
        OPTIONAL { ?word srs-kg:imageFileName ?image } .
        OPTIONAL { ?word srs-kg:concreteness ?concreteness } .
        OPTIONAL { ?word srs-kg:ageOfAcquisition ?aoa } .
        FILTER (?hsk >= 1 && ?hsk <= 6)
    }
    """
    
    all_words = []
    try:
        results = g.query(query, initNs={'srs-kg': SRS_KG, 'rdf': RDF})
        for row in results:
            all_words.append({
                'text': str(row.text),
                'pinyin_raw': str(row.pinyin),
                'freq': float(row.freq) if row.freq else 99999.0,
                'hsk': int(row.hsk) if row.hsk else 99,
                'has_image': bool(row.image),
                'image_file': str(row.image) if row.image else "",
                'concreteness': float(row.concreteness) if row.concreteness else 0.0,
                'aoa': float(row.aoa) if row.aoa else 99.0,
            })
        print(f"✅ Loaded {len(all_words)} words")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    return all_words


def find_best_candidate(all_words: list, target_syllable: str, pics_map: dict, cedict_data: dict):
    """
    Find best candidate word from pre-loaded list.
    Uses EXACT matching only (no partial matching).
    Rank candidates by:
    - Concreteness (highest priority, higher = better)
    - Image availability (huge bonus)
    - HSK Level (lower = better, prioritize 1-3)
    - Age of Acquisition (lower = better, learned earlier)
    - Frequency Rank (only as tiebreaker, lower = better)
    - Word length (shorter = better for pinyin examples)
    """
    target_normalized = normalize_syllable_for_query(target_syllable)
    target_clean = clean_pinyin(target_syllable)
    
    candidates = []
    
    for word_data in all_words:
        text = word_data['text']
        pinyin_raw = word_data['pinyin_raw']
            # Normalize and check if word actually contains the target syllable
            cleaned_pinyin = clean_pinyin(pinyin_raw)
            # Split by space for multi-syllable words
            syllables = cleaned_pinyin.split()
                # EXACT MATCHING ONLY - no partial matching
        # Check if target syllable exactly matches one of the syllables
                found = False
        syllable_position = -1  # Track position of matching syllable
        for i, syl in enumerate(syllables):
            if syl == target_clean or syl == target_normalized:
                        found = True
                syllable_position = i  # 0 = first syllable, 1 = second, etc.
                        break
        
                if not found:
                    continue
                # Extract fields
        freq = word_data['freq']
        hsk = word_data['hsk']
        concreteness = word_data['concreteness']
        aoa = word_data['aoa']
                # Check image availability from multiple sources
        has_image_from_kg = word_data['has_image']
        image_file_from_kg = word_data['image_file']
                # Check direct Chinese word match in all_pics.dat
        has_image_from_pics_direct = text.lower() in pics_map
        image_file_from_pics_direct = pics_map.get(text.lower(), "")
                # Check via CEDICT translation (Chinese -> English -> all_pics.dat)
        has_image_from_cedict, image_file_from_cedict = check_image_via_cedict(text, cedict_data, pics_map)
                # Use best available image source (priority: direct match > CEDICT > KG)
        has_image = has_image_from_pics_direct or has_image_from_cedict or has_image_from_kg
        if has_image_from_pics_direct:
            image_file = image_file_from_pics_direct
        elif has_image_from_cedict:
            image_file = image_file_from_cedict
        else:
            image_file = image_file_from_kg
            # Scoring: lower score = better
            score = 0
                # PRIORITY 1: Concreteness (highest weight, higher = better)
        # Scale 1-5, so subtract (5 - concreteness) * 500
        # This gives concreteness 5 = -2000 points, concreteness 1 = 0 points
        if concreteness > 0:
            score -= (5 - concreteness) * 500
        else:
        # Penalty for missing concreteness data
            score += 1000
                # PRIORITY 2: Image availability (huge bonus)
            if has_image:
            score -= 1500
                # PRIORITY 3: HSK: lower is better (HSK 1 = 0 points, HSK 6 = 500 points)
        score += (hsk - 1) * 100
                # PRIORITY 4: AoA: lower is better (learned earlier)
        # Subtract points for early acquisition (e.g., AoA 3 = -120 points)
            if aoa < 99:
                score -= (15 - aoa) * 10  # Early words (AoA 3-7) get big bonus
        else:
        # Small penalty for missing AoA
            score += 50
                # PRIORITY 5: Frequency: only as tiebreaker (lower rank = better, more frequent)
        # Much smaller weight than concreteness
        score += freq / 10000
            # Word length: prefer shorter words for pinyin examples
        score += len(text) * 2
            # Prefer single-syllable words (best for pinyin learning)
            if len(syllables) == 1:
            score -= 100
                # PRIORITY: Prefer words where target syllable is FIRST (most prominent for learning)
        if syllable_position == 0:
            score -= 200  # Big bonus for first syllable position
        elif syllable_position > 0:
            score += syllable_position * 50  # Small penalty for later positions
            
            candidates.append({
                'word': text,
                'pinyin': pinyin_raw,
                'score': score,
                'hsk': hsk,
                'freq': freq,
                'has_image': has_image,
                'image_file': image_file,
                'concreteness': concreteness,
                'aoa': aoa,
                'num_syllables': len(syllables)
            })
    
    # Sort by score (ascending = best first)
    candidates.sort(key=lambda x: x['score'])
    
    if candidates:
        return candidates[0]
    return None


def main():
    """Main execution function."""
    print("=" * 80)
    print("Find Best Words for Missing Pinyin Syllables")
    print("=" * 80)
    
    # Load knowledge graph
    g = load_knowledge_graph()
    if not g:
        return
    
    # Get missing syllables
    print(f"\n1. Reading missing syllables from {INPUT_CSV}...")
    missing_syllables = get_missing_syllables()
    print(f"   Found {len(missing_syllables)} missing syllables.")
    
    if not missing_syllables:
        print("   No missing syllables found. Exiting.")
        return
    
    # Load image mapping from all_pics.dat
    print(f"\n2. Loading image mappings from all_pics.dat...")
    pics_map = load_all_pics_map()
    
    # Load CC-CEDICT for Chinese-to-English translation
    print(f"\n3. Loading CC-CEDICT dictionary...")
    cedict_data = load_cedict_data()
    
    # Pre-load all words into memory (much faster than individual queries)
    print(f"\n4. Pre-loading all words from Knowledge Graph (HSK 1-6 only)...")
    all_words = load_all_words(g)
    if not all_words:
        print("   ❌ Failed to load words. Exiting.")
        return
    
    # Find best candidates
    print(f"\n5. Searching for best candidates (exact matching, prioritizing concreteness)...")
    suggestions = []
    
    for i, syllable in enumerate(missing_syllables, 1):
        print(f"   [{i}/{len(missing_syllables)}] Searching for: {syllable}...", end=" ")
        best = find_best_candidate(all_words, syllable, pics_map, cedict_data)
        
        if best:
            print(f"✅ {best['word']} ({best['pinyin']}) [HSK {best['hsk']}, AoA {best['aoa']:.1f}]")
            suggestions.append({
                'Syllable': syllable,
                'Suggested Word': best['word'],
                'Word Pinyin': best['pinyin'],
                'HSK Level': best['hsk'] if best['hsk'] < 99 else '-',
                'Frequency Rank': int(best['freq']) if best['freq'] < 99999 else '-',
                'Has Image': 'Yes' if best['has_image'] else 'No',
                'Image File': best['image_file'],
                'Concreteness': f"{best['concreteness']:.2f}" if best['concreteness'] > 0 else '-',
                'AoA': f"{best['aoa']:.1f}" if best['aoa'] < 99 else '-',
                'Num Syllables': best['num_syllables'],
                'Score': f"{best['score']:.2f}"
            })
        else:
            print("❌ No candidate found")
            suggestions.append({
                'Syllable': syllable,
                'Suggested Word': 'NONE',
                'Word Pinyin': '-',
                'HSK Level': '-',
                'Frequency Rank': '-',
                'Has Image': 'No',
                'Image File': '',
                'Concreteness': '-',
                'AoA': '-',
                'Num Syllables': '-',
                'Score': '-'
            })
    
    # Save report
    print(f"\n6. Saving suggestions to {OUTPUT_REPORT}...")
    df = pd.DataFrame(suggestions)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_REPORT, index=False, encoding='utf-8')
    
    found_count = sum(1 for s in suggestions if s['Suggested Word'] != 'NONE')
    print(f"   ✅ Saved {len(suggestions)} suggestions ({found_count} found, {len(suggestions) - found_count} not found)")
    
    print("\n" + "=" * 80)
    print("✅ Complete!")
    print(f"   Report: {OUTPUT_REPORT}")
    print("=" * 80)


if __name__ == "__main__":
    main()
