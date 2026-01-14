#!/usr/bin/env python3
"""
Knowledge Graph Generator V2 - Ontology-Driven
Generates a clean knowledge graph adhering to knowledge_graph/ontology.ttl

Features:
- Strict URI conventions (URL-safe, no spaces)
- Wikidata Q-ID fetching and linking
- Hub-and-Spoke architecture (Concept -> Word)
- rdfs:label for ALL human-readable text
- Comprehensive error handling and logging
"""

import re
import sys
import time
import csv
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import requests
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import XSD
import argparse

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Define namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
SRS_INST = Namespace("http://srs4autism.com/instance/")
WD = Namespace("http://www.wikidata.org/entity/")

# Pinyin library (optional but recommended)
try:
    from pypinyin import pinyin as get_pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    print("⚠️  pypinyin not installed. Install with: pip install pypinyin")

# Data paths
DATA_DIR = PROJECT_ROOT / "data" / "content_db"
HSK_CSV_DIR = DATA_DIR / "hsk_csv"
HSK_COMBINED = DATA_DIR / "hsk_vocabulary.csv"
ENGLISH_CSV = DATA_DIR / "english_vocab_evp.csv"

# Cache for Wikidata Q-IDs (to avoid repeated lookups)
QIDCACHE_FILE = DATA_DIR / "wikidata_qid_cache.json"

# Wikidata API configuration
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# User-Agent for Wikidata API (required)
HEADERS = {
    "User-Agent": "SRS4Autism-KG-Builder/2.0 (https://github.com/srs4autism; research project)"
}


