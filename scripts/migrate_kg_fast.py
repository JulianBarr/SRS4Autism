import json
import re
import shutil
from pathlib import Path

# --- CONFIGURATION ---
PROJECT_ROOT = Path(".").resolve()
MIGRATION_LOG = PROJECT_ROOT / "migration_log.json"
KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
BACKUP_FILE = KG_FILE.with_suffix(".ttl.fast_bak")

# The new centralized home for hashed media
NEW_MEDIA_PATH = "content/media/objects/"

def migrate_kg_fast():
    print(f"=== Knowledge Graph Hash Migration (Fast Regex) ===")
    
    # 1. Validation
    if not MIGRATION_LOG.exists():
        print(f"❌ CRITICAL: Log not found at {MIGRATION_LOG}")
        return
    if not KG_FILE.exists():
        print(f"❌ CRITICAL: KG file not found at {KG_FILE}")
        return

    # 2. Load the Map
    print("📖 Loading Migration Log...")
    with open(MIGRATION_LOG, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
        # Handle flat vs nested structure
        raw_map = log_data.get('old_full_path', log_data)

    # Create Normalized Map
    filename_map = {}
    for k, v in raw_map.items():
        fname = Path(k).name.lower()
        filename_map[fname] = v
        
    print(f"✅ Loaded {len(filename_map)} file mappings.")

    # 3. Create Backup
    print(f"📦 Backing up {KG_FILE.name}...")
    shutil.copy2(KG_FILE, BACKUP_FILE)

    # 4. Read Content
    with open(KG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 5. Regex Replacement
    # Captures: "anything/filename.ext" or "filename.ext"
    # Group 1: Opening Quote
    # Group 2: Filename (The part we care about)
    # Group 3: Closing Quote
    pattern = re.compile(
        r'(")(?:[^"]*\/)?([^"/]+\.(?:jpg|jpeg|png|gif|webp|svg|mp3|wav))(")',
        re.IGNORECASE
    )

    count = 0
    missing = set()

    def replacer(match):
        nonlocal count
        quote_open = match.group(1)
        filename = match.group(2)  # <--- FIXED (Was 3)
        quote_close = match.group(3) # <--- FIXED (Was 4)
        
        key = filename.lower()
        
        # Normalize jpeg -> jpg lookup if needed
        if key.endswith(".jpeg") and key not in filename_map:
             alt_key = key.replace(".jpeg", ".jpg")
             if alt_key in filename_map:
                 key = alt_key

        if key in filename_map:
            new_hash = filename_map[key]
            count += 1
            # Replace with full new path
            return f'{quote_open}{NEW_MEDIA_PATH}{new_hash}{quote_close}'
        else:
            missing.add(filename)
            return match.group(0)

    new_content = pattern.sub(replacer, content)

    # 6. Save
    if count > 0:
        print(f"💾 Writing updated Knowledge Graph...")
        with open(KG_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"🎉 Success! Updated {count} references.")
    else:
        print("⚠️  No changes made (0 matches found).")

    if missing:
        print(f"⚠️  {len(missing)} filenames in KG were not found in the migration log.")
        print(f"   Examples: {list(missing)[:5]}")

if __name__ == "__main__":
    migrate_kg_fast()
