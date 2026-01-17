#!/usr/bin/env python3
"""
BOPOMOFO URI PRE-PROCESSOR
===========================
This script fixes malformed URIs that contain spaces and bopomofo annotations.

Examples of malformed URIs:
- srs-kg:pinyin- (ㄒㄧㄥˊ)5
- srs-kg:char-行 (ㄒㄧㄥˊ)
- srs-kg:concept-同行 (ㄒㄧㄥˊ)-14626801

These get cleaned to remove the bopomofo annotations while preserving structure:
- srs-kg:pinyin-_5 (or just srs-kg:pinyin-5)
- srs-kg:char-行
- srs-kg:concept-同行-14626801

Strategy:
1. Find patterns like: srs-XX:something space (bopomofo) suffix
2. Remove the space and bopomofo annotation
3. Preserve any suffix after the bopomofo
"""

import re
from pathlib import Path
import time

# ============================================================================
# SETTINGS
# ============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_preprocessed.ttl"

# ============================================================================
# BOPOMOFO DETECTION
# ============================================================================

# Unicode ranges for Bopomofo characters (ㄅㄆㄇㄈ etc)
# Bopomofo: U+3105 to U+312F
# Bopomofo Extended: U+31A0 to U+31BF
BOPOMOFO_PATTERN = r'[\u3105-\u312F\u31A0-\u31BF]'

def contains_bopomofo(text):
    """Check if text contains bopomofo characters."""
    return re.search(BOPOMOFO_PATTERN, text) is not None

# ============================================================================
# URI CLEANING
# ============================================================================

def clean_malformed_uri(match):
    """
    Clean a malformed URI with bopomofo annotation.

    Input: srs-kg:pinyin- (ㄒㄧㄥˊ)5
    Output: srs-kg:pinyin-5

    Input: srs-kg:concept-同行 (ㄒㄧㄥˊ)-14626801
    Output: srs-kg:concept-同行-14626801
    """
    namespace = match.group(1)  # e.g., "srs-kg:"
    prefix = match.group(2)     # e.g., "pinyin-" or "concept-同行"
    annotation = match.group(3)  # e.g., " (ㄒㄧㄥˊ)"
    suffix = match.group(4) if len(match.groups()) >= 4 else ""  # e.g., "5" or "-14626801"

    # Remove trailing space from prefix if present
    prefix = prefix.rstrip()

    # If suffix is just a number or dash-number, keep it
    # Otherwise might be continuation of the text
    result = namespace + prefix + suffix

    return result

def clean_quotes_in_uri(match):
    """
    Remove quotes from URIs.

    Input: srs-inst:gp-A2-061-"When" with "de shihou"
    Output: srs-inst:gp-A2-061-When_with_de_shihou
    """
    namespace = match.group(1)
    uri_part = match.group(2)

    # Remove quotes and replace spaces with underscores in the URI part
    uri_part = uri_part.replace('"', '').replace(' ', '_')

    return namespace + uri_part

def preprocess_line(line):
    """
    Pre-process a single line to fix malformed URIs.
    """
    # Pattern 1: srs-XX:text space (bopomofo) optional-suffix
    # This pattern matches URIs with spaces before bopomofo annotations
    # Match: namespace + non-whitespace-chars + space + (bopomofo-chars) + optional-suffix
    pattern1 = r'(srs-(?:inst|kg):)([^\s;,]+)\s+(\([^)]*' + BOPOMOFO_PATTERN + r'[^)]*\))([^\s;,]*)'
    line = re.sub(pattern1, clean_malformed_uri, line)

    # Pattern 2: srs-XX:text with quotes and spaces in SUBJECT or OBJECT position
    # Only match if:
    # - At start of line (subject position): ^\s*srs-...
    # - After a predicate expecting URI (object position): (hasExample|means|demonstratesGrammar|etc.) srs-...
    # This pattern handles: srs-inst:gp-A2-061-"When" with "de shihou"

    # Subject position: line starts with URI containing quotes
    if line.strip().startswith('srs-') and '"' in line and ' a ' in line:
        # Capture everything from namespace to just before ' a '
        pattern2 = r'^(\s*srs-(?:inst|kg):)(.+?)(?=\s+a\s)'
        line = re.sub(pattern2, clean_quotes_in_uri, line)

    # Object position: after predicates that expect URIs (not literals)
    # Look for patterns like: hasExample srs-inst:something-"with"-quotes
    uri_predicates = r'(?:hasExample|means|demonstratesGrammar|requiresPrerequisite|composedOf|isSynonymOf)'
    pattern3 = r'(' + uri_predicates + r'\s+)(srs-(?:inst|kg):)([^\s;,]+(?:\s+"[^"]*"[^\s;,]*)+)'
    if re.search(uri_predicates, line) and '"' in line:
        def clean_object_uri(m):
            predicate = m.group(1)
            namespace = m.group(2)
            uri_part = m.group(3)
            # Clean the URI part
            uri_part = uri_part.replace('"', '').replace(' ', '_')
            return predicate + namespace + uri_part
        line = re.sub(pattern3, clean_object_uri, line)

    return line

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    start_time = time.time()
    print(f"🔧 Starting Bopomofo URI Pre-processor...")
    print(f"   Input:  {INPUT_FILE.name}")
    print(f"   Output: {OUTPUT_FILE.name}")

    # Statistics
    total_lines = 0
    modified_lines = 0
    bopomofo_found = 0
    quotes_fixed = 0

    print(f"\n📖 Reading and processing...")

    with open(INPUT_FILE, 'r', encoding='utf-8') as infile, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:

        for line in infile:
            total_lines += 1
            original = line

            # Check if line needs processing
            needs_processing = False

            # Case 1: Line contains bopomofo
            if contains_bopomofo(line):
                bopomofo_found += 1
                needs_processing = True

            # Case 2 & 3: Disable - quoted URI handling is done in master_synthesis.py
            # (These cases were matching too broadly and mangling string literals)

            if needs_processing:
                # Try to clean malformed URIs
                line = preprocess_line(line)

                if line != original:
                    modified_lines += 1
                    if modified_lines <= 20:  # Show first 20 examples
                        print(f"\n   Example {modified_lines}:")
                        print(f"   Before: {original.strip()[:100]}")
                        print(f"   After:  {line.strip()[:100]}")

            outfile.write(line)

            # Progress indicator
            if total_lines % 100000 == 0:
                print(f"   Processed {total_lines:,} lines...")

    elapsed = time.time() - start_time
    output_size = OUTPUT_FILE.stat().st_size / 1e6

    print(f"\n{'='*70}")
    print(f"✅ PRE-PROCESSING COMPLETE!")
    print(f"{'='*70}")
    print(f"   Total lines: {total_lines:,}")
    print(f"   Lines with bopomofo: {bopomofo_found:,}")
    print(f"   Lines modified: {modified_lines:,}")
    print(f"   Output size: {output_size:.1f}MB")
    print(f"   Time: {elapsed:.1f}s")
    print(f"\n🎯 Next: Run master_synthesis.py with the preprocessed file")

if __name__ == "__main__":
    main()
