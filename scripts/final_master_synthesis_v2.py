#!/usr/bin/env python3
"""
FINAL MASTER SYNTHESIS SCRIPT V2
=================================
This version uses a different strategy:
1. Process RDF blocks (triples ending with .)
2. For each block, identify the SUBJECT zone and clean it aggressively
3. Then mask literals in the PREDICATE/OBJECT zone
4. Join metadata and save

This prevents the "vault markers in URIs" problem.
"""

import re
from pathlib import Path
import time

# ============================================================================
# SETTINGS
# ============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_41M = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
COMPLETE_11M = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
FINAL_MASTER = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def slugify_uri(text):
    """
    Converts a messy URI into a clean RDF slug.
    PRESERVES: hyphens (-) and colons (:) for namespace bindings
    REPLACES: spaces, quotes, parentheses, etc. with underscores
    """
    text = re.sub(r'[^a-zA-Z0-9:-]', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')

# ============================================================================
# MAIN SYNTHESIS LOGIC
# ============================================================================

def main():
    start_time = time.time()
    print(f"🚀 Starting Final Master Synthesis V2...")

    # ========================================================================
    # STEP 1: INDEX METADATA FROM 11MB FILE
    # ========================================================================
    print("\n📚 Step 1: Indexing metadata from enrichment file...")
    meta_lookup = {}

    with open(COMPLETE_11M, 'r', encoding='utf-8') as f:
        content_11m = f.read()
        blocks = re.split(r'\s*\.\s*\n', content_11m)

        for block in blocks:
            zh_labels = re.findall(r'"([^"]+)"@zh', block)
            wd_match = re.search(r'wikidataId\s+"(Q\d+)"', block)
            hsk_match = re.search(r'hskLevel\s+(\d+)', block)

            if zh_labels and (wd_match or hsk_match):
                metadata = {
                    'wd': wd_match.group(1) if wd_match else None,
                    'hsk': hsk_match.group(1) if hsk_match else None
                }
                for zh_char in zh_labels:
                    if zh_char not in meta_lookup:
                        meta_lookup[zh_char] = metadata

    print(f"   ✓ Indexed {len(meta_lookup)} Chinese entries")

    # ========================================================================
    # STEP 2: READ LEGACY FILE AND PROCESS BLOCKS
    # ========================================================================
    print("\n📖 Step 2: Reading legacy file...")

    with open(BACKUP_41M, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into lines for header processing
    lines = content.split('\n')
    headers = []
    body_start = 0

    # Extract @prefix headers
    for i, line in enumerate(lines):
        if line.strip().startswith('@prefix'):
            headers.append(line)
        elif line.strip() and not line.strip().startswith('@'):
            body_start = i
            break

    # Rejoin body
    body = '\n'.join(lines[body_start:])

    print(f"   ✓ Extracted {len(headers)} prefix headers")

    # ========================================================================
    # STEP 3: PROCESS BLOCKS AND CLEAN SUBJECT ZONES
    # ========================================================================
    print("\n🛠  Step 3: Processing RDF blocks...")

    # Split into RDF blocks (each ends with .)
    # Use a more careful split that doesn't break on periods in literals
    blocks = []
    current_block = []
    in_string = False
    escape_next = False

    for line in body.split('\n'):
        stripped = line.strip()

        # Track if we're inside a string literal
        for char in line:
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
            elif char == '"':
                in_string = not in_string

        current_block.append(line)

        # If line ends with . and we're not in a string, it's end of block
        if stripped.endswith('.') and not in_string:
            blocks.append('\n'.join(current_block))
            current_block = []

    # Add any remaining
    if current_block:
        blocks.append('\n'.join(current_block))

    print(f"   ✓ Split into {len(blocks)} RDF blocks")

    # ========================================================================
    # STEP 4: CLEAN EACH BLOCK
    # ========================================================================
    print("\n🧹 Step 4: Cleaning blocks...")

    cleaned_blocks = []
    injection_count = 0
    debug_block_found = False

    for i, block in enumerate(blocks):
        # Strip leading/trailing whitespace from block
        block = block.strip()

        if not block:
            continue

        # Check if this block has a subject line (starts with srs-inst: or srs-kg:)
        first_line = block.split('\n')[0].strip()

        # Debug output for problematic block
        if 'gp-A1-019' in block and not debug_block_found:
            print(f"\n🔍 DEBUG: Found gp-A1-019 at block {i}")
            print(f"   First line: {first_line[:80]}")
            debug_block_found = True

        if first_line.startswith('srs-inst:') or first_line.startswith('srs-kg:'):
            # This is a subject block - need to clean the subject zone

            # Find where the subject ends (at first occurrence of ' a ' or ' ;')
            # Split the block into subject line(s) and the rest
            match = re.search(r'^(.*?\s+)(a\s+|;\s+)(.*)', block, re.DOTALL | re.MULTILINE)

            if match:
                subject_part = match.group(1).strip()
                separator = match.group(2)
                rest_of_block = match.group(3)

                # Clean the subject URI
                def clean_subject_uri(m):
                    namespace = m.group(1)
                    local_part = m.group(2)
                    cleaned = slugify_uri(local_part)
                    if 'gp-A1-019' in local_part:
                        print(f"   🧹 Cleaning subject URI:")
                        print(f"      Original: {namespace}{local_part}")
                        print(f"      Cleaned:  {namespace}{cleaned}")
                    return namespace + cleaned

                # Match the entire URI in subject position
                # Pattern: srs- namespace + everything until whitespace
                subject_part_before = subject_part
                subject_part = re.sub(
                    r'(srs-(?:inst|kg):)([^\s]+(?:\s+(?!a\s|;\s|,|\.)[^\s]+)*)',
                    clean_subject_uri,
                    subject_part
                )

                if 'gp-A1-019' in block:
                    print(f"   Subject before: {subject_part_before[:80]}")
                    print(f"   Subject after:  {subject_part[:80]}")

                # Also clean any other srs URIs in the rest of the block
                def clean_object_uri(m):
                    namespace = m.group(1)
                    local_part = m.group(2)
                    # Don't touch if it looks like it's before a string literal
                    return namespace + slugify_uri(local_part)

                rest_of_block = re.sub(
                    r'(srs-(?:inst|kg):)([^\s"]+)',
                    clean_object_uri,
                    rest_of_block
                )

                # Reconstruct block
                block = subject_part + ' ' + separator + rest_of_block

        # ====================================================================
        # STEP 5: INJECT METADATA
        # ====================================================================

        # Check for Chinese labels
        zh_matches = re.findall(r'"([^"]+)"@zh', block)

        if zh_matches:
            for zh_char in zh_matches:
                if zh_char in meta_lookup:
                    meta = meta_lookup[zh_char]

                    # Only inject if not already present
                    if meta['wd'] and 'wikidataId' not in block:
                        # Remove trailing period
                        block = block.rstrip(' .')
                        block += f' ;\n    srs-kg:wikidataId "{meta["wd"]}"'
                        injection_count += 1

                    if meta['hsk'] and 'hskLevel' not in block:
                        if not block.rstrip().endswith(';'):
                            block = block.rstrip(' .') + ' ;'
                        block += f'\n    srs-kg:hskLevel {meta["hsk"]}'

                    # Re-add period
                    if not block.rstrip().endswith('.'):
                        block = block.rstrip() + ' .'

                    break  # Only inject once per block

        cleaned_blocks.append(block)

    print(f"   ✓ Cleaned {len(cleaned_blocks)} blocks")
    print(f"   ✓ Injected metadata into {injection_count} entries")

    # ========================================================================
    # STEP 6: SAVE FINAL OUTPUT
    # ========================================================================
    print("\n💾 Step 6: Saving final master file...")

    output = '\n'.join(headers) + '\n\n' + '\n\n'.join(cleaned_blocks)

    with open(FINAL_MASTER, 'w', encoding='utf-8') as f:
        f.write(output)

    elapsed = time.time() - start_time
    final_size = FINAL_MASTER.stat().st_size / 1e6

    print(f"\n{'='*70}")
    print(f"✅ SUCCESS!")
    print(f"{'='*70}")
    print(f"   Output: {FINAL_MASTER.name}")
    print(f"   Size: {final_size:.1f}MB")
    print(f"   Time: {elapsed:.1f}s")
    print(f"\n🎯 Next step: Run audit with 'python scripts/audit_final_kg.py'")

if __name__ == "__main__":
    main()
