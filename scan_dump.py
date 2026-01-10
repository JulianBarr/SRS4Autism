import re
import json
import os

# ================= CONFIGURATION =================
DUMP_FILE = 'data/srs4autism.sql'    # The file you generated in Phase 1
RAINBOW_FILE = 'migration_log.json'     # Your existing mapping file
TTL_FILE = 'knowledge_graph/world_model_complete.ttl'        # Optional: Check TTL if available

# Regex to catch your specific file patterns inside SQL statements
# Captures strings ending in common image extensions
# Group 1 will be the filename/path
PATH_PATTERN = re.compile(r'[\'"]([a-zA-Z0-9_/\-\.]+\.(?:jpg|png|jpeg|gif))[\'"]', re.IGNORECASE)

# Regex for your NEW short hash format (12 hex chars + extension)
HASH_PATTERN = re.compile(r'^[a-fA-F0-9]{12}\.(?:jpg|png|jpeg|gif)$', re.IGNORECASE)
# =================================================

def load_rainbow(path):
    if not os.path.exists(path):
        print(f"[!] Rainbow table missing: {path}")
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def scan_file(filepath, description):
    """Scans a text file (SQL dump or TTL) for paths and hashes."""
    if not os.path.exists(filepath):
        print(f"[!] File missing: {filepath}")
        return [], []

    print(f"Scanning {description}...")
    found_hashes = []
    found_paths = []
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            # Fast filter: skip lines that definitely don't have filenames
            if '.jpg' not in line and '.png' not in line: 
                continue
                
            matches = PATH_PATTERN.findall(line)
            for m in matches:
                if HASH_PATTERN.match(m):
                    found_hashes.append(m)
                else:
                    found_paths.append(m)
                    
    return found_hashes, found_paths

def main():
    print("--- Universal Dump Scanner ---")
    
    # 1. Load the Map
    rainbow = load_rainbow(RAINBOW_FILE)
    print(f"Loaded {len(rainbow)} mappings from Rainbow Table.\n")

    # 2. Scan the SQL Dump
    db_hashes, db_paths = scan_file(DUMP_FILE, "SQL Dump")
    
    # 3. Scan the TTL (Optional)
    ttl_hashes, ttl_paths = scan_file(TTL_FILE, "TTL Graph")

    # 4. Analyze "Pending" vs "Lost"
    # "Pending": Found in Dump as old path, BUT we have a mapping for it.
    pending_migration = []
    # "Lost": Found in Dump as old path, and we DO NOT have a mapping.
    lost_files = []

    for path in set(db_paths):
        # Clean up path (sometimes SQL dump escaping adds slashes)
        clean_path = path.replace('\\', '') 
        if clean_path in rainbow:
            pending_migration.append(clean_path)
        else:
            lost_files.append(clean_path)

    # 5. Report
    print("\n" + "="*40)
    print("       AUDIT REPORT")
    print("="*40)

    print(f"\n[DB STATE] Total References Found: {len(db_hashes) + len(db_paths)}")
    print(f"  - Already Migrated (Short Hashes): {len(set(db_hashes))}")
    print(f"  - Legacy Paths (Need Fix):         {len(set(db_paths))}")

    if pending_migration:
        print(f"\n[ACTIONABLE] {len(pending_migration)} items found in DB can be auto-migrated.")
        print("  (These exist in your Rainbow Table)")
        print(f"  Sample: {pending_migration[0]} -> {rainbow.get(pending_migration[0])}")

    if lost_files:
        print(f"\n[CRITICAL] {len(lost_files)} items in DB are completely unknown (No Rainbow match).")
        print("  These might be typos, old test data, or files you forgot to hash.")
        for x in lost_files[:5]:
            print(f"  [?] {x}")
            
    if ttl_paths:
         print(f"\n[TTL WARNING] Your TTL file still contains {len(set(ttl_paths))} legacy paths.")

if __name__ == "__main__":
    main()
