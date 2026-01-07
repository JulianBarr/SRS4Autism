import sqlite3
import json
import os

# 1. Setup Paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, "..", "data", "srs4autism.db")

def scrub_db():
    print(f"🧹 STARTING CLEANUP: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("❌ Error: Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Get all notes
    cursor.execute("SELECT note_id, fields FROM pinyin_syllable_notes")
    rows = cursor.fetchall()

    print(f"   Scanning {len(rows)} notes...")
    
    updated_count = 0
    
    for note_id, fields_json in rows:
        if not fields_json:
            continue
            
        fields = json.loads(fields_json)
        original_keys = list(fields.keys())
        
        # 3. Identify and Remove Obsolete Keys
        keys_to_remove = [ 'ConfusorPicture1', 'ConfusorPicture2', 'ConfusorPicture3' ,'Confusor1', 'Confusor2', 'Confusor3', 'Tone1', 'Tone2', 'Tone3', 'Tone4']  # <--- Add these 
        modified = False
        
        for key in keys_to_remove:
            if key in fields:
                del fields[key]
                modified = True
        
        # 4. Save back if changed
        if modified:
            new_json = json.dumps(fields, ensure_ascii=False)
            cursor.execute(
                "UPDATE pinyin_syllable_notes SET fields = ? WHERE note_id = ?", 
                (new_json, note_id)
            )
            updated_count += 1
            # Optional: Print first few to confirm
            if updated_count < 3:
                print(f"   [Debug] scrubbed note {note_id}")

    conn.commit()
    conn.close()
    
    print("-" * 30)
    print(f"✅ CLEANUP COMPLETE.")
    print(f"   Scrubbed obsolete fields from {updated_count} notes.")
    print("   👉 Now Restart CUMA and Trigger a Sync to update Anki.")

if __name__ == "__main__":
    scrub_db()
