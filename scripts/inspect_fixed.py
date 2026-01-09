import zipfile
import sqlite3
import json
import tempfile
import os
import sys

def smart_inspect(apkg_path):
    print(f"--- SMART INSPECTION: {apkg_path} ---")
    
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
        # 1. List files to confirm the theory
        all_files = zip_ref.namelist()
        print(f"Files inside .apkg: {all_files}")
        
        # 2. Pick the best database
        if 'collection.anki21' in all_files:
            db_name = 'collection.anki21'
            print(">>> DETECTED MODERN ANKI DATABASE (v21)")
        elif 'collection.anki2' in all_files:
            db_name = 'collection.anki2'
            print(">>> DETECTED LEGACY ANKI DATABASE (v2)")
        else:
            print("ERROR: No collection database found!")
            return

        zip_ref.extract(db_name, temp_dir)
    
    db_path = os.path.join(temp_dir, db_name)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 3. Dump Note Types (Models)
    try:
        cursor.execute("SELECT models FROM col")
        res = cursor.fetchone()
        if not res:
            print("Error: 'col' table found but 'models' column is empty.")
            return
        models = json.loads(res[0])
    except Exception as e:
        print(f"Error reading models: {e}")
        return

    print(f"\nFound {len(models)} Note Types:\n")

    for m_id, m_data in models.items():
        name = m_data['name']
        flds = m_data['flds']
        field_names = [f['name'] for f in flds]
        
        # Check if this looks like your custom type
        is_target = 'Pinyin' in str(field_names) or 'Hanzi' in str(field_names)
        prefix = ">>> MATCH? " if is_target else ""
        
        print(f"{prefix}Note Type: [{name}]")
        print(f"    Fields: {field_names}")
        
        # Grab a real sample to confirm data exists
        cursor.execute("SELECT flds FROM notes WHERE mid = ? LIMIT 1", (m_id,))
        sample_note = cursor.fetchone()
        if sample_note:
            # Only print first 50 chars of the first field to verify it's not a warning
            raw_preview = sample_note[0].split('\x1f')[0][:50]
            print(f"    Sample: {raw_preview}...")
        print("-" * 40)
        
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        smart_inspect(sys.argv[1])
    else:
        print("Usage: python inspect_fixed.py <path_to_apkg>")
