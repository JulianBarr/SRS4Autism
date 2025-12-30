import sys
import json
import sqlite3
import re
import urllib.parse
from pathlib import Path

# --- Config ---
PROJECT_ROOT = Path(".").resolve()
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
KG_PATH = PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl"
MIGRATION_LOG = PROJECT_ROOT / "migration_log.json"

def load_migration_map():
    if not MIGRATION_LOG.exists():
        print(f"❌ CRITICAL: Migration log not found at {MIGRATION_LOG}")
        print("   Without this log, we cannot map the moved files back to DB entries.")
        sys.exit(1)
    
    with open(MIGRATION_LOG, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Handle both flat map or nested structure depending on previous script version
        if 'old_full_path' in data:
            return data['old_full_path'] # Nested format
        return data # Flat format

def fix_database(migration_map):
    print("\n💾 Fixing Database (Advanced Matching)...")
    if not DB_PATH.exists(): return

    # Prepare lookup: filename -> hash
    # We add URL encoded versions too: "apple red.jpg" AND "apple%20red.jpg"
    filename_map = {}
    for old_path, new_name in migration_map.items():
        fname = Path(old_path).name
        filename_map[fname] = new_name
        # Handle URL encoding
        encoded = urllib.parse.quote(fname)
        if encoded != fname:
            filename_map[encoded] = new_name

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all cards
    cursor.execute("SELECT id, content FROM approved_cards")
    cards = cursor.fetchall()
    
    updates = 0
    
    for card_id, content_raw in cards:
        try:
            # We treat content as a raw string to catch all occurrences
            # (JSON parsing is safer but might miss escaped strings inside other fields)
            new_content = content_raw
            modified = False
            
            # 1. Regex Replace for precise <img> tag targeting
            # Finds src="...filename..."
            def replace_match(match):
                prefix = match.group(1) # src=".../
                old_file = match.group(2) # filename.jpg
                suffix = match.group(3) # "
                
                # Try exact match
                if old_file in filename_map:
                    return f"{prefix}{filename_map[old_file]}{suffix}"
                
                # Try URL decoded match
                decoded = urllib.parse.unquote(old_file)
                if decoded in filename_map:
                    return f"{prefix}{filename_map[decoded]}{suffix}"
                    
                return match.group(0)

            # Regex: src=" (optional path) (filename) "
            # Captures: 1=prefix, 2=filename, 3=closing quote
            # Be robust: match path separators / or \ or nothing
            pattern = re.compile(r'(src=["\'].*?[/\\]?)([^/\\"\']+\.[a-zA-Z0-9]+)(["\'])')
            
            new_content = pattern.sub(replace_match, new_content)
            
            if new_content != content_raw:
                cursor.execute("UPDATE approved_cards SET content = ? WHERE id = ?", (new_content, card_id))
                updates += 1
                
        except Exception as e:
            print(f"   ⚠️ Error processing card {card_id}: {e}")

    conn.commit()
    conn.close()
    print(f"   ✅ Force-updated {updates} cards in Database.")

def fix_knowledge_graph(migration_map):
    print("\n🔗 Fixing Knowledge Graph (Robust Regex)...")
    if not KG_PATH.exists(): return

    # Prepare lookup
    filename_map = {Path(k).name: v for k, v in migration_map.items()}
    
    # Read entire file (if it fits in memory, safer for regex) 
    # OR stream if huge. Streaming is safer.
    temp_file = KG_PATH.with_suffix('.ttl.fix')
    
    # Regex for Turtle: matches srs-kg:imageFileName "value"
    # Handles flexible whitespace
    pattern = re.compile(r'(srs-kg:imageFileName\s*["\'])([^"\']+)["\']')
    
    changes = 0
    with open(KG_PATH, 'r', encoding='utf-8') as fin, \
         open(temp_file, 'w', encoding='utf-8') as fout:
        
        for line in fin:
            match = pattern.search(line)
            if match:
                prefix = match.group(1)
                old_val = match.group(2)
                
                # Turtle values might be just "apple.jpg" or "content/media/images/apple.jpg"
                old_fname = Path(old_val).name
                
                if old_fname in filename_map:
                    new_val = filename_map[old_fname]
                    # Rewrite line
                    # Preserve prefix, swap filename, append originalName
                    # Check if line has semicolon/dot at end
                    clean_line = line.rstrip()
                    terminator = ""
                    if clean_line.endswith(";") or clean_line.endswith("."):
                        terminator = clean_line[-1]
                    
                    # Reconstruction
                    # We assume the match covers the property and value. 
                    # We replace the match with the new structure.
                    
                    replacement = f'{prefix}{new_val}" ; srs-kg:originalName "{old_fname}"'
                    
                    # Replace only the match part in the line
                    new_line = line.replace(match.group(0), replacement)
                    fout.write(new_line)
                    changes += 1
                    continue
            
            fout.write(line)

    import shutil
    shutil.move(temp_file, KG_PATH)
    print(f"   ✅ Fixed {changes} lines in Knowledge Graph.")

if __name__ == "__main__":
    print("=== RECOVERY MODE: Fix Data Links ===")
    m_map = load_migration_map()
    print(f"Loaded {len(m_map)} file mappings.")
    
    fix_database(m_map)
    fix_knowledge_graph(m_map)
    print("\nDone. Please run verification again.")
