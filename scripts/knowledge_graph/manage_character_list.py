#!/usr/bin/env python3
"""
Manage Chinese character list for the knowledge graph.

1. Extract unique characters from HSK vocabulary
2. Get GB2312 character set (6763 characters)
3. Add missing characters to the knowledge graph
"""
import sys
import csv
import re
from pathlib import Path
from typing import Set, Dict, List
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rdflib import Graph, Namespace, RDF, RDFS, Literal, XSD
from rdflib.namespace import RDF, RDFS

SRS_KG = Namespace("http://srs4autism.com/schema/")
SRS_INST = Namespace("http://srs4autism.com/instance/")


def extract_characters_from_hsk() -> Set[str]:
    """Extract all unique characters from HSK vocabulary."""
    hsk_file = PROJECT_ROOT / "data" / "content_db" / "hsk_vocabulary.csv"
    
    if not hsk_file.exists():
        print(f"⚠️  HSK vocabulary file not found: {hsk_file}")
        return set()
    
    characters = set()
    print(f"📚 Extracting characters from {hsk_file}...")
    
    with open(hsk_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row.get('word', '').strip()
            # Extract all Chinese characters
            for char in word:
                if '\u4e00' <= char <= '\u9fff':  # Chinese character range
                    characters.add(char)
    
    print(f"   ✅ Found {len(characters)} unique characters in HSK vocabulary")
    return characters


def get_gb2312_characters() -> Set[str]:
    """
    Generate GB2312 character set (6763 characters).
    
    GB2312 encoding range:
    - Level 1: B0A1 - D7F9 (3755 characters)
    - Level 2: D8A1 - FEFE (3008 characters)
    - Total: 6763 characters
    """
    characters = set()
    print("📚 Generating GB2312 character set...")
    
    # Level 1: B0A1 - D7F9 (3755 characters)
    level1_count = 0
    for row in range(0xB0, 0xD8):
        for col in range(0xA1, 0xFE + 1):
            try:
                byte_pair = bytes([row, col])
                char = byte_pair.decode('gb2312')
                if '\u4e00' <= char <= '\u9fff':  # Only Chinese characters
                    characters.add(char)
                    level1_count += 1
            except (UnicodeDecodeError, UnicodeError):
                continue
    
    # Level 2: D8A1 - FEFE (3008 characters)
    level2_count = 0
    for row in range(0xD8, 0xFF):
        for col in range(0xA1, 0xFE + 1):
            try:
                byte_pair = bytes([row, col])
                char = byte_pair.decode('gb2312')
                if '\u4e00' <= char <= '\u9fff':  # Only Chinese characters
                    characters.add(char)
                    level2_count += 1
            except (UnicodeDecodeError, UnicodeError):
                continue
    
    print(f"   ✅ Generated {len(characters)} GB2312 characters")
    print(f"      Level 1: {level1_count}, Level 2: {level2_count}")
    return characters


def get_existing_characters(kg_file: Path) -> Set[str]:
    """Get all existing Character nodes from the knowledge graph."""
    if not kg_file.exists():
        print(f"⚠️  KG file not found: {kg_file}")
        return set()
    
    print(f"📚 Loading existing characters from {kg_file}...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.parse(str(kg_file), format="turtle")
    
    characters = set()
    for char_uri in graph.subjects(RDF.type, SRS_KG.Character):
        labels = list(graph.objects(char_uri, RDFS.label))
        for label in labels:
            char_str = str(label)
            if '\u4e00' <= char_str <= '\u9fff':
                characters.add(char_str)
    
    print(f"   ✅ Found {len(characters)} existing Character nodes")
    return characters


def generate_slug(char: str) -> str:
    """Generate URL-safe slug from character."""
    # URL encode the character
    return quote(char, safe='')


def create_character_node(graph: Graph, char: str) -> None:
    """Create a Character node in the graph if it doesn't exist."""
    char_slug = generate_slug(char)
    char_uri = SRS_KG[f"char-{char_slug}"]
    
    # Check if already exists
    if (char_uri, RDF.type, SRS_KG.Character) in graph:
        return
    
    # Create character node
    graph.add((char_uri, RDF.type, SRS_KG.Character))
    graph.add((char_uri, RDFS.label, Literal(char, lang="zh")))
    graph.add((char_uri, SRS_KG.glyph, Literal(char, lang="zh")))
    
    # Note: We don't have definitions for all GB2312 characters,
    # but they can be added later from dictionaries


def add_characters_to_kg(
    characters: Set[str],
    kg_file: Path,
    output_file: Path = None
) -> int:
    """
    Add characters to the knowledge graph.
    
    Args:
        characters: Set of characters to add
        kg_file: Path to existing KG file
        output_file: Path to output file (if None, overwrites kg_file)
    
    Returns:
        Number of characters added
    """
    if output_file is None:
        output_file = kg_file
    
    print(f"📚 Loading knowledge graph from {kg_file}...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.bind("srs-inst", SRS_INST)
    
    if kg_file.exists():
        graph.parse(str(kg_file), format="turtle")
    
    # Get existing characters
    existing = get_existing_characters(kg_file) if kg_file.exists() else set()
    
    # Find characters to add
    to_add = characters - existing
    print(f"   📊 {len(existing)} existing, {len(to_add)} new characters to add")
    
    if not to_add:
        print("   ✅ All characters already in KG")
        return 0
    
    # Add characters
    print(f"   🔨 Adding {len(to_add)} characters...")
    added = 0
    for char in sorted(to_add):
        try:
            create_character_node(graph, char)
            added += 1
            if added % 100 == 0:
                print(f"      Added {added}/{len(to_add)} characters...")
        except Exception as e:
            print(f"      ⚠️  Error adding character '{char}': {e}")
    
    # Save
    print(f"   💾 Saving to {output_file}...")
    graph.serialize(destination=str(output_file), format="turtle")
    print(f"   ✅ Added {added} characters to knowledge graph")
    
    return added


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Manage Chinese character list for knowledge graph"
    )
    parser.add_argument(
        "--source",
        choices=["hsk", "gb2312", "both"],
        default="both",
        help="Character source: hsk (from HSK vocabulary), gb2312 (GB2312 set), or both"
    )
    parser.add_argument(
        "--kg-file",
        type=Path,
        default=PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl",
        help="Path to knowledge graph file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: overwrite kg-file)"
    )
    parser.add_argument(
        "--prefer-hsk",
        action="store_true",
        help="If both sources, prefer HSK characters (use GB2312 only for missing)"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Chinese Character List Management")
    print("=" * 80)
    print()
    
    # Collect characters
    all_characters = set()
    
    if args.source in ("hsk", "both"):
        hsk_chars = extract_characters_from_hsk()
        all_characters.update(hsk_chars)
        print(f"   HSK characters: {len(hsk_chars)}")
    
    if args.source in ("gb2312", "both"):
        gb2312_chars = get_gb2312_characters()
        if args.source == "both" and args.prefer_hsk:
            # Only add GB2312 characters not in HSK
            gb2312_chars = gb2312_chars - all_characters
            print(f"   GB2312 characters (not in HSK): {len(gb2312_chars)}")
        all_characters.update(gb2312_chars)
        if args.source == "gb2312":
            print(f"   GB2312 characters: {len(gb2312_chars)}")
    
    print(f"\n📊 Total unique characters: {len(all_characters)}")
    print()
    
    # Add to KG
    added = add_characters_to_kg(
        all_characters,
        args.kg_file,
        args.output
    )
    
    print()
    print("=" * 80)
    if added > 0:
        print(f"✅ Successfully added {added} characters to knowledge graph")
    else:
        print("✅ No new characters to add")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

