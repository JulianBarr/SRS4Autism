#!/usr/bin/env python3
"""
FINAL MASTER SYNTHESIS SCRIPT
==============================
This script creates world_model_final_master.ttl by:
1. Vaulting valid RDF string literals (masking)
2. Surgically cleaning all URIs (subject zones and objects)
3. Injecting metadata from enrichment file (wikidataId, hskLevel)
4. Unmasking and saving

This uses the "Stateful Tokenizer" approach to treat the file as structured data,
not as text, preventing the destruction of Chinese content.
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
    REPLACES: spaces, quotes, parentheses, percent signs with underscores
    """
    # Replace anything NOT alphanumeric, colon, or hyphen with underscore
    text = re.sub(r'[^a-zA-Z0-9:-]', '_', text)
    # Collapse multiple underscores
    text = re.sub(r'_+', '_', text)
    # Strip leading/trailing underscores
    return text.strip('_')

def extract_prefix(line):
    """Extract namespace prefix declarations."""
    match = re.match(r'^@prefix\s+(\S+):\s+<([^>]+)>\s*\.$', line.strip())
    if match:
        return (match.group(1), match.group(2))
    return None

# ============================================================================
# MAIN SYNTHESIS LOGIC
# ============================================================================

def main():
    start_time = time.time()
    print(f"🚀 Starting Final Master Synthesis...")
    print(f"   Base: {BACKUP_41M.name} ({BACKUP_41M.stat().st_size / 1e6:.1f}MB)")
    print(f"   Enrichment: {COMPLETE_11M.name} ({COMPLETE_11M.stat().st_size / 1e6:.1f}MB)")

    # ========================================================================
    # STEP 1: INDEX METADATA FROM 11MB FILE
    # ========================================================================
    print("\n📚 Step 1: Indexing metadata from enrichment file...")
    meta_lookup = {}  # Maps Chinese character -> {wd: Q-ID, hsk: level}

    with open(COMPLETE_11M, 'r', encoding='utf-8') as f:
        content_11m = f.read()

        # Split into blocks (each block ends with .)
        blocks = re.split(r'\s*\.\s*\n', content_11m)

        for block in blocks:
            # Find all Chinese labels
            zh_labels = re.findall(r'"([^"]+)"@zh', block)

            # Find metadata
            wd_match = re.search(r'wikidataId\s+"(Q\d+)"', block)
            hsk_match = re.search(r'hskLevel\s+(\d+)', block)

            if zh_labels and (wd_match or hsk_match):
                metadata = {
                    'wd': wd_match.group(1) if wd_match else None,
                    'hsk': hsk_match.group(1) if hsk_match else None
                }

                # Index by each Chinese label found
                for zh_char in zh_labels:
                    if zh_char not in meta_lookup:
                        meta_lookup[zh_char] = metadata

    print(f"   ✓ Indexed {len(meta_lookup)} Chinese entries with metadata")

    # ========================================================================
    # STEP 2: READ LEGACY FILE AND MASK STRING LITERALS
    # ========================================================================
    print("\n🎭 Step 2: Vaulting string literals...")

    with open(BACKUP_41M, 'r', encoding='utf-8') as f:
        content = f.read()

    # Vault for storing masked literals
    literal_vault = []

    def mask_literal(match):
        """Replace valid RDF string literal with placeholder."""
        literal_vault.append(match.group(0))
        return f"%%VAULT{len(literal_vault)-1}%%"

    # Mask ALL valid RDF string literals:
    # - "text"@lang (e.g., "你好"@zh, "hello"@en)
    # - "text"^^<datatype> (e.g., "123"^^xsd:integer)
    # - "text" (plain string literal)
    # This uses a regex that handles escaped quotes inside strings
    # Pattern matches: "..." followed by optional @lang or ^^datatype
    literal_pattern = r'"(?:[^"\\]|\\.)*"(?:@[a-zA-Z][-a-zA-Z]*|\^\^<[^>]+>)?'
    content = re.sub(literal_pattern, mask_literal, content)

    print(f"   ✓ Vaulted {len(literal_vault)} string literals")

    # ========================================================================
    # STEP 3: PROCESS LINE-BY-LINE, CLEANING URIS
    # ========================================================================
    print("\n🛠  Step 3: Surgical URI cleaning...")

    lines = content.split('\n')
    cleaned_lines = []
    prefixes = {}  # Store namespace prefixes

    for line in lines:
        stripped = line.strip()

        # Handle empty lines
        if not stripped:
            cleaned_lines.append('')
            continue

        # Handle @prefix declarations - DO NOT MODIFY
        prefix_info = extract_prefix(line)
        if prefix_info:
            prefix_name, prefix_uri = prefix_info
            prefixes[prefix_name] = prefix_uri
            cleaned_lines.append(line)
            continue

        # For all other lines, clean URIs
        # Strategy: Find all URIs (srs-inst:xxx or srs-kg:xxx) and slugify them
        # Pattern matches URI local parts including spaces until RDF keywords
        def clean_uri(match):
            """Clean a URI, preserving vault markers."""
            namespace = match.group(1)  # 'srs-inst:' or 'srs-kg:'
            local_part = match.group(2)  # The part after the colon

            # If local part contains vault markers, it's already protected
            if '%%VAULT' in local_part:
                return match.group(0)

            # Slugify the local part
            cleaned = slugify_uri(local_part)
            return namespace + cleaned

        # Clean all URIs in the line
        # This pattern matches: namespace + (non-space OR space+non-keyword)+
        # It stops at space followed by RDF keywords: a, ;, comma, period, brackets
        line = re.sub(r'(srs-(?:inst|kg):)(\S+(?:\s+(?!a\s|;\s*$|,|\.|\[|\])\S+)*)', clean_uri, line)

        cleaned_lines.append(line)

    # Rejoin into single content
    content = '\n'.join(cleaned_lines)
    print(f"   ✓ Cleaned URIs across {len(cleaned_lines)} lines")

    # ========================================================================
    # STEP 4: INJECT METADATA FROM 11MB FILE
    # ========================================================================
    print("\n💉 Step 4: Injecting metadata...")

    # Split into RDF blocks for metadata injection
    blocks = re.split(r'\s*\.\s*\n', content)
    enriched_blocks = []
    injection_count = 0

    for block in blocks:
        if not block.strip():
            continue

        # Check if block has a Chinese label with vault marker
        zh_vault_match = re.search(r'%%VAULT(\d+)%%', block)

        if zh_vault_match:
            vault_idx = int(zh_vault_match.group(1))
            # Get the original literal from vault
            original = literal_vault[vault_idx]

            # Extract Chinese character if it's a @zh label
            if '@zh' in original:
                zh_char = re.search(r'"([^"]+)"@zh', original)
                if zh_char:
                    char = zh_char.group(1)

                    # Look up metadata
                    if char in meta_lookup:
                        meta = meta_lookup[char]

                        # Inject metadata
                        # Remove trailing period if present
                        block = block.rstrip(' .')

                        # Add metadata properties
                        if meta['wd']:
                            block += f' ;\n    srs-kg:wikidataId "{meta["wd"]}"'
                            injection_count += 1

                        if meta['hsk']:
                            block += f' ;\n    srs-kg:hskLevel {meta["hsk"]}'

        # Add block with proper termination
        enriched_blocks.append(block.rstrip(' .') + ' .')

    print(f"   ✓ Injected metadata into {injection_count} entries")

    # ========================================================================
    # STEP 5: UNMASK STRING LITERALS
    # ========================================================================
    print("\n🔓 Step 5: Unmasking string literals...")

    # Rejoin blocks
    result = '\n\n'.join(enriched_blocks)

    # Unmask all vault markers
    def unmask_literal(match):
        vault_idx = int(match.group(1))
        return literal_vault[vault_idx]

    result = re.sub(r'%%VAULT(\d+)%%', unmask_literal, result)

    # ========================================================================
    # STEP 6: FINAL CLEANUP (removed syntax hardening - too aggressive)
    # ========================================================================
    print("\n🔧 Step 6: Final cleanup...")

    # ========================================================================
    # STEP 7: SAVE FINAL OUTPUT
    # ========================================================================
    print("\n💾 Step 7: Saving final master file...")

    with open(FINAL_MASTER, 'w', encoding='utf-8') as f:
        f.write(result)

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
