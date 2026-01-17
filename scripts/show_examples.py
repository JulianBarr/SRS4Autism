#!/usr/bin/env python3
"""
Show Examples of Valid and Broken Blocks
=========================================
Display 5 examples each of successful and broken blocks per category.
"""

import re
from pathlib import Path
from rdflib import Graph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_preprocessed.ttl"

def extract_examples(lines, prefix_block, pattern, category_name, max_examples=5):
    """Extract and categorize blocks, showing examples."""
    print(f"\n{'='*80}")
    print(f"📊 {category_name}")
    print(f"{'='*80}")

    blocks = []
    current_block = []
    in_block = False

    for line in lines:
        stripped = line.strip()

        if re.match(pattern, stripped):
            if current_block:
                blocks.append(''.join(current_block))
            current_block = [line]
            in_block = True
        elif in_block:
            if line and not line[0].isspace() and not stripped.startswith('@'):
                blocks.append(''.join(current_block))
                current_block = []
                in_block = False
                if re.match(pattern, stripped):
                    current_block = [line]
                    in_block = True
            else:
                current_block.append(line)

    if current_block and in_block:
        blocks.append(''.join(current_block))

    if len(blocks) == 0:
        print(f"   ⚠️  No blocks found")
        return

    # Categorize blocks
    valid_examples = []
    broken_examples = []

    for block in blocks:
        test_content = prefix_block + "\n\n" + block
        try:
            g = Graph()
            g.parse(data=test_content, format='turtle')
            if len(valid_examples) < max_examples:
                valid_examples.append(block)
        except Exception as e:
            if len(broken_examples) < max_examples:
                broken_examples.append((block, str(e)))

        # Stop early if we have enough examples
        if len(valid_examples) >= max_examples and len(broken_examples) >= max_examples:
            break

    # Display valid examples
    print(f"\n✅ VALID EXAMPLES ({len(valid_examples)}):")
    print(f"{'-'*80}")
    for i, block in enumerate(valid_examples, 1):
        print(f"\n[{i}]")
        # Show first 15 lines or full block if shorter
        lines = block.split('\n')[:15]
        print('\n'.join(lines))
        if len(block.split('\n')) > 15:
            print("    ...")

    # Display broken examples
    print(f"\n\n❌ BROKEN EXAMPLES ({len(broken_examples)}):")
    print(f"{'-'*80}")
    for i, (block, error) in enumerate(broken_examples, 1):
        print(f"\n[{i}]")
        # Show first 15 lines or full block if shorter
        lines = block.split('\n')[:15]
        print('\n'.join(lines))
        if len(block.split('\n')) > 15:
            print("    ...")
        # Show error (first 200 chars)
        error_short = error[:200] + "..." if len(error) > 200 else error
        print(f"\n   ERROR: {error_short}")

def main():
    print("🔍 Extracting Examples from Knowledge Graph\n")

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

    # Categories to analyze
    categories = [
        (r'^srs-kg:word-zh-', "Chinese Words"),
        (r'^srs-kg:word-en-', "English Words"),
        (r'^srs-kg:char-', "Chinese Characters"),
        (r'^srs-kg:concept-', "Concepts"),
        (r'^srs-kg:pinyin-', "Pinyin Syllables"),
        (r'^srs-inst:gp-', "Grammar Points"),
        (r'^srs-inst:sent-', "Sentences"),
    ]

    for pattern, name in categories:
        extract_examples(lines, prefix_block, pattern, name, max_examples=5)

if __name__ == "__main__":
    main()
