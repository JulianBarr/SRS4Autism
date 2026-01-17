#!/usr/bin/env python3
"""
Extract English words, skip broken blocks
==========================================
Process English words section and skip any blocks with parse errors.
Save broken blocks separately for later reconstruction.
"""

import re
from pathlib import Path
from rdflib import Graph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"
OUTPUT_VALID = PROJECT_ROOT / "knowledge_graph" / "world_model_english_words_valid.ttl"
OUTPUT_SKIPPED = PROJECT_ROOT / "knowledge_graph" / "world_model_english_words_skipped.ttl"

def main():
    print("🚀 Extracting English words (skip broken blocks)...")

    # Read the entire file
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Extract prefix definitions
    prefixes = []
    for line in lines[:50]:
        if line.strip().startswith('@prefix'):
            prefixes.append(line)

    prefix_block = ''.join(prefixes)

    # Find English words section (lines starting with srs-kg:word-en-)
    print("📍 Finding English words section...")
    word_blocks = []
    current_block = []
    in_english_word = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect start of English word block
        if stripped.startswith('srs-kg:word-en-'):
            if current_block:
                word_blocks.append(''.join(current_block))
            current_block = [line]
            in_english_word = True
        elif in_english_word:
            current_block.append(line)
            # End of block is a line ending with ' .'
            if stripped.endswith(' .'):
                word_blocks.append(''.join(current_block))
                current_block = []
                in_english_word = False

    print(f"✅ Found {len(word_blocks):,} English word blocks")

    # Test each block
    print("🧪 Testing blocks individually...")
    valid_blocks = []
    skipped_blocks = []

    for i, block in enumerate(word_blocks):
        if i % 1000 == 0:
            print(f"   Processed {i:,}/{len(word_blocks):,} blocks... (valid: {len(valid_blocks):,}, skipped: {len(skipped_blocks):,})")

        # Try parsing this block
        test_content = prefix_block + "\n\n" + block
        try:
            g = Graph()
            g.parse(data=test_content, format='turtle')
            valid_blocks.append(block)
        except Exception as e:
            skipped_blocks.append(block)

    print(f"\n{'='*70}")
    print(f"✅ EXTRACTION COMPLETE!")
    print(f"{'='*70}")
    print(f"   Total blocks: {len(word_blocks):,}")
    print(f"   Valid blocks: {len(valid_blocks):,}")
    print(f"   Skipped blocks: {len(skipped_blocks):,}")
    print(f"   Success rate: {len(valid_blocks)/len(word_blocks)*100:.1f}%")

    # Write valid blocks
    with open(OUTPUT_VALID, 'w', encoding='utf-8') as f:
        f.write(prefix_block)
        f.write('\n\n')
        for block in valid_blocks:
            f.write(block)
            f.write('\n')

    # Write skipped blocks
    with open(OUTPUT_SKIPPED, 'w', encoding='utf-8') as f:
        f.write("# SKIPPED ENGLISH WORD BLOCKS\n")
        f.write("# These blocks had parse errors and need reconstruction\n\n")
        for block in skipped_blocks:
            f.write(block)
            f.write('\n')

    # Validate final output
    print(f"\n🔍 Validating final output...")
    g = Graph()
    g.parse(OUTPUT_VALID, format='turtle')
    print(f"✅ Valid file created: {len(g):,} triples")

    valid_size = OUTPUT_VALID.stat().st_size / 1e6
    skipped_size = OUTPUT_SKIPPED.stat().st_size / 1e6
    print(f"\n📦 Output files:")
    print(f"   Valid: {OUTPUT_VALID.name} ({valid_size:.1f}MB)")
    print(f"   Skipped: {OUTPUT_SKIPPED.name} ({skipped_size:.1f}MB)")

if __name__ == "__main__":
    main()