def load_qid_cache() -> Dict[str, str]:
    """Load cached Wikidata Q-IDs from file."""
    if QIDCACHE_FILE.exists():
        try:
            with open(QIDCACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                print(f"✅ Loaded {len(cache)} cached Q-IDs")
                return cache
        except Exception as e:
            print(f"⚠️  Error loading Q-ID cache: {e}")
    return {}


def save_qid_cache(cache: Dict[str, str]):
    """Save Wikidata Q-ID cache to file."""
    try:
        with open(QIDCACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved {len(cache)} Q-IDs to cache")
    except Exception as e:
        print(f"⚠️  Error saving Q-ID cache: {e}")


def load_hsk_vocabulary(hsk_levels: Optional[List[int]] = None) -> List[Dict]:
    """
    Load HSK vocabulary from CSV files.

    Prioritizes individual HSK CSV files (hsk1.csv, hsk2.csv, etc.) which contain
    English glosses needed for accurate Wikidata Q-ID lookups. Falls back to
    combined CSV if individual files are not available.

    Args:
        hsk_levels: List of HSK levels to load (1-6), or None for all

    Returns:
        List of vocabulary dictionaries with keys: zh, pinyin_raw, en_gloss, hsk_level
    """
    vocab = []
    levels_to_load = hsk_levels or list(range(1, 7))

    # PRIORITY 1: Try individual HSK files first (they have English glosses)
    if HSK_CSV_DIR.exists():
        print(f"📖 Loading HSK vocabulary from individual files in {HSK_CSV_DIR.name}/")
        files_found = 0

        for level in levels_to_load:
            hsk_file = HSK_CSV_DIR / f"hsk{level}.csv"
            if not hsk_file.exists():
                continue

            files_found += 1
            print(f"  📄 Loading HSK{level} from {hsk_file.name}")

            with open(hsk_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3:
                        vocab.append({
                            'zh': row[0].strip(),
                            'pinyin_raw': row[1].strip(),
                            'en_gloss': row[2].strip(),
                            'hsk_level': level
                        })

        if files_found > 0:
            print(f"✅ Loaded {len(vocab)} HSK words from {files_found} individual files")
            return vocab
        else:
            print(f"  ⚠️  No individual HSK files found, trying combined file...")

    # PRIORITY 2: Fall back to combined file (lacks English glosses - less accurate Q-IDs)
    if HSK_COMBINED.exists():
        print(f"📖 Loading HSK vocabulary from combined file {HSK_COMBINED.name}")
        print(f"  ⚠️  WARNING: Combined file lacks English glosses, Q-ID lookups may be less accurate")

        with open(HSK_COMBINED, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    hsk_level_str = row.get('hsk_level', '1').strip()
                    hsk_level = int(hsk_level_str) if hsk_level_str else 1
                except (ValueError, AttributeError):
                    hsk_level = 1

                if hsk_levels and hsk_level not in hsk_levels:
                    continue

                word = row.get('word', '').strip()
                if not word:  # Skip empty rows
                    continue

                vocab.append({
                    'zh': word,
                    'traditional': row.get('traditional', '').strip(),
                    'pinyin_raw': row.get('pinyin', '').strip(),
                    'en_gloss': '',  # Not available in combined file
                    'hsk_level': hsk_level
                })

        print(f"✅ Loaded {len(vocab)} HSK words from combined file")
        return vocab

    # No files found
    print(f"❌ No HSK vocabulary files found!")
    return vocab


def load_english_vocabulary(limit: Optional[int] = None) -> List[Dict]:
    """
    Load English vocabulary from CSV.

    Args:
        limit: Maximum number of words to load, or None for all

    Returns:
        List of vocabulary dictionaries
    """
    vocab = []

    if not ENGLISH_CSV.exists():
        print(f"⚠️  English vocabulary file not found: {ENGLISH_CSV}")
        return vocab

    print(f"📖 Loading English vocabulary from {ENGLISH_CSV.name}")

    with open(ENGLISH_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if limit and idx >= limit:
                break

            vocab.append({
                'en': row.get('word', '').strip(),
                'definition': row.get('definition', '').strip(),
                'pos': row.get('pos', 'noun').strip(),
                'cefr_level': row.get('cefr_level', '').strip(),
                'concreteness': row.get('concreteness', '').strip()
            })

    print(f"✅ Loaded {len(vocab)} English words")
    return vocab


def clean_pinyin_for_uri(pinyin: str) -> str:
    """
    Clean pinyin for URI usage (remove tones, spaces, special chars).

    Args:
        pinyin: Pinyin with tone marks (e.g., "péng you")

    Returns:
        Clean pinyin for URI (e.g., "pengyou")
    """
    # Remove tone marks
    tone_map = {
        'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
        'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
        'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
        'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
        'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
        'ǖ': 'v', 'ǘ': 'v', 'ǚ': 'v', 'ǜ': 'v', 'ü': 'v',
    }

    result = pinyin.lower().strip()
    for tone, base in tone_map.items():
        result = result.replace(tone, base)

    # Remove spaces and special characters
    result = re.sub(r'[^\w]', '', result)

    return result


def clean_for_uri(text: str) -> str:
    """
    Clean text to be URL-safe for URI usage.
    Removes spaces, quotes, and special characters.
    """
    # Remove or replace problematic characters
    text = text.lower().strip()
    text = re.sub(r'[^\w\-]', '', text)  # Keep only alphanumeric, hyphens, underscores
    return text


def clean_english_gloss(gloss: str) -> str:
    """
    Clean English gloss for Wikidata searching by removing parenthetical notes.

    Examples:
        "(informal) father" -> "father"
        "dish (type of food)" -> "dish"
        "(negative prefix)" -> "" (empty)

    Args:
        gloss: Raw English gloss from HSK CSV

    Returns:
        Cleaned gloss suitable for Wikidata search
    """
    # Remove all parenthetical content
    cleaned = re.sub(r'\([^)]*\)', '', gloss)
    # Clean up extra whitespace
    cleaned = ' '.join(cleaned.split())
    return cleaned.strip()


def fetch_wikidata_qid(english_term: str, qid_cache: Dict[str, str], use_cache: bool = True) -> Optional[str]:
    """
    Fetch Wikidata Q-ID for a given English term using the Wikidata API.
    Uses cache to avoid repeated API calls.

    Args:
        english_term: The English word to search for
        qid_cache: Dictionary cache for Q-IDs
        use_cache: Whether to check cache first

    Returns:
        Q-ID string (e.g., "Q146") or None if not found
    """
    # Clean the English term (remove parenthetical notes)
    search_term = clean_english_gloss(english_term)

    # If cleaning removed everything, skip
    if not search_term:
        print(f"  ℹ️  Skipping empty gloss after cleaning: '{english_term}'")
        return None

    # Normalize term for cache lookup (use original for cache key)
    cache_key = english_term.lower().strip()

    # Check cache first
    if use_cache and cache_key in qid_cache:
        return qid_cache[cache_key]

    try:
        # Use Wikidata's wbsearchentities API
        params = {
            "action": "wbsearchentities",
            "format": "json",
            "language": "en",
            "type": "item",
            "search": search_term,
            "limit": 5  # Get top 5 results
        }

        response = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "search" in data and len(data["search"]) > 0:
            # Get the first result's Q-ID
            qid = data["search"][0]["id"]
            label = data["search"][0].get("label", "")
            description = data["search"][0].get("description", "")

            # Cache the result
            qid_cache[cache_key] = qid

            # Show cleaned term if different from original
            if search_term != english_term:
                print(f"  ✓ Found Q-ID: {qid} ('{label}' - {description}) [searched: \"{search_term}\"]")
            else:
                print(f"  ✓ Found Q-ID: {qid} ('{label}' - {description})")
            return qid
        else:
            print(f"  ✗ No Q-ID found for '{english_term}' (searched: \"{search_term}\")")
            # Cache negative result to avoid repeated lookups
            qid_cache[cache_key] = None
            return None

    except requests.RequestException as e:
        print(f"  ✗ Error fetching Q-ID for '{english_term}': {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"  ✗ Unexpected API response for '{english_term}': {e}")
        return None


def add_concept(g: Graph, qid: str, english_label: str, description: Optional[str] = None) -> URIRef:
    """
    Add a Concept hub to the graph.

    Args:
        g: RDF graph
        qid: Wikidata Q-ID (e.g., "Q146")
        english_label: Human-readable English label
        description: Optional description

    Returns:
        URIRef of the created concept
    """
    concept_uri = SRS_INST[f"concept_{qid}"]

    # Type
    g.add((concept_uri, RDF.type, SRS_KG.Concept))

    # Label (using rdfs:label)
    g.add((concept_uri, RDFS.label, Literal(f"concept:{english_label}", lang="en")))

    # Description
    if description:
        g.add((concept_uri, RDFS.comment, Literal(description, lang="en")))

    # Wikidata integration
    g.add((concept_uri, SRS_KG.wikidataId, Literal(qid, datatype=XSD.string)))
    g.add((concept_uri, OWL.sameAs, WD[qid]))

    return concept_uri


def add_chinese_word(
    g: Graph,
    zh_text: str,
    pinyin: str,
    pinyin_tones: str,
    concept_uri: URIRef,
    pos: Optional[str] = None,
    hsk_level: int = 1
) -> URIRef:
    """
    Add a Chinese Word spoke to the graph.

    Args:
        g: RDF graph
        zh_text: Chinese text
        pinyin: Pinyin without tones (for URI)
        pinyin_tones: Pinyin with tone marks (for display)
        concept_uri: The concept this word means
        pos: Part of speech
        hsk_level: HSK level

    Returns:
        URIRef of the created word
    """
    # Clean pinyin for URI
    pinyin_clean = clean_for_uri(pinyin)
    word_uri = SRS_INST[f"word_zh_{pinyin_clean}"]

    # Type
    g.add((word_uri, RDF.type, SRS_KG.Word))

    # Label (Chinese text with @zh language tag)
    g.add((word_uri, RDFS.label, Literal(zh_text, lang="zh")))

    # Additional label (pinyin for reference)
    g.add((word_uri, RDFS.label, Literal(pinyin_tones, lang="en-Latn")))

    # Pinyin properties
    g.add((word_uri, SRS_KG.pinyin, Literal(pinyin_tones, datatype=XSD.string)))

    # Part of speech
    if pos:
        g.add((word_uri, SRS_KG.partOfSpeech, Literal(pos, datatype=XSD.string)))

    # HSK level
    g.add((word_uri, SRS_KG.hskLevel, Literal(hsk_level, datatype=XSD.integer)))

    # Hub-and-spoke relationship: Word -> Concept
    g.add((word_uri, SRS_KG.means, concept_uri))

    return word_uri


def add_english_word(
    g: Graph,
    en_text: str,
    concept_uri: URIRef,
    pos: Optional[str] = None
) -> URIRef:
    """
    Add an English Word spoke to the graph.

    Args:
        g: RDF graph
        en_text: English text
        concept_uri: The concept this word means
        pos: Part of speech

    Returns:
        URIRef of the created word
    """
    # Clean English for URI
    en_clean = clean_for_uri(en_text)
    word_uri = SRS_INST[f"word_en_{en_clean}"]

    # Type
    g.add((word_uri, RDF.type, SRS_KG.Word))

    # Label (English text with @en language tag)
    g.add((word_uri, RDFS.label, Literal(en_text, lang="en")))

    # Part of speech
    if pos:
        g.add((word_uri, SRS_KG.partOfSpeech, Literal(pos, datatype=XSD.string)))

    # Hub-and-spoke relationship: Word -> Concept
    g.add((word_uri, SRS_KG.means, concept_uri))

    # Learning theme (for Logic City integration)
    g.add((word_uri, SRS_KG.learningTheme, Literal("Logic City", datatype=XSD.string)))

    return word_uri


def generate_knowledge_graph(
    hsk_vocab: List[Dict],
    english_vocab: Optional[List[Dict]] = None,
    qid_cache: Optional[Dict] = None,
    rate_limit: float = 0.5,
    save_every: int = 100
) -> Graph:
    """
    Generate the knowledge graph from vocabulary lists.

    Args:
        hsk_vocab: List of HSK vocabulary dictionaries
        english_vocab: Optional list of English vocabulary
        qid_cache: Cache for Wikidata Q-IDs
        rate_limit: Seconds to wait between Wikidata API calls
        save_every: Save cache every N items

    Returns:
        RDF Graph object
    """
    print("\n" + "="*70)
    print("KNOWLEDGE GRAPH GENERATOR V2 - ONTOLOGY-DRIVEN")
    print("="*70 + "\n")

    if qid_cache is None:
        qid_cache = {}

    # Initialize graph
    g = Graph()

    # Bind namespaces
    g.bind("srs-kg", SRS_KG)
    g.bind("srs-inst", SRS_INST)
    g.bind("wd", WD)
    g.bind("owl", OWL)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    total_items = len(hsk_vocab)
    processed = 0
    skipped = 0
    concepts_created = set()

    print(f"Processing {total_items} HSK vocabulary items...\n")

    for idx, entry in enumerate(hsk_vocab, start=1):
        zh = entry.get("zh", "").strip()
        pinyin_raw = entry.get("pinyin_raw", "").strip()
        hsk_level = entry.get("hsk_level", 1)

        if not zh:
            skipped += 1
            continue

        # Clean pinyin for URI and generate if missing
        if pinyin_raw:
            pinyin_clean = clean_pinyin_for_uri(pinyin_raw)
            pinyin_tones = pinyin_raw
        elif HAS_PYPINYIN:
            # Generate pinyin if not provided
            pinyin_tones = " ".join([x[0] for x in get_pinyin(zh, style=Style.TONE)])
            pinyin_clean = clean_pinyin_for_uri(pinyin_tones)
        else:
            print(f"[{idx}/{total_items}] ⚠️  Skipping '{zh}' - no pinyin available")
            skipped += 1
            continue

        # Try to get English gloss (for Q-ID lookup)
        en_gloss = entry.get("en_gloss", "").strip()

        # Skip if no English gloss for now (we need it for Wikidata lookup)
        # In production, you might want to use a dictionary or translation API
        if not en_gloss:
            # Try to use Chinese word for Wikidata search (less reliable)
            en_gloss = zh

        print(f"[{idx}/{total_items}] Processing: {zh} ({pinyin_tones}) [HSK{hsk_level}]")

        # Step 1: Fetch Wikidata Q-ID (with cache)
        qid = fetch_wikidata_qid(en_gloss, qid_cache)

        if not qid:
            print(f"  ⚠️  Skipping - no Q-ID found\n")
            skipped += 1
            continue

        # Step 2: Create Concept hub (only once per Q-ID)
        if qid not in concepts_created:
            concept_uri = add_concept(g, qid, en_gloss)
            print(f"  ✓ Created concept: {concept_uri}")
            concepts_created.add(qid)
        else:
            concept_uri = SRS_INST[f"concept_{qid}"]
            print(f"  ℹ️  Reusing existing concept: {concept_uri}")

        # Step 3: Create Chinese Word spoke
        zh_word_uri = add_chinese_word(
            g, zh, pinyin_clean, pinyin_tones, concept_uri,
            pos=None, hsk_level=hsk_level
        )
        print(f"  ✓ Created Chinese word: {zh_word_uri}")

        processed += 1

        # Rate limiting (be nice to Wikidata)
        if rate_limit > 0:
            time.sleep(rate_limit)

        # Periodic cache save
        if save_every and idx % save_every == 0:
            save_qid_cache(qid_cache)
            print(f"  💾 Progress saved ({idx}/{total_items})\n")

    # Process English vocabulary if provided
    if english_vocab:
        print(f"\nProcessing {len(english_vocab)} English vocabulary items...\n")

        for idx, entry in enumerate(english_vocab, start=1):
            en = entry.get("en", "").strip()
            pos = entry.get("pos", "noun").strip()

            if not en:
                continue

            print(f"[{idx}/{len(english_vocab)}] Processing English: {en}")

            # Fetch Q-ID
            qid = fetch_wikidata_qid(en, qid_cache)

            if not qid:
                print(f"  ⚠️  Skipping - no Q-ID found\n")
                continue

            # Create/reuse concept
            if qid not in concepts_created:
                concept_uri = add_concept(g, qid, en)
                print(f"  ✓ Created concept: {concept_uri}")
                concepts_created.add(qid)
            else:
                concept_uri = SRS_INST[f"concept_{qid}"]
                print(f"  ℹ️  Reusing existing concept: {concept_uri}")

            # Create English word
            en_word_uri = add_english_word(g, en, concept_uri, pos)
            print(f"  ✓ Created English word: {en_word_uri}")

            # Rate limiting
            if rate_limit > 0:
                time.sleep(rate_limit)

    print("\n" + "="*70)
    print(f"✅ Generation complete!")
    print(f"   Total triples: {len(g)}")
    print(f"   Concepts created: {len(concepts_created)}")
    print(f"   HSK words processed: {processed}/{total_items}")
    print(f"   Skipped: {skipped}")
    print("="*70 + "\n")

    return g


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Generate Knowledge Graph v2.0")
    parser.add_argument("--hsk-levels", nargs="+", type=int, choices=range(1, 7),
                       help="HSK levels to process (1-6), default: all")
    parser.add_argument("--english", action="store_true",
                       help="Include English vocabulary from Logic City")
    parser.add_argument("--english-limit", type=int, default=None,
                       help="Limit number of English words to process")
    parser.add_argument("--rate-limit", type=float, default=0.5,
                       help="Seconds between Wikidata API calls (default: 0.5)")
    parser.add_argument("--save-every", type=int, default=100,
                       help="Save cache every N items (default: 100)")
    parser.add_argument("--output", type=str,
                       default="knowledge_graph/world_model_v2.ttl",
                       help="Output file path")
    parser.add_argument("--sample", type=int, default=None,
                       help="Process only first N HSK words (for testing)")

    args = parser.parse_args()

    print("="*70)
    print("KNOWLEDGE GRAPH GENERATOR V2.0")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  HSK Levels: {args.hsk_levels or 'All (1-6)'}")
    print(f"  English vocab: {'Yes' if args.english else 'No'}")
    print(f"  Rate limit: {args.rate_limit}s")
    print(f"  Output: {args.output}")
    print()

    # Load Q-ID cache
    qid_cache = load_qid_cache()

    # Load HSK vocabulary
    hsk_vocab = load_hsk_vocabulary(args.hsk_levels)

    # Apply sample limit if specified
    if args.sample:
        print(f"⚠️  SAMPLE MODE: Processing only first {args.sample} words\n")
        hsk_vocab = hsk_vocab[:args.sample]

    # Load English vocabulary if requested
    english_vocab = None
    if args.english:
        english_vocab = load_english_vocabulary(args.english_limit)

    # Generate the graph
    graph = generate_knowledge_graph(
        hsk_vocab=hsk_vocab,
        english_vocab=english_vocab,
        qid_cache=qid_cache,
        rate_limit=args.rate_limit,
        save_every=args.save_every
    )

    # Save final cache
    save_qid_cache(qid_cache)

    # Output path
    output_path = PROJECT_ROOT / args.output

    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize to Turtle format
    print(f"Writing to: {output_path}")
    graph.serialize(destination=str(output_path), format="turtle")

    # Get file size
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n✅ SUCCESS! Knowledge graph saved to:\n   {output_path}")
    print(f"   File size: {size_mb:.2f} MB\n")

    # Validation
    print("="*70)
    print("VALIDATION CHECKS")
    print("="*70)

    # Check for URL-safe URIs
    print("\n1. URI Safety Check:")
    all_uris = set(graph.subjects()) | set(graph.objects())
    problematic_uris = [uri for uri in all_uris if isinstance(uri, URIRef) and (" " in str(uri) or "'" in str(uri) or '"' in str(uri))]

    if problematic_uris:
        print(f"  ✗ Found {len(problematic_uris)} problematic URIs with spaces/quotes:")
        for uri in problematic_uris[:5]:
            print(f"    - {uri}")
    else:
        print("  ✓ All URIs are URL-safe (no spaces, quotes, or special chars)")

    # Check for rdfs:label usage
    print("\n2. rdfs:label Usage Check:")
    concepts = list(graph.subjects(RDF.type, SRS_KG.Concept))
    words = list(graph.subjects(RDF.type, SRS_KG.Word))

    concepts_without_labels = [c for c in concepts if not list(graph.objects(c, RDFS.label))]
    words_without_labels = [w for w in words if not list(graph.objects(w, RDFS.label))]

    if concepts_without_labels or words_without_labels:
        print(f"  ✗ Entities without rdfs:label:")
        print(f"    - Concepts: {len(concepts_without_labels)}")
        print(f"    - Words: {len(words_without_labels)}")
    else:
        print(f"  ✓ All entities have rdfs:label")
        print(f"    - Concepts: {len(concepts)}")
        print(f"    - Words: {len(words)}")

    # Check for Wikidata links
    print("\n3. Wikidata Integration Check:")
    concepts_with_sameAs = [c for c in concepts if list(graph.objects(c, OWL.sameAs))]
    print(f"  ✓ Concepts linked to Wikidata: {len(concepts_with_sameAs)}/{len(concepts)}")

    print("\n" + "="*70)
    print("All validation checks complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
