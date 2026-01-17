#!/usr/bin/env python3
"""
Extract grammar points, skip broken blocks
==========================================
Process grammar points section and skip any blocks with parse errors.
Save broken blocks separately for later reconstruction.
"""

import re
from pathlib import Path
from rdflib import Graph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_preprocessed.ttl"
OUTPUT_VALID = PROJECT_ROOT / "knowledge_graph" / "world_model_grammar_valid.ttl"
OUTPUT_SKIPPED = PROJECT_ROOT / "knowledge_graph" / "world_model_grammar_skipped.ttl"

def main():
    print("🚀 Extracting grammar points (skip broken blocks)...")

    # Read the entire file
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Extract prefix definitions
    prefixes = []
    for line in lines[:50]:
        if line.strip().startswith('@prefix'):
            prefixes.append(line)

    prefix_block = ''.join(prefixes)

    # Find grammar points section (lines starting with srs-inst:gp-)
    print("📍 Finding grammar points section...")
    grammar_blocks = []
    current_block = []
    in_grammar = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect start of grammar point block
        if re.match(r'^srs-inst:gp-', stripped):
            if current_block:
                grammar_blocks.append(''.join(current_block))
            current_block = [line]
            in_grammar = True
        elif in_grammar:
            # Continue accumulating lines
            if line and not line[0].isspace() and not stripped.startswith('@'):
                # New block starting, save previous
                grammar_blocks.append(''.join(current_block))
                current_block = []
                in_grammar = False
                # Check if this new line is also a grammar point
                if re.match(r'^srs-inst:gp-', stripped):
                    current_block = [line]
                    in_grammar = True
            else:
                current_block.append(line)

    if current_block and in_grammar:
        grammar_blocks.append(''.join(current_block))

    print(f"✅ Found {len(grammar_blocks):,} grammar point blocks")

    # Test each block
    print("🧪 Testing blocks individually...")
    valid_blocks = []
    skipped_blocks = []

    for i, block in enumerate(grammar_blocks):
        if i % 100 == 0:
            print(f"   Processed {i:,}/{len(grammar_blocks):,} blocks... (valid: {len(valid_blocks):,}, skipped: {len(skipped_blocks):,})")

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
    print(f"   Total blocks: {len(grammar_blocks):,}")
    print(f"   Valid blocks: {len(valid_blocks):,}")
    print(f"   Skipped blocks: {len(skipped_blocks):,}")
    if len(grammar_blocks) > 0:
        print(f"   Success rate: {len(valid_blocks)/len(grammar_blocks)*100:.1f}%")

    # Write valid blocks
    with open(OUTPUT_VALID, 'w', encoding='utf-8') as f:
        f.write(prefix_block)
        f.write('\n\n')
        for block in valid_blocks:
            f.write(block)
            f.write('\n')

    # Write skipped blocks
    with open(OUTPUT_SKIPPED, 'w', encoding='utf-8') as f:
        f.write("# SKIPPED GRAMMAR POINT BLOCKS\n")
        f.write("# These blocks had parse errors and need reconstruction\n\n")
        for block in skipped_blocks:
            f.write(block)
            f.write('\n')

    # Validate final output if we have valid blocks
    if len(valid_blocks) > 0:
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
