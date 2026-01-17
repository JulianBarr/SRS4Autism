#!/usr/bin/env python3
"""
Comprehensive KG Statistics
============================
Extract and test all major entity types from the knowledge graph.
"""

import re
from pathlib import Path
from rdflib import Graph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_preprocessed.ttl"

def extract_and_test_category(lines, prefix_block, pattern, category_name):
    """Extract blocks matching pattern and test each one."""
    print(f"\n{'='*70}")
    print(f"📊 {category_name}")
    print(f"{'='*70}")

    blocks = []
    current_block = []
    in_block = False

    for line in lines:
        stripped = line.strip()

        # Detect start of block
        if re.match(pattern, stripped):
            if current_block:
                blocks.append(''.join(current_block))
            current_block = [line]
            in_block = True
        elif in_block:
            # Continue accumulating lines
            if line and not line[0].isspace() and not stripped.startswith('@'):
                # New block starting
                blocks.append(''.join(current_block))
                current_block = []
                in_block = False
                # Check if this new line matches pattern
                if re.match(pattern, stripped):
                    current_block = [line]
                    in_block = True
            else:
                current_block.append(line)

    if current_block and in_block:
        blocks.append(''.join(current_block))

    if len(blocks) == 0:
        print(f"   ⚠️  No blocks found")
        return 0, 0, 0

    print(f"   Found: {len(blocks):,} blocks")

    # Test each block
    valid = 0
    broken = 0

    for i, block in enumerate(blocks):
        if i % 1000 == 0 and i > 0:
            print(f"   Testing... {i:,}/{len(blocks):,}")

        test_content = prefix_block + "\n\n" + block
        try:
            g = Graph()
            g.parse(data=test_content, format='turtle')
            valid += 1
        except:
            broken += 1

    success_rate = (valid / len(blocks) * 100) if len(blocks) > 0 else 0

    print(f"   ✅ Valid: {valid:,} ({success_rate:.1f}%)")
    print(f"   ❌ Broken: {broken:,} ({100-success_rate:.1f}%)")

    return len(blocks), valid, broken

def main():
    print("🚀 Comprehensive Knowledge Graph Statistics")
    print(f"   Input: {INPUT_FILE.name}\n")

    # Read file
    print("📖 Reading file...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Extract prefixes
    prefixes = []
    for line in lines[:50]:
        if line.strip().startswith('@prefix'):
            prefixes.append(line)
    prefix_block = ''.join(prefixes)

    # Test each category
    categories = [
        (r'^srs-kg:word-zh-', "Chinese Words"),
        (r'^srs-kg:word-en-', "English Words"),
        (r'^srs-kg:char-', "Chinese Characters"),
        (r'^srs-kg:concept-', "Concepts"),
        (r'^srs-kg:pinyin-', "Pinyin Syllables"),
        (r'^srs-inst:gp-', "Grammar Points"),
        (r'^srs-inst:sent-', "Sentences"),
    ]

    results = []
    for pattern, name in categories:
        total, valid, broken = extract_and_test_category(lines, prefix_block, pattern, name)
        results.append((name, total, valid, broken))

    # Summary table
    print(f"\n\n{'='*70}")
    print("📋 SUMMARY")
    print(f"{'='*70}")
    print(f"{'Category':<25} {'Total':>10} {'Valid':>10} {'Broken':>10} {'Success':>10}")
    print(f"{'-'*70}")

    grand_total = 0
    grand_valid = 0
    grand_broken = 0

    for name, total, valid, broken in results:
        success = f"{(valid/total*100):.1f}%" if total > 0 else "N/A"
        print(f"{name:<25} {total:>10,} {valid:>10,} {broken:>10,} {success:>10}")
        grand_total += total
        grand_valid += valid
        grand_broken += broken

    print(f"{'-'*70}")
    grand_success = f"{(grand_valid/grand_total*100):.1f}%" if grand_total > 0 else "N/A"
    print(f"{'TOTAL':<25} {grand_total:>10,} {grand_valid:>10,} {grand_broken:>10,} {grand_success:>10}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
