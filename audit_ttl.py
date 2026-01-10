import re
import json
import os

# ================= CONFIGURATION =================
# Updated with your specific paths
TTL_FILE = 'knowledge_graph/world_model_complete.ttl'
RAINBOW_FILE = 'migration_log.json'

# Regex 1: Matches the NEW format (12 hex chars + extension)
# Checks for broken hash links
HASH_PATTERN = re.compile(r'\b([a-fA-F0-9]{12}\.(?:jpg|png|gif|jpeg))\b', re.IGNORECASE)

# Regex 2: Matches the OLD format (Semantic paths)
# Detects things that still look like "content/media/images/..."
LEGACY_PATTERN = re.compile(r'["<](content/media/[a-zA-Z0-9_/\-\.]+\.(?:jpg|png|jpeg))[" >]', re.IGNORECASE)
# =================================================

def main():
    print(f"--- SRS4Autism TTL Audit ---")
    print(f"Target: {TTL_FILE}")

    # 1. Load Rainbow Table
    if not os.path.exists(RAINBOW_FILE):
        print(f"[!] Error: Rainbow file not found at {RAINBOW_FILE}")
        return

    print("Loading migration log...")
    try:
        with open(RAINBOW_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Map: { "content/media/old.jpg": "a1b2c3d4e5f6.jpg" }
            legacy_map = data
            # Set of valid result hashes
            valid_hashes = set(data.values())
            print(f" -> Loaded {len(data)} mappings.")
    except Exception as e:
        print(f"[!] JSON Error: {e}")
        return

    # 2. Scan TTL File
    if not os.path.exists(TTL_FILE):
        print(f"[!] Error: TTL file not found at {TTL_FILE}")
        return

    print("Scanning TTL file...")
    found_hashes = set()     # Hashes found in TTL
    found_legacy = set()     # Old paths found in TTL
    
    with open(TTL_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            # Check for Hashes
            hashes = HASH_PATTERN.findall(line)
            found_hashes.update(hashes)
            
            # Check for Legacy Paths
            paths = LEGACY_PATTERN.findall(line)
            found_legacy.update(paths)

    # 3. Analyze Results
    
    # Category A: Migratable vs Lost Legacy Paths
    migratable = []
    lost_legacy = []
    
    for path in found_legacy:
        if path in legacy_map:
            migratable.append(path)
        else:
            lost_legacy.append(path)

    # Category B: Broken Hashes (Integrity Check)
    broken_hashes = found_hashes - valid_hashes

    # 4. Report
    print("\n" + "="*40)
    print("       AUDIT REPORT")
    print("="*40)

    # REPORT 1: LEGACY PATHS
    if found_legacy:
        print(f"\n[ACTION REQUIRED] Found {len(found_legacy)} legacy paths.")
        print(f"  - {len(migratable)} can be AUTO-PATCHED (Mapping exists).")
        
        if lost_legacy:
            print(f"  - {len(lost_legacy)} are UNKNOWN (No mapping found).")
            print(f"    [Sample]: {lost_legacy[0]}")
    else:
        print("\n[OK] No legacy paths found in TTL. It is fully migrated.")

    # REPORT 2: BROKEN HASHES
    if broken_hashes:
        print(f"\n[DANGER] Found {len(broken_hashes)} hashes in TTL that do NOT exist in migration log:")
        for x in list(broken_hashes)[:5]:
            print(f"  - {x}")
    else:
        print(f"\n[PERFECT] All {len(found_hashes)} hashes in TTL are valid.")

if __name__ == "__main__":
    main()
