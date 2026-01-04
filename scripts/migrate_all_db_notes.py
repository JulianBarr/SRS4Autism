import sqlite3
import json
import re
import shutil
from pathlib import Path

# --- CONFIGURATION ---
PROJECT_ROOT = Path(".").resolve()
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db" 
MIGRATION_LOG = PROJECT_ROOT / "migration_log.json"
BACKUP_DB_PATH = DB_PATH.with_suffix(".db.bak")

# The list of tables you provided
TABLES_TO_MIGRATE = [
    "chinese_word_recognition_notes",
    "english_word_recognition_notes",
    "pinyin_element_notes",
    "pinyin_syllable_notes",
    "character_recognition_notes"
]

# The new URL prefix for the frontend
NEW_MEDIA_URL_PREFIX = "/media/objects/"

def migrate_all_notes():
    print("=== Universal Database Note Migration ===")

    # 1. Validation & Backup
    if not MIGRATION_LOG.exists():
        print(f"❌ Migration log not found: {MIGRATION_LOG}")
        return
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return

    print(f"📦 Backing up database to {BACKUP_DB_PATH.name}...")
    shutil.copy2(DB_PATH, BACKUP_DB_PATH)

    # 2. Load Rainbow Table
    print("📖 Loading rainbow table...")
    with open(MIGRATION_LOG, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
        raw_map = log_data.get('old_full_path', log_data)
        
    filename_map = {Path(k).name: v for k, v in raw_map.items()}
    print(f"✅ Loaded {len(filename_map)} file mappings.")

    # 3. Connect to DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Regex: Capture src="/media/FOLDER/filename.ext"
    # Group 1: Prefix (src=")
    # Group 2: Old Folder (e.g. /media/images/)
    # Group 3: Filename (e.g. apple.jpg)
    # Group 4: Suffix (")
    img_pattern = re.compile(r'(src=\\?["\'])(/media/[^/\"\'\\]+/)([^/\"\'\\]+\.[a-zA-Z0-9]+)(\\?["\'])')

    total_updates = 0

    # 4. Loop through Tables
    for table in TABLES_TO_MIGRATE:
        print(f"\n🔄 Processing table: {table}...")
        
        try:
            cursor.execute(f"SELECT id, fields FROM {table}")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            print(f"⚠️  Skipping {table} (Table not found)")
            continue

        table_updates = 0
        
        for row_id, fields_json in rows:
            if not fields_json: continue
            
            original_json = fields_json
            
            def replace_img(match):
                prefix = match.group(1)       # src="
                old_folder = match.group(2)   # /media/old_folder/
                old_filename = match.group(3) # peacock.png
                suffix = match.group(4)       # "
                
                if old_filename in filename_map:
                    new_hash = filename_map[old_filename]
                    # Replace with centralized object path
                    return f'{prefix}{NEW_MEDIA_URL_PREFIX}{new_hash}{suffix}'
                else:
                    return match.group(0) # Keep original if not in map

            new_json = img_pattern.sub(replace_img, original_json)
            
            if new_json != original_json:
                cursor.execute(f"UPDATE {table} SET fields = ? WHERE id = ?", (new_json, row_id))
                table_updates += 1

        print(f"   ✨ Updated {table_updates} rows.")
        total_updates += table_updates

    conn.commit()
    conn.close()

    print(f"\n🎉 Total Success! Updated {total_updates} notes across all tables.")
    print(f"   (Backup saved at {BACKUP_DB_PATH.name})")

if __name__ == "__main__":
    migrate_all_notes()
