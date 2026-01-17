#!/usr/bin/env python3
"""
STRATEGIC FILTER: Skip Grammar Points and Sentences
====================================================
Skip the problematic grammar points and sentences.
Keep: Characters, Words, Concepts, and core vocabulary.

This eliminates most malformed URIs which are in grammar/sentence IDs.
"""

import re
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_preprocessed.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_vocabulary_only.ttl"

def main():
    start_time = time.time()
    print(f"🎯 Strategic Filter: Extracting Vocabulary (skip grammar/sentences)...")
    print(f"   Input:  {INPUT_FILE.name}")
    print(f"   Output: {OUTPUT_FILE.name}")

    # Statistics
    total_lines = 0
    kept_lines = 0
    skipped_blocks = 0
    kept_blocks = 0

    current_block = []
    in_skip_block = False
    last_was_empty = False

    with open(INPUT_FILE, 'r', encoding='utf-8') as infile, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:

        for line in infile:
            total_lines += 1
            stripped = line.strip()

            # Handle prefix headers - always keep
            if stripped.startswith('@prefix'):
                outfile.write(line)
                kept_lines += 1
                continue

            # Empty line can signal end of block
            if not stripped:
                if current_block and not in_skip_block:
                    outfile.writelines(current_block)
                    outfile.write(line)  # Write the empty line too
                    kept_lines += len(current_block) + 1
                    kept_blocks += 1
                elif current_block and in_skip_block:
                    skipped_blocks += 1
                current_block = []
                in_skip_block = False
                last_was_empty = True
                continue

            # Detect start of new block (non-indented line after empty or start)
            if not line.startswith(' ') and not line.startswith('\t'):
                # Process previous block if exists
                if current_block:
                    if not in_skip_block:
                        outfile.writelines(current_block)
                        kept_lines += len(current_block)
                        kept_blocks += 1
                    else:
                        skipped_blocks += 1
                    current_block = []

                # Check if this new block should be skipped
                # Skip grammar points: srs-inst:gp-*
                # Skip sentences: srs-inst:sent-*
                if re.match(r'^\s*srs-inst:(gp-|sent-)', stripped):
                    in_skip_block = True
                else:
                    in_skip_block = False

            # Accumulate lines for current block
            current_block.append(line)
            last_was_empty = False

            # Progress
            if total_lines % 100000 == 0:
                print(f"   Processed {total_lines:,} lines... (kept {kept_blocks:,} blocks, skipped {skipped_blocks:,})")

        # Handle last block
        if current_block and not in_skip_block:
            outfile.writelines(current_block)
            kept_lines += len(current_block)
            kept_blocks += 1

    elapsed = time.time() - start_time
    output_size = OUTPUT_FILE.stat().st_size / 1e6
    reduction = ((total_lines - kept_lines) / total_lines) * 100

    print(f"\n{'='*70}")
    print(f"✅ FILTERING COMPLETE!")
    print(f"{'='*70}")
    print(f"   Total lines: {total_lines:,}")
    print(f"   Kept lines: {kept_lines:,}")
    print(f"   Reduction: {reduction:.1f}%")
    print(f"   Blocks kept: {kept_blocks:,}")
    print(f"   Blocks skipped: {skipped_blocks:,}")
    print(f"   Output size: {output_size:.1f}MB")
    print(f"   Time: {elapsed:.1f}s")
    print(f"\n🎯 Next: Run master_synthesis.py on vocabulary-only file")

if __name__ == "__main__":
    main()
