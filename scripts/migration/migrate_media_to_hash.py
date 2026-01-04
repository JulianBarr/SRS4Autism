import os
import sys
import json
import hashlib
import shutil
from pathlib import Path

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATION_LOG = PROJECT_ROOT / "migration_log.json"
DEST_DIR = PROJECT_ROOT / "content" / "media" / "objects"

# 1. DEFINE WHERE TO SEARCH
SOURCE_DIRS = [
    # The main content repository
    PROJECT_ROOT / "content" / "media" / "images",

    # The root-level 'media' folder (Legacy/Anki imports)
    PROJECT_ROOT / "media" / "character_recognition",
    PROJECT_ROOT / "media" / "chinese_word_recognition",
    PROJECT_ROOT / "media" / "english_word_recognition",
    PROJECT_ROOT / "media" / "pinyin",
    PROJECT_ROOT / "media" / "images",  # Appears distinct from content/media/images

    # Other potential scattered locations found in tree
    PROJECT_ROOT / "media" / "visual_images",
    PROJECT_ROOT / "content" / "media" / "visual_images",
    PROJECT_ROOT / "data" / "content_db" / "jpgs",
]

# Valid extensions to process
VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.mp3', '.wav', '.svg', '.webp'}

def calculate_content_hash(filepath):
    """
    Calculates MD5 hash of the ACTUAL FILE CONTENT.
    Reads in 64k chunks to handle large files safely.
    """
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    except Exception as e:
        print(f"❌ Error hashing {filepath}: {e}")
        return None

def migrate_media():
    print("=== 🚚 Media Content Migration (Content-Aware) ===")
    
    # Setup Destination
    if not DEST_DIR.exists():
        print(f"📂 Creating target directory: {DEST_DIR}")
        DEST_DIR.mkdir(parents=True, exist_ok=True)

    migration_map = {}
    stats = {"processed": 0, "copied": 0, "skipped": 0, "errors": 0}
    seen_hashes = set()

    # Scan and Process
    for source_dir in SOURCE_DIRS:
        if not source_dir.exists():
            print(f"⚠️  Skipping missing source: {source_dir}")
            continue

        print(f"🔍 Scanning {source_dir.name}...")
        
        for root, _, files in os.walk(source_dir):
            for filename in files:
                file_path = Path(root) / filename
                
                # Check Extension
                if file_path.suffix.lower() not in VALID_EXTENSIONS:
                    continue
                
                stats["processed"] += 1
                
                # A. Calculate Hash
                file_hash = calculate_content_hash(file_path)
                if not file_hash:
                    stats["errors"] += 1
                    continue
                
                # B. Generate New Filename
                short_hash = file_hash[:12]
                new_ext = file_path.suffix.lower()
                if new_ext == ".jpeg": new_ext = ".jpg" # Normalize extension
                
                new_filename = f"{short_hash}{new_ext}"
                dest_path = DEST_DIR / new_filename
                
                # C. Record Mapping
                # We map the RELATIVE PATH to the NEW FILENAME
                try:
                    rel_path = str(file_path.relative_to(PROJECT_ROOT))
                except ValueError:
                    rel_path = str(file_path)
                
                migration_map[rel_path] = new_filename

                # D. Copy File (Deduplication Logic)
                if short_hash not in seen_hashes:
                    if not dest_path.exists():
                        try:
                            shutil.copy2(file_path, dest_path)
                            stats["copied"] += 1
                        except Exception as e:
                            print(f"   ❌ Copy Failed: {filename} - {e}")
                            stats["errors"] += 1
                    else:
                        stats["skipped"] += 1 # File exists (from previous run)
                    seen_hashes.add(short_hash)
                else:
                    stats["skipped"] += 1 # Hash already seen in this run

    # Save Rainbow Table
    print(f"\n💾 Saving Migration Log to {MIGRATION_LOG}...")
    with open(MIGRATION_LOG, 'w', encoding='utf-8') as f:
        json.dump(migration_map, f, indent=2)

    print("-" * 30)
    print("🎉 Migration Complete")
    print(f"   - Files Scanned: {stats['processed']}")
    print(f"   - Unique Files:  {len(seen_hashes)}")
    print(f"   - Log Entries:   {len(migration_map)}")

if __name__ == "__main__":
    migrate_media()
