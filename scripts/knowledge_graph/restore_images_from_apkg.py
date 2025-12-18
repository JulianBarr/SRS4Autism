import zipfile
import json
import shutil
import csv
import os
from pathlib import Path

# --- CONFIGURATION ---
# Adjust these paths if necessary
PROJECT_ROOT = Path(".").resolve() 
APKG_PATH = PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"
CSV_PATH = PROJECT_ROOT / "logs" / "vision_cleanup_report.csv"
TARGET_DIR = PROJECT_ROOT / "content" / "media" / "images"

def restore_images():
    print("♻️  STARTING IMAGE RESTORE PROCESS")
    print(f"   📦 Source Deck: {APKG_PATH}")
    print(f"   📋 Filter CSV:  {CSV_PATH}")
    print(f"   📂 Target Dir:  {TARGET_DIR}")

    # 1. Clean Target Directory
    if TARGET_DIR.exists():
        print(f"\n[1/4] Cleaning {TARGET_DIR}...")
        shutil.rmtree(TARGET_DIR)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Get List of "Old_Filenames" we need from the CSV
    print(f"[2/4] Reading required files from CSV...")
    required_files = set()
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Match?', '').strip() == 'True':
                    old_name = row.get('Old_Filename', '').strip()
                    if old_name:
                        required_files.add(old_name)
        print(f"   ✅ Found {len(required_files)} unique images to restore.")
    except Exception as e:
        print(f"   ❌ Error reading CSV: {e}")
        return

    # 3. Open APKG and Map Files
    print(f"[3/4] Extracting images from APKG...")
    try:
        with zipfile.ZipFile(APKG_PATH, 'r') as z:
            # Read the 'media' JSON file which maps ID -> Filename
            # Format: {"123": "apple.jpg", "456": "tie2.jpg"}
            media_json = z.read('media').decode('utf-8')
            media_map = json.loads(media_json)
            
            # Create Reverse Map: Filename -> ID (e.g., "tie2.jpg" -> "456")
            filename_to_id = {v: k for k, v in media_map.items()}
            
            restored_count = 0
            missing_count = 0

            # 4. Extract only the required files
            print(f"[4/4] Writing files to target directory...")
            for filename in required_files:
                if filename in filename_to_id:
                    file_id = filename_to_id[filename]
                    source_path = file_id  # Inside zip, file is named "123"
                    dest_path = TARGET_DIR / filename # We want "tie2.jpg"
                    
                    try:
                        with z.open(source_path) as source, open(dest_path, 'wb') as dest:
                            shutil.copyfileobj(source, dest)
                        restored_count += 1
                    except KeyError:
                        print(f"      ⚠️ File ID {file_id} not found in zip for {filename}")
                else:
                    # Some files might not be in the APKG (if manually added later)
                    print(f"      ⚠️ '{filename}' not found in APKG media map.")
                    missing_count += 1

            print(f"\n✅ Restore Complete!")
            print(f"   Restored: {restored_count}")
            print(f"   Missing:  {missing_count}")
            print(f"   Folder:   {TARGET_DIR}")

    except FileNotFoundError:
        print(f"❌ APKG file not found at {APKG_PATH}")
    except Exception as e:
        print(f"❌ Error processing APKG: {e}")

if __name__ == "__main__":
    restore_images()
