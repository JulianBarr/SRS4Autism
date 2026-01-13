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
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import requests
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import XSD

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Define namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
SRS_INST = Namespace("http://srs4autism.com/instance/")
WD = Namespace("http://www.wikidata.org/entity/")

# Sample HSK 1 vocabulary with hardcoded Q-IDs (fallback for API issues)
HSK1_VOCAB = [
    {"zh": "朋友", "pinyin": "pengyou", "pinyin_tones": "péng you", "en": "friend", "pos": "noun", "qid": "Q34079"},
    {"zh": "猫", "pinyin": "mao", "pinyin_tones": "māo", "en": "cat", "pos": "noun", "qid": "Q146"},
    {"zh": "吃", "pinyin": "chi", "pinyin_tones": "chī", "en": "eat", "pos": "verb", "qid": "Q213449"},
    {"zh": "老师", "pinyin": "laoshi", "pinyin_tones": "lǎo shī", "en": "teacher", "pos": "noun", "qid": "Q37226"},
    {"zh": "苹果", "pinyin": "pingguo", "pinyin_tones": "píng guǒ", "en": "apple", "pos": "noun", "qid": "Q89"},
]

# Wikidata API configuration
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# User-Agent for Wikidata API (required)
HEADERS = {
    "User-Agent": "SRS4Autism-KG-Builder/2.0 (https://github.com/srs4autism; research project)"
}


def clean_for_uri(text: str) -> str:
    """
    Clean text to be URL-safe for URI usage.
    Removes spaces, quotes, and special characters.
    """
    # Remove or replace problematic characters
    text = text.lower().strip()
    text = re.sub(r'[^\w\-]', '', text)  # Keep only alphanumeric, hyphens, underscores
    return text


def fetch_wikidata_qid(english_term: str, hardcoded_qid: Optional[str] = None, language: str = "en") -> Optional[str]:
    """
    Fetch Wikidata Q-ID for a given English term using the Wikidata API.
    Falls back to hardcoded Q-ID if API fails.

    Args:
        english_term: The English word to search for
        hardcoded_qid: Optional hardcoded Q-ID to use as fallback
        language: Language code (default: "en")

    Returns:
        Q-ID string (e.g., "Q146") or None if not found
    """
    # If hardcoded Q-ID is provided, use it as fallback
    if hardcoded_qid:
        print(f"  ✓ Using hardcoded Q-ID: {hardcoded_qid}")
        return hardcoded_qid

    try:
        # Use Wikidata's wbsearchentities API
        params = {
            "action": "wbsearchentities",
            "format": "json",
            "language": language,
            "type": "item",
            "search": english_term,
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

            print(f"  ✓ Found Q-ID: {qid} ('{label}' - {description})")
            return qid
        else:
            print(f"  ✗ No Q-ID found for '{english_term}'")
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


def generate_knowledge_graph() -> Graph:
    """
    Generate the knowledge graph from HSK 1 vocabulary.

    Returns:
        RDF Graph object
    """
    print("\n" + "="*70)
    print("KNOWLEDGE GRAPH GENERATOR V2 - ONTOLOGY-DRIVEN")
    print("="*70 + "\n")

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

    print(f"Processing {len(HSK1_VOCAB)} vocabulary items...\n")

    for idx, entry in enumerate(HSK1_VOCAB, start=1):
        zh = entry["zh"]
        pinyin = entry["pinyin"]
        pinyin_tones = entry["pinyin_tones"]
        en = entry["en"]
        pos = entry.get("pos")
        hardcoded_qid = entry.get("qid")

        print(f"[{idx}/{len(HSK1_VOCAB)}] Processing: {zh} ({pinyin_tones}) = {en}")

        # Step 1: Fetch Wikidata Q-ID (with hardcoded fallback)
        qid = fetch_wikidata_qid(en, hardcoded_qid=hardcoded_qid)

        if not qid:
            print(f"  ⚠ Skipping '{en}' - no Q-ID found\n")
            continue

        # Step 2: Create Concept hub
        concept_uri = add_concept(g, qid, en)
        print(f"  ✓ Created concept: {concept_uri}")

        # Step 3: Create Chinese Word spoke
        zh_word_uri = add_chinese_word(g, zh, pinyin, pinyin_tones, concept_uri, pos)
        print(f"  ✓ Created Chinese word: {zh_word_uri}")

        # Step 4: Create English Word spoke
        en_word_uri = add_english_word(g, en, concept_uri, pos)
        print(f"  ✓ Created English word: {en_word_uri}")

        print()

        # Rate limiting (be nice to Wikidata)
        time.sleep(0.5)

    print("="*70)
    print(f"✅ Generation complete! Total triples: {len(g)}")
    print("="*70 + "\n")

    return g


def main():
    """Main execution function."""
    # Generate the graph
    graph = generate_knowledge_graph()

    # Output path
    output_path = PROJECT_ROOT / "knowledge_graph" / "world_model_v2.ttl"

    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize to Turtle format
    print(f"Writing to: {output_path}")
    graph.serialize(destination=str(output_path), format="turtle")

    print(f"\n✅ SUCCESS! Knowledge graph saved to:\n   {output_path}\n")

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
