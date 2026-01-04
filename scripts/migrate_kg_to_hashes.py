import json
import re
import shutil
from pathlib import Path

# --- CONFIGURATION ---
PROJECT_ROOT = Path(".").resolve()
MIGRATION_LOG = PROJECT_ROOT / "migration_log.json"
# Target the specific file you mentioned
KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"
BACKUP_FILE = KG_FILE.with_suffix(".ttl.bak")

# The new centralized home for hashed media
NEW_MEDIA_PREFIX = "content/media/objects/"

def migrate_kg():
    print(f"=== Knowledge Graph Hash Migration ===")
    
    # 1. Validation
    if not MIGRATION_LOG.exists():
        print(f"❌ CRITICAL: Log not found at {MIGRATION_LOG}")
        return
    if not KG_FILE.exists():
        print(f"❌ CRITICAL: KG file not found at {KG_FILE}")
        return

    # 2. Load the Map (Rainbow Table)
    print("Loading Migration Log...")
    with open(MIGRATION_LOG, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
        # Handle format (nested vs flat)
        raw_map = log_data.get('old_full_path', log_data)

    # Prepare the lookup dictionary: "apple.jpg" -> "8f4b2e....jpg"
    # We sort by length (descending) to prevent substring issues (replacing 'apple.jpg' inside 'pineapple.jpg')
    filename_map = {Path(k).name: v for k, v in raw_map.items()}
    sorted_filenames = sorted(filename_map.keys(), key=len, reverse=True)
    
    print(f"✅ Loaded {len(filename_map)} file mappings.")

    # 3. Create Backup
    print(f"Backing up {KG_FILE.name}...")
    shutil.copy2(KG_FILE, BACKUP_FILE)

    # 4. Read Content
    with open(KG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 5. Perform Replacements
    # Strategy: We look for the filename appearing in typical RDF string contexts.
    # We assume the KG currently points to old paths like "media/images/apple.jpg" or just "apple.jpg"
    
    replacement_count = 0
    
    for old_fname in sorted_filenames:
        new_hash_name = filename_map[old_fname]
        
        # SKIP if the file isn't actually in the text (optimization)
        if old_fname not in content:
            continue

        # Regex Pattern Explanation:
        # 1. We look for a path separator '/' or a quote '"' preceding the filename.
        #    This ensures we match ".../apple.jpg" or "apple.jpg", but NOT ".../pineapple.jpg".
        # 2. We capture the filename.
        # 3. We ignore what comes before (we will replace the whole path segment).
        
        # Regex: Find (any_path_prefix/)(filename)
        # We replace the whole match with the NEW_MEDIA_PREFIX + hash
        
        # Valid patterns we might see in TTL:
        # "content/media/images/apple.jpg"
        # "/media/images/apple.jpg"
        # "apple.jpg"
        
        # Escaping for regex
        esc_fname = re.escape(old_fname)
        
        # Pattern:
        # (["/])       -> Group 1: Capture a preceding slash or quote (boundary)
        # (?:[\w\-/]*/)? -> Non-capturing group: Optional folder path (images/, media/images/)
        # apple\.jpg   -> The filename
        # (?=["\s])    -> Lookahead: Must be followed by a quote or whitespace (end of value)
        
        pattern = re.compile(r'([\"\/])(?:[\w\-\.\/]+\/)?' + esc_fname + r'(?=[\"|\s])')
        
        # Replacement function: keep the opening quote/slash, inject new path
        def replace_func(match):
            prefix_char = match.group(1) # The " or /
            
            # If it started with /, we keep relative pathing logic if needed, 
            # but usually for KG we want the full canonical path.
            # Let's standardize: If it was a file link, it now points to the object store.
            
            if prefix_char == '"':
                return f'"{NEW_MEDIA_PREFIX}{new_hash_name}'
            else:
                # If it was part of a URL/path like .../images/apple.jpg
                return f'/{NEW_MEDIA_PREFIX}{new_hash_name}'

        # Execute
        new_content, n = pattern.subn(replace_func, content)
        if n > 0:
            content = new_content
            replacement_count += n
            # print(f"  Replaced: {old_fname} -> {new_hash_name} ({n} times)")

    # 6. Save
    print(f"Writing updated Knowledge Graph...")
    with open(KG_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"🎉 Success! Updated {replacement_count} references in {KG_FILE.name}")
    print(f"   (Backup saved at {BACKUP_FILE.name})")

if __name__ == "__main__":
    migrate_kg()
