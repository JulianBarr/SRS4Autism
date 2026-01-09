import zipfile
import sqlite3
import json
import tempfile
import os
import sys

def inspect_apkg(apkg_path):
    print(f"--- INSPECTING SCHEMA: {apkg_path} ---")
    
    # Extract DB
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
    db_path = os.path.join(temp_dir, 'collection.anki2')
    
    if not os.path.exists(db_path):
        print("ERROR: collection.anki2 not found. Is this a standard .apkg?")
        return

    # Connect
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get Models
    try:
        cursor.execute("SELECT models FROM col")
        models_json = cursor.fetchone()[0]
        models = json.loads(models_json)
    except Exception as e:
        print(f"Error reading models: {e}")
        return

    print(f"\nFound {len(models)} Note Types:\n")

    for m_id, m_data in models.items():
        name = m_data['name']
        fields = [f['name'] for f in m_data['flds']]
        
        print(f"Note Type: [{name}]")
        print(f"Fields:    {fields}")
        print("-" * 40)
        
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        inspect_apkg(sys.argv[1])
    else:
        print("Usage: python inspect_apkg.py <path_to_apkg>")
