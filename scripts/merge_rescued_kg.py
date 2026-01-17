#!/usr/bin/env python3
"""
Merge Rescued Knowledge Graph Files
====================================
Combine all rescued files into one complete knowledge graph.
"""

from pathlib import Path
from rdflib import Graph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_rescued.ttl"

# Source files in order
SOURCE_FILES = [
    "world_model_seed.ttl",                    # Characters + Concepts + Ontology
    "world_model_chinese_words_valid.ttl",     # Chinese words with pinyin
    "world_model_english_words_valid.ttl",     # English words
    "world_model_grammar_valid.ttl",           # Grammar points
]

def main():
    print("🔗 Merging Rescued Knowledge Graph Files...\n")

    # Create merged graph
    merged = Graph()

    for filename in SOURCE_FILES:
        filepath = PROJECT_ROOT / "knowledge_graph" / filename
        if not filepath.exists():
            print(f"   ⚠️  Skipping {filename} (not found)")
            continue

        print(f"   📥 Loading {filename}...")
        g = Graph()
        g.parse(str(filepath), format='turtle')

        # Add all triples to merged graph
        for triple in g:
            merged.add(triple)

        print(f"      Added {len(g):,} triples")

    print(f"\n✅ Total triples in merged graph: {len(merged):,}")

    # Serialize to file
    print(f"\n💾 Writing to {OUTPUT_FILE.name}...")
    merged.serialize(destination=str(OUTPUT_FILE), format='turtle')

    output_size = OUTPUT_FILE.stat().st_size / 1e6
    print(f"✅ DONE! Created {OUTPUT_FILE.name} ({output_size:.1f} MB)")

    # Validate
    print(f"\n🔍 Validating output...")
    test = Graph()
    test.parse(str(OUTPUT_FILE), format='turtle')
    print(f"✅ Valid! {len(test):,} triples")

if __name__ == "__main__":
    main()
