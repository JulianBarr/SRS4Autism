import sqlite3
import json
import re
import os

# ================= CONFIGURATION =================
DB_PATH = 'data/srs4autism.db'           # Your SQLite file
TTL_PATH = 'knowledge_graph/world_model_complete.ttl'    # Your Turtle file
RAINBOW_PATH = 'migration_log.json' # The mapping file you provided sample of
TABLE_NAME = 'media'          # Table name in DB
ID_COLUMN = 'id'              # Column name in DB

# Regex for the NEW format: 12 hex chars followed by an extension
# Matches: 09060a5ef146.jpg
NEW_ID_PATTERN = re.compile(r'^[a-fA-F0-9]{12}\.(jpg|jpeg|png|gif)$', re.IGNORECASE)
# =================================================

def load_rainbow(path):
    """Loads the rainbow table JSON."""
    if not os.path.exists(path):
        print(f"[!] Rainbow table not found at {path}")
        return {}, set()
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Return: 
            # 1. Map: { "content/old/path.jpg": "new_hash.jpg" }
            # 2. Set of all valid new filenames for quick lookup
            valid_new_ids = set(data.values())
            return data, valid_new_ids
    except json.JSONDecodeError as e:
        print(f"[!] JSON Error: {e}")
        return {}, set()

def get_db_ids(db_path):
    """Fetches IDs from DB."""
    if not os.path.exists(db_path):
        return set()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT {ID_COLUMN} FROM {TABLE_NAME}")
        ids = {str(row[0]).strip() for row in cursor.fetchall()}
        conn.close()
        return ids
    except Exception as e:
        print(f"[!] DB Error: {e}")
        return set()

def get_ttl_ids(ttl_path):
    """Rough scan of TTL for IDs (both old paths and new hashes)."""
    if not os.path.exists(ttl_path):
        return set()
    
    ids = set()
    # Simple token extraction to catch filenames/paths inside < > or " "
    with open(ttl_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Find strings ending in .jpg/.png inside quotes or brackets
        # Matches: "09060a5ef146.jpg" OR <content/media/images/foo.jpg>
        matches = re.findall(r'["<]([\w\-/]+\.(?:jpg|png|jpeg))[" >]', content, re.IGNORECASE)
        ids.update(matches)
    return ids

def main():
    print("--- CUMA Migration Audit ---")
    
    # 1. Load Data
    print("Loading Rainbow Table...")
    rainbow_map, rainbow_values = load_rainbow(RAINBOW_PATH)
    print(f" -> Loaded {len(rainbow_map)} mappings.")

    print("Loading DB IDs...")
    db_ids = get_db_ids(DB_PATH)
    print(f" -> Found {len(db_ids)} rows in DB.")
    
    # 2. Analyze DB Content
    migrated_count = 0
    pending_ids = []      # In DB as Old Path, Hash EXISTS in Rainbow
    lost_ids = []         # In DB as Old Path, Hash MISSING from Rainbow
    unknown_ids = []      # Doesn't look like either
    
    for item in db_ids:
        if NEW_ID_PATTERN.match(item):
            migrated_count += 1
        elif item in rainbow_map:
            pending_ids.append(item)
        else:
            # If it looks like a path/filename but isn't in rainbow map
            if "/" in item or "." in item:
                lost_ids.append(item)
            else:
                unknown_ids.append(item)

    # 3. Report
    print("\n" + "="*40)
    print("       STATUS REPORT")
    print("="*40)
    
    print(f"\n[DONE] Already Migrated: {migrated_count} items")
    
    if pending_ids:
        print(f"\n[PENDING] {len(pending_ids)} items in DB need updates (Hash exists in Rainbow):")
        print("   (These can be automatically updated via SQL)")
        for x in pending_ids[:3]: print(f"   - {x}  -> {rainbow_map[x]}")
        
    if lost_ids:
        print(f"\n[DANGER] {len(lost_ids)} items in DB are Old Paths but NOT in Rainbow Table:")
        print("   (You need to find these files and generate hashes for them)")
        for x in lost_ids[:5]: print(f"   - {x}")

    if unknown_ids:
        print(f"\n[UNKNOWN] {len(unknown_ids)} weird IDs (neither hash nor known path):")
        for x in unknown_ids[:3]: print(f"   ? {x}")

    # 4. Quick TTL Check
    ttl_ids = get_ttl_ids(TTL_PATH)
    ttl_legacy = [x for x in ttl_ids if x in rainbow_map]
    
    if ttl_legacy:
        print(f"\n[TTL Check] Your TTL file still contains {len(ttl_legacy)} old paths.")
        print("   Example: " + ttl_legacy[0])

if __name__ == "__main__":
    main()
