import zipfile
import sqlite3
import json
import tempfile
import os
import sys

def deep_inspect(apkg_path):
    print(f"--- DEEP CONTENT SEARCH: {apkg_path} ---")
    
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
    db_path = os.path.join(temp_dir, 'collection.anki2')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get Models
    cursor.execute("SELECT models FROM col")
    models = json.loads(cursor.fetchone()[0])

    for m_id, m_data in models.items():
        model_name = m_data['name']
        flds = m_data['flds']
        field_names = [f['name'] for f in flds]
        
        # Get up to 3 notes for this model
        cursor.execute("SELECT flds FROM notes WHERE mid = ? LIMIT 3", (m_id,))
        notes = cursor.fetchall()
        
        if not notes:
            continue
            
        print(f"\n[{model_name}] (Fields: {field_names})")
        print("=" * 50)
        
        for i, note in enumerate(notes):
            # Split fields by unit separator
            values = note[0].split('\x1f')
            
            # Print field mapping
            for f_name, f_val in zip(field_names, values):
                # Truncate long values (like images/audio) for readability
                preview = f_val[:50] + "..." if len(f_val) > 50 else f_val
                print(f"  {f_name:<15}: {preview}")
            print("-" * 30)

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        deep_inspect(sys.argv[1])
    else:
        print("Usage: python inspect_content.py <path_to_apkg>")
