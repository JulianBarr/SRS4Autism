import re
import json
import os

# ================= CONFIGURATION =================
TTL_FILE = 'knowledge_graph/world_model_complete.ttl'
RAINBOW_FILE = 'migration_log.json'

# Regex to capture the FILENAME at the end of your path
# Matches: 15608711e5c9.jpg from content/media/objects/15608711e5c9.jpg
FILENAME_PATTERN = re.compile(r'content/media/objects/([a-fA-F0-9]{12}\.(?:jpg|png|gif|jpeg))', re.IGNORECASE)
# =================================================

def main():
    print("--- CUMA TTL Integrity Verification ---")
    
    # 1. Load Valid Hashes
    print(f"Loading {RAINBOW_FILE}...")
    valid_hashes = set()
    try:
        with open(RAINBOW_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            valid_hashes = set(data.values()) # We check against the VALUES (the new hashes)
    except Exception as e:
        print(f"Error: {e}")
        return

    # 2. Scan TTL
    print(f"Scanning {TTL_FILE}...")
    ttl_hashes = set()
    
    with open(TTL_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            matches = FILENAME_PATTERN.findall(line)
            ttl_hashes.update(matches)

    # 3. Check Integrity
    unknown_hashes = ttl_hashes - valid_hashes

    print("\n" + "="*40)
    print("       INTEGRITY REPORT")
    print("="*40)
    
    print(f"Total References Found: {len(ttl_hashes)}")
    
    if len(unknown_hashes) == 0:
        print(f"\n[SUCCESS] All {len(ttl_hashes)} files referenced in TTL correspond to valid hashes in your migration log.")
        print("Your TTL file is CLEAN. No changes needed.")
    else:
        print(f"\n[WARNING] Found {len(unknown_hashes)} files in TTL that are NOT in the migration log:")
        for x in list(unknown_hashes)[:5]:
            print(f"  - {x}")

if __name__ == "__main__":
    main()
