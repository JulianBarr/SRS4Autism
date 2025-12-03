#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate _KG_Map for all English vocabulary cards.

This script:
1. Loads the English knowledge graph (world_model_english.ttl)
2. Connects to Anki via AnkiConnect
3. Finds all notes in the YM::YM_ENG::Vocab deck with note type
   "CUMA - Basic (and reversed card)"
4. Extracts the word from the Back field and matches it to KG nodes
5. Writes the directional kg_link entries to the _KG_Map field
6. Logs successes and misses for manual follow-up (e.g., via Wikidata)
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add project root
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from rdflib import Graph, Namespace
    from rdflib.namespace import RDF, RDFS
except ImportError:
    print("ERROR: rdflib is not installed. Install with `pip install rdflib`")
    sys.exit(1)

from anki_integration.anki_connect import AnkiConnect

# Configuration
KG_FILE = project_root / "knowledge_graph" / "world_model_english.ttl"
DECK_NAME = "YM::YM_ENG::Vocab"
NOTE_TYPE = "CUMA - Basic (and reversed card)"
LOG_DIR = project_root / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
NOT_FOUND_LOG = LOG_DIR / "english_kg_map_not_found.json"
SUMMARY_LOG = LOG_DIR / "english_kg_map_summary.json"

SRS_KG = Namespace("http://srs4autism.com/schema/")


def chunked(seq: List[Any], size: int) -> List[List[Any]]:
    """Yield successive chunks from seq."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def load_english_kg() -> Tuple[Graph, Dict[str, Tuple[str, str]], Dict[str, str]]:
    """Load KG and build lookups of word text -> (word_id, concept_id)."""
    print("Loading English knowledge graph...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)

    if not KG_FILE.exists():
        print(f"❌ KG file not found: {KG_FILE}")
        sys.exit(1)

    graph.parse(str(KG_FILE), format="turtle")
    print(f"✅ Loaded {len(graph)} triples")

    word_to_ids: Dict[str, Tuple[str, str]] = {}
    lowercase_map: Dict[str, str] = {}

    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        word_text = None
        for _, _, label in graph.triples((word_uri, RDFS.label, None)):
            if getattr(label, "language", None) == "en":
                word_text = str(label).strip()
                break
        if not word_text:
            for _, _, literal in graph.triples((word_uri, SRS_KG.text, None)):
                if getattr(literal, "language", None) in (None, "en"):
                    word_text = str(literal).strip()
                    break
        if not word_text:
            continue

        concept_uri = None
        for _, _, concept in graph.triples((word_uri, SRS_KG.means, None)):
            concept_uri = concept
            break
        if not concept_uri:
            continue

        word_id = str(word_uri).split("/")[-1]
        concept_id = str(concept_uri).split("/")[-1]
        word_to_ids[word_text] = (word_id, concept_id)
        lowercase_map[word_text.lower()] = word_text

    print(f"✅ Built lookup for {len(word_to_ids)} words")
    return graph, word_to_ids, lowercase_map


def extract_word(back_field: str) -> Optional[str]:
    """Extract the main word/phrase from the Back field."""
    if not back_field:
        return None
    text = re.sub(r"<[^>]+>", "", back_field)
    text = text.strip()
    text = re.sub(r"[.;:!?、，。！？]+$", "", text)
    return text or None


def find_word(word_text: str, word_map: Dict[str, Tuple[str, str]], lowercase_map: Dict[str, str]) -> Optional[Tuple[str, str]]:
    """Locate the word in the KG lookup dictionaries."""
    if word_text in word_map:
        return word_map[word_text]
    lower = word_text.lower()
    if lower in lowercase_map:
        canonical = lowercase_map[lower]
        return word_map.get(canonical)
    if word_text and word_text[0].isupper():
        lowered = word_text[0].lower() + word_text[1:]
        if lowered in word_map:
            return word_map[lowered]
    return None


def build_kg_map(word_id: str, concept_id: str) -> str:
    """
    Build _KG_Map JSON following strict schema from Knowledge Tracking Specification.
    
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
    """
    card_mappings = {
        "0": [{"kp": word_id, "skill": "sound_to_concept", "weight": 1.0}],  # Card 1: Word => Concept
        "1": [{"kp": word_id, "skill": "concept_to_sound", "weight": 1.0}],  # Card 2: Concept => Word
    }
    return json.dumps(card_mappings, ensure_ascii=False, separators=(",", ":"))


def main():
    print("=" * 80)
    print("Populate _KG_Map for English Vocabulary Cards - BULK")
    print("=" * 80)
    print()

    _, word_map, lowercase_map = load_english_kg()
    print()

    print("Connecting to AnkiConnect...")
    anki = AnkiConnect()
    if not anki.ping():
        print("❌ AnkiConnect not reachable. Please open Anki with AnkiConnect running.")
        sys.exit(1)
    print("✅ Connected to AnkiConnect\n")

    query = f'deck:"{DECK_NAME}" note:"{NOTE_TYPE}"'
    note_ids = anki._invoke("findNotes", {"query": query})
    if not note_ids:
        print(f"❌ No notes found for query: {query}")
        sys.exit(1)
    print(f"✅ Found {len(note_ids)} notes to process\n")

    successes = []
    skipped = []

    for chunk in chunked(note_ids, 100):
        notes_info = anki._invoke("notesInfo", {"notes": chunk}) or []
        for note in notes_info:
            note_id = note.get("noteId")
            fields = note.get("fields", {})
            front_field = fields.get("Front", {})
            back_field = fields.get("Back", {})
            front_text = front_field.get("value") if isinstance(front_field, dict) else front_field
            back_text = back_field.get("value") if isinstance(back_field, dict) else back_field

            word_text = extract_word(back_text or "")
            if not word_text:
                skipped.append(
                    {
                        "note_id": note_id,
                        "front": front_text,
                        "back": back_text,
                        "reason": "Back field empty or unparsable",
                    }
                )
                continue

            match = find_word(word_text, word_map, lowercase_map)
            if not match:
                skipped.append(
                    {
                        "note_id": note_id,
                        "front": front_text,
                        "back": back_text,
                        "word": word_text,
                        "reason": "Word not found in KG",
                    }
                )
                continue

            word_id, concept_id = match
            kg_map_str = build_kg_map(word_id, concept_id)

            try:
                anki._invoke(
                    "updateNoteFields",
                    {"note": {"id": note_id, "fields": {"_KG_Map": kg_map_str}}},
                )
                successes.append(
                    {
                        "note_id": note_id,
                        "word": word_text,
                        "word_id": word_id,
                        "concept_id": concept_id,
                    }
                )
            except Exception as e:
                skipped.append(
                    {
                        "note_id": note_id,
                        "word": word_text,
                        "reason": f"Anki update failed: {e}",
                    }
                )

    print("\nSummary")
    print("-" * 80)
    print(f"✅ Successfully updated: {len(successes)}")
    print(f"⚠️  Skipped / not found: {len(skipped)}")
    print(f"Logs:")
    print(f"  Success summary -> {SUMMARY_LOG}")
    print(f"  Not found log  -> {NOT_FOUND_LOG}")

    with open(SUMMARY_LOG, "w", encoding="utf-8") as f:
        json.dump({"updated": successes}, f, indent=2, ensure_ascii=False)

    with open(NOT_FOUND_LOG, "w", encoding="utf-8") as f:
        json.dump({"skipped": skipped}, f, indent=2, ensure_ascii=False)

    print("\nDone.")


if __name__ == "__main__":
    main()

