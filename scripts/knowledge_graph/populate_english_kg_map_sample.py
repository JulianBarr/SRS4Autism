#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample script to populate _KG_Map for English vocabulary cards.

This script:
1. Queries AnkiConnect for "CUMA - Basic (and reversed card)" notes in "YM::YM_ENG::Vocab" deck
2. Matches Back field to English words in the knowledge graph
3. Creates _KG_Map JSON for both card directions
4. Shows sample of 5 cards for review before bulk update

Usage:
    python populate_english_kg_map_sample.py
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from rdflib import Graph, Namespace, Literal
    from rdflib.namespace import RDF, RDFS
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

from anki_integration.anki_connect import AnkiConnect

# Configuration
KG_FILE = project_root / 'knowledge_graph' / 'world_model_english.ttl'
DECK_NAME = "YM::YM_ENG::Vocab"
NOTE_TYPE = "CUMA - Basic (and reversed card)"
SAMPLE_SIZE = 5

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")


def load_english_kg() -> Tuple[Graph, Dict[str, str], Dict[str, str]]:
    """
    Load English knowledge graph and build lookup dictionaries.
    
    Returns:
        Tuple of (graph, word_to_concept_map, word_lowercase_map)
        - word_to_concept_map: Maps word text -> concept ID
        - word_lowercase_map: Maps lowercase word -> word text (for case-insensitive lookup)
    """
    print("Loading English knowledge graph...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    
    if not KG_FILE.exists():
        print(f"❌ Knowledge graph file not found: {KG_FILE}")
        sys.exit(1)
    
    try:
        graph.parse(str(KG_FILE), format="turtle")
        print(f"✅ Loaded {len(graph)} triples")
    except Exception as e:
        print(f"❌ Error parsing KG file: {e}")
        sys.exit(1)
    
    # Build lookup maps
    word_to_concept_map = {}  # word text -> (word_id, concept_id)
    word_lowercase_map = {}   # lowercase word -> word text
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        # Get word text (from label or text property)
        word_text = None
        for _, _, label in graph.triples((word_uri, RDFS.label, None)):
            if hasattr(label, 'language') and label.language == 'en':
                word_text = str(label).strip()
                break
        if not word_text:
            for _, _, text in graph.triples((word_uri, SRS_KG.text, None)):
                if hasattr(text, 'language') and (not hasattr(text, 'language') or text.language == 'en'):
                    word_text = str(text).strip()
                    break
        
        if not word_text:
            continue
        
        # Get concept
        concept_uri = None
        for _, _, concept in graph.triples((word_uri, SRS_KG.means, None)):
            concept_uri = concept
            break
        
        if concept_uri:
            # Extract IDs from URIs
            word_id = str(word_uri).split('/')[-1] if '/' in str(word_uri) else str(word_uri)
            concept_id = str(concept_uri).split('/')[-1] if '/' in str(concept_uri) else str(concept_uri)
            
            word_to_concept_map[word_text] = (word_id, concept_id)
            word_lowercase_map[word_text.lower()] = word_text
    
    print(f"✅ Built lookup maps: {len(word_to_concept_map)} words")
    return graph, word_to_concept_map, word_lowercase_map


def extract_word_from_back(back_field: str) -> Optional[str]:
    """
    Extract word from Back field.
    
    Handles:
    - HTML tags
    - Capitalization (first letter may be capitalized)
    - Multi-word phrases
    - Punctuation
    
    Returns:
        Extracted word/phrase or None
    """
    if not back_field:
        return None
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', back_field)
    
    # Strip whitespace
    text = text.strip()
    
    # Remove trailing punctuation (but keep internal punctuation for phrases)
    text = re.sub(r'[.,;:!?]+$', '', text)
    
    # Split by common separators (for multi-word phrases)
    # But first, try to get the whole phrase
    if text:
        return text
    
    return None


def find_word_in_kg(word_text: str, word_to_concept_map: Dict[str, Tuple[str, str]], 
                     word_lowercase_map: Dict[str, str]) -> Optional[Tuple[str, str]]:
    """
    Find word in KG and return (word_id, concept_id).
    
    Args:
        word_text: Word to search for
        word_to_concept_map: Maps word text -> (word_id, concept_id)
        word_lowercase_map: Maps lowercase word -> word text
    
    Returns:
        Tuple of (word_id, concept_id) or None if not found
    """
    # Try exact match first
    if word_text in word_to_concept_map:
        return word_to_concept_map[word_text]
    
    # Try case-insensitive match
    word_lower = word_text.lower()
    if word_lower in word_lowercase_map:
        actual_word = word_lowercase_map[word_lower]
        return word_to_concept_map[actual_word]
    
    # Try with first letter lowercase (common case)
    if word_text and word_text[0].isupper():
        word_lower_first = word_text[0].lower() + word_text[1:]
        if word_lower_first in word_to_concept_map:
            return word_to_concept_map[word_lower_first]
    
    return None


def build_kg_map(word_id: str, concept_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build _KG_Map JSON structure following strict schema from Knowledge Tracking Specification.
    
    Schema:
    {
      "0": [
        { "kp": "word-en-apple", "skill": "sound_to_concept", "weight": 1.0 }
      ],
      "1": [
        { "kp": "word-en-apple", "skill": "concept_to_sound", "weight": 1.0 }
      ]
    }
    
    For "CUMA - Basic (and reversed card)" note type:
    - Card 0: Front (word) => Back (concept) = sound_to_concept (Hear word, select picture)
    - Card 1: Back (concept) => Front (word) = concept_to_sound (See picture, say word)
    
    Args:
        word_id: Word KG ID (e.g., "word-en-cat")
        concept_id: Concept KG ID (e.g., "concept-cat") - unused but kept for compatibility
    
    Returns:
        Dict mapping card index (string) to list of KnowledgeTrace dicts
    """
    return {
        "0": [{"kp": word_id, "skill": "sound_to_concept", "weight": 1.0}],  # Card 1: Word => Concept
        "1": [{"kp": word_id, "skill": "concept_to_sound", "weight": 1.0}],  # Card 2: Concept => Word
    }


def main():
    """Main function to show sample matches."""
    print("=" * 80)
    print("Populate _KG_Map for English Vocabulary Cards - SAMPLE")
    print("=" * 80)
    print()
    
    # Load KG
    graph, word_to_concept_map, word_lowercase_map = load_english_kg()
    print()
    
    # Connect to Anki
    print("Connecting to AnkiConnect...")
    anki = AnkiConnect()
    if not anki.ping():
        print("❌ AnkiConnect is not running. Please start Anki with AnkiConnect add-on.")
        sys.exit(1)
    print("✅ Connected to AnkiConnect")
    print()
    
    # Find notes in the deck
    print(f"Finding notes in deck '{DECK_NAME}' with note type '{NOTE_TYPE}'...")
    query = f'deck:"{DECK_NAME}" note:"{NOTE_TYPE}"'
    note_ids = anki._invoke("findNotes", {"query": query})
    
    if not note_ids:
        print(f"❌ No notes found matching: {query}")
        sys.exit(1)
    
    print(f"✅ Found {len(note_ids)} notes")
    print()
    
    # Get note info for first 5 notes
    print(f"Getting info for first {SAMPLE_SIZE} notes...")
    sample_note_ids = note_ids[:SAMPLE_SIZE]
    notes_info = anki._invoke("notesInfo", {"notes": sample_note_ids})
    
    if not notes_info:
        print("❌ Failed to get note info")
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("SAMPLE MATCHES (for review)")
    print("=" * 80)
    print()
    
    matches = []
    no_matches = []
    
    for note in notes_info:
        note_id = note.get("noteId")
        fields = note.get("fields", {})
        front = fields.get("Front", {}).get("value", "") if isinstance(fields.get("Front"), dict) else fields.get("Front", "")
        back = fields.get("Back", {}).get("value", "") if isinstance(fields.get("Back"), dict) else fields.get("Back", "")
        
        # Extract word from Back field
        word_text = extract_word_from_back(back)
        
        if not word_text:
            no_matches.append({
                "note_id": note_id,
                "front": front[:50] + "..." if len(front) > 50 else front,
                "back": back[:50] + "..." if len(back) > 50 else back,
                "reason": "Could not extract word from Back field"
            })
            continue
        
        # Find in KG
        result = find_word_in_kg(word_text, word_to_concept_map, word_lowercase_map)
        
        if result:
            word_id, concept_id = result
            kg_map = build_kg_map(word_id, concept_id)
            matches.append({
                "note_id": note_id,
                "front": front[:50] + "..." if len(front) > 50 else front,
                "back": back[:50] + "..." if len(back) > 50 else back,
                "extracted_word": word_text,
                "word_id": word_id,
                "concept_id": concept_id,
                "kg_map": kg_map,  # Already a dict, will be serialized when needed
                "kg_map_json": json.dumps(kg_map, ensure_ascii=False)  # JSON string for Anki
            })
        else:
            no_matches.append({
                "note_id": note_id,
                "front": front[:50] + "..." if len(front) > 50 else front,
                "back": back[:50] + "..." if len(back) > 50 else back,
                "extracted_word": word_text,
                "reason": "Word not found in knowledge graph"
            })
    
    # Display matches
    if matches:
        print("✅ MATCHES FOUND:")
        print("-" * 80)
        for i, match in enumerate(matches, 1):
            print(f"\n{i}. Note ID: {match['note_id']}")
            print(f"   Front: {match['front']}")
            print(f"   Back: {match['back']}")
            print(f"   Extracted word: '{match['extracted_word']}'")
            print(f"   Word ID: {match['word_id']}")
            print(f"   Concept ID: {match['concept_id']}")
            print(f"   _KG_Map: {json.dumps(match['kg_map'], indent=2)}")
        print()
    
    # Display no matches
    if no_matches:
        print("⚠️  NO MATCHES (will be skipped):")
        print("-" * 80)
        for i, no_match in enumerate(no_matches, 1):
            print(f"\n{i}. Note ID: {no_match['note_id']}")
            print(f"   Front: {no_match['front']}")
            print(f"   Back: {no_match['back']}")
            if 'extracted_word' in no_match:
                print(f"   Extracted word: '{no_match['extracted_word']}'")
            print(f"   Reason: {no_match['reason']}")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total notes checked: {len(notes_info)}")
    print(f"✅ Matches: {len(matches)}")
    print(f"⚠️  No matches: {len(no_matches)}")
    print()
    
    if matches:
        print("If these matches look correct, you can proceed with bulk update.")
        print("The script will update all notes in the deck with matching words.")
    else:
        print("No matches found. Please check:")
        print("1. Are the words in the Back field matching the KG?")
        print("2. Is the KG file up to date?")
        print("3. Are there capitalization or formatting differences?")


if __name__ == "__main__":
    main()

