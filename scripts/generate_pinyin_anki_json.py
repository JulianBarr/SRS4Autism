import csv
import json
import re
import os

# ==========================================
# 1. CONFIGURATION
# ==========================================
INPUT_FILE = "pinyin_all_redist.txt"
OUTPUT_FILE = "_pinyin_db.js" 

def extract_img_src(html_tag):
    """Extracts filename from <img src="...">"""
    if not html_tag:
        return ""
    clean_tag = html_tag.replace('""', '"') # Handle CSV escaping
    match = re.search(r'src="([^"]+)"', clean_tag)
    if match:
        return match.group(1)
    return ""

def generate_db():
    print(f"🚀 Generating Pinyin Database from {INPUT_FILE}...")
    
    # Locate input file
    input_path = INPUT_FILE
    if not os.path.exists(input_path):
        # Fallback for running from scripts/ folder
        if os.path.exists(os.path.join("..", INPUT_FILE)):
            input_path = os.path.join("..", INPUT_FILE)
        else:
            print(f"❌ Error: Could not find '{INPUT_FILE}'")
            return

    entries = []
    
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        
        for row in reader:
            # Skip comments/empty
            if not row or row[0].startswith('#') or len(row) < 6:
                continue

            # --- COLUMN MAPPING ---
            # Based on your file:
            # Col 0: Element (a)
            # Col 1: Syllable (bá)
            # Col 2: Word Pinyin
            # Col 3: Hanzi
            # Col 4: Picture (<img>)
            # Col 5: Audio (filename.mp3)
            
            syllable = row[1].strip()
            pic_html = row[4].strip()
            audio_raw = row[5].strip()
            
            # 1. Extract Picture
            pic_filename = extract_img_src(pic_html)
            
            # 2. Extract Audio (Handle raw filename or [sound:])
            # You said it's just the filename now, so we take it as is.
            # We strip [sound:] just in case, to be safe.
            audio_filename = audio_raw.replace('[sound:', '').replace(']', '').strip()

            # 3. Check Validity (Must have Syllable + Picture + Audio)
            # We filter out "Element" cards by ensuring Col 4 has an image tag
            if syllable and pic_filename and audio_filename:
                
                # 4. Generate Unique ID
                # We use the Audio Filename as the ID. 
                # It is unique, stable, and you said "use the filename" for now.
                unique_id = audio_filename
                
                entries.append({
                    "id": unique_id,  # <--- NEW ID FIELD
                    "syllable": syllable,
                    "pic": pic_filename,
                    "audio": audio_filename
                })

    # Write to JS file
    js_content = f"// Auto-generated Pinyin Database\n// Total Entries: {len(entries)}\n"
    js_content += "window.PINYIN_DB = " + json.dumps(entries, indent=2, ensure_ascii=False) + ";"
    
    output_path = OUTPUT_FILE
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
        
    print(f"✅ Success! Database generated with {len(entries)} items.")
    print(f"   Saved to: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    generate_db()
