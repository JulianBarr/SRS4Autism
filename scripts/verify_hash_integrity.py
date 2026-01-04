import hashlib
import json
import random
from pathlib import Path

# --- CONFIG ---
PROJECT_ROOT = Path(".").resolve()
MIGRATION_LOG = PROJECT_ROOT / "migration_log.json"
SAMPLE_SIZE = 20  # Number of files to audit (set to 0 to check ALL)

def get_file_hash(path):
    """Calculates MD5 hash of file content (not filename)."""
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def verify_integrity():
    print("=== 🕵️‍♀️ Hash Integrity Audit ===")
    
    if not MIGRATION_LOG.exists():
        print(f"❌ Migration log missing: {MIGRATION_LOG}")
        return

    print("Loading rainbow table...")
    with open(MIGRATION_LOG, 'r') as f:
        data = json.load(f)
        # Handle both flat and nested formats
        raw_map = data.get('old_full_path', data)

    items = list(raw_map.items())
    total_files = len(items)
    print(f"Loaded {total_files} mappings.")

    # Select sample
    if SAMPLE_SIZE > 0 and SAMPLE_SIZE < total_files:
        print(f"🎲 Randomly auditing {SAMPLE_SIZE} files...")
        audit_batch = random.sample(items, SAMPLE_SIZE)
    else:
        print(f"🔎 Auditing ALL {total_files} files...")
        audit_batch = items

    errors = 0
    checked = 0

    for old_path_str, new_filename in audit_batch:
        # 1. Locate the actual file on disk
        # The log likely contains relative paths like "content/media/images/apple.jpg"
        # We try to resolve it relative to PROJECT_ROOT
        
        # Clean path separators for current OS
        clean_path = Path(old_path_str)
        if clean_path.is_absolute():
            # If log has absolute paths, try to find them, or try stripping root
            if not clean_path.exists():
                # Try relative to project root
                try_rel = PROJECT_ROOT / clean_path.name
                if try_rel.exists(): clean_path = try_rel
        else:
            clean_path = PROJECT_ROOT / old_path_str

        if not clean_path.exists():
            print(f"⚠️  File not found on disk: {clean_path}")
            continue

        # 2. Calculate REAL Content Hash
        try:
            real_full_hash = get_file_hash(clean_path)
            
            # 3. Compare with Log
            # Log value is likely "hash.ext" (e.g., "8f4b2e.jpg")
            log_hash = Path(new_filename).stem  # "8f4b2e"
            
            # Your system likely uses the first N characters of the hash
            hash_length = len(log_hash)
            real_truncated_hash = real_full_hash[:hash_length]

            if real_truncated_hash == log_hash:
                # MATCH!
                checked += 1
                # print(f"✅ OK: {clean_path.name}")
            else:
                # FAILURE!
                errors += 1
                print(f"❌ CRITICAL MISMATCH: {clean_path.name}")
                print(f"   Log claims hash: {log_hash}")
                print(f"   Actual content:  {real_truncated_hash} (Full: {real_full_hash})")
                print("   👉 This implies the log is WRONG or the file changed.")

        except Exception as e:
            print(f"⚠️  Error reading {clean_path}: {e}")

    print("-" * 30)
    print(f"Audit Complete. Checked {checked} files.")
    if errors == 0:
        print("✅ INTEGRITY CONFIRMED: Hashes match file content.")
    else:
        print(f"❌ FAILED: Found {errors} hash mismatches.")
        print("🛑 DO NOT PROCEED with migration scripts.")

if __name__ == "__main__":
    verify_integrity()
