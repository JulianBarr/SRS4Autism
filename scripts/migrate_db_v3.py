import sqlite3
import json
import re
import shutil
from pathlib import Path

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
MIGRATION_LOG = PROJECT_ROOT / "migration_log.json"
BACKUP_DB_PATH = DB_PATH.with_suffix(".db.v3_bak")

TABLES_TO_MIGRATE = [
    "chinese_word_recognition_notes",
    "english_word_recognition_notes",
    "pinyin_element_notes",
    "pinyin_syllable_notes",
    "character_recognition_notes"
]

NEW_MEDIA_URL_PREFIX = "/media/objects/"

def migrate_db_v3():
    print("=== Database Migration V3 (Case-Insensitive) ===")

    if not MIGRATION_LOG.exists():
        print(f"❌ Rainbow table not found: {MIGRATION_LOG}")
        return

    print("📖 Loading rainbow table...")
    with open(MIGRATION_LOG, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
        # Handle flattened log structure if necessary, or just use keys directly
        # The new script produces a flat map: "rel_path/file.jpg": "hash.jpg"
        raw_map = log_data
    
    # --- NORMALIZATION STEP ---
    # We create a lookup map where the KEY is lowercased filename.
    # { "lion.png": "hash..." }  becomes  { "lion.png": "hash..." }
    # { "path/to/Lion.PNG": "hash..." }  becomes  { "lion.png": "hash..." }
    
    filename_map = {}
    for k, v in raw_map.items():
        # k is likely "content/media/images/Lion.png"
        fname = Path(k).name.lower()
        filename_map[fname] = v  
        
    print(f"✅ Loaded {len(filename_map)} mappings (keys lowercased).")

    if DB_PATH.exists():
        print(f"📦 Backing up DB to {BACKUP_DB_PATH.name}...")
        shutil.copy2(DB_PATH, BACKUP_DB_PATH)
    else:
        print(f"❌ DB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Regex captures filename extension case-insensitively
    # Captures: src="apple.jpg", : "apple.jpg", [sound:apple.mp3]
    # Group 1: Prefix
    # Group 2: Filename
    # Group 3: Suffix
    pattern = re.compile(
        r'(src=\\?["\']|: \\?["\']|\[sound:)(?:/media/[^/\"\'\\]+/)?([^/\"\'\\]+\.(?:png|jpg|jpeg|gif|webp|svg|mp3|wav))(\\?["\']|\])',
        re.IGNORECASE
    )

    missing_files = set()

    for table in TABLES_TO_MIGRATE:
        print(f"\n🔄 Processing {table}...")
        try:
            cursor.execute(f"SELECT id, fields FROM {table}")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            print(f"⚠️  Skipping (Table not found)")
            continue

        updates = 0
        
        for row_id, fields_json in rows:
            if not fields_json: continue
            
            original_json = fields_json
            
            def replacer(match):
                prefix = match.group(1)
                filename = match.group(2) # e.g. Lion.PNG
                suffix = match.group(3)

                # --- LOOKUP STEP ---
                # Lowercase the filename found in DB before looking it up
                key = filename.lower() 
                
                # Normalize extension in key just in case (jpeg->jpg) if map has it normalized
                # But typically filename matching is enough
                if key == ".jpeg": key = key.replace(".jpeg", ".jpg")

                if key in filename_map:
                    new_hash = filename_map[key]
                    # We use the hash from the map
                    return f'{prefix}{NEW_MEDIA_URL_PREFIX}{new_hash}{suffix}'
                else:
                    # Try simple fallback for jpeg/jpg mismatch
                    if key.endswith(".jpeg") and key.replace(".jpeg", ".jpg") in filename_map:
                         new_hash = filename_map[key.replace(".jpeg", ".jpg")]
                         return f'{prefix}{NEW_MEDIA_URL_PREFIX}{new_hash}{suffix}'
                    
                    missing_files.add(filename)
                    return match.group(0)

            new_json = pattern.sub(replacer, original_json)
            
            if new_json != original_json:
                cursor.execute(f"UPDATE {table} SET fields = ? WHERE id = ?", (new_json, row_id))
                updates += 1

        print(f"   ✨ Updated {updates} rows.")

    conn.commit()
    conn.close()
    
    print("\n✅ Migration V3 Complete.")
    if missing_files:
        print(f"⚠️  WARNING: {len(missing_files)} unique files NOT found in map (checked case-insensitively).")
        print(f"   Examples: {list(missing_files)[:5]}")

if __name__ == "__main__":
    migrate_db_v3()
