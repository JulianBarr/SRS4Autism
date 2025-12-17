import sys
import csv
import json
import os
import time
import re
from pathlib import Path

# --- 1. SETUP ---
try:
    import google.generativeai as genai
    from PIL import Image
    from rdflib import Graph, Namespace, Literal
    from dotenv import load_dotenv
except ImportError:
    print("❌ Error: Missing libraries. Run: pip install google-generativeai pillow rdflib python-dotenv")
    sys.exit(1)

load_dotenv()

API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    print("❌ Error: GOOGLE_API_KEY not set in .env file.")
    sys.exit(1)

genai.configure(api_key=API_KEY)

# Using Gemini 2.0 Flash (Fast & Smart)
model = genai.GenerativeModel("gemini-2.0-flash")

# Path Configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
INPUT_KG = BASE_DIR / "knowledge_graph" / "world_model_with_images.ttl"
OUTPUT_REPORT = BASE_DIR / "logs" / "vision_cleanup_report.csv"
MEDIA_DIR = BASE_DIR / "content" / "media" / "images"

SRS_KG = Namespace("http://srs4autism.com/schema/")

def get_clean_filename(english_word, existing_filename):
    """
    Asks Gemini 2.0 for a better filename and validation.
    """
    full_path = MEDIA_DIR / existing_filename
    if not full_path.exists():
        return None

    try:
        img = Image.open(full_path)
    except Exception as e:
        print(f"   ⚠️ Corrupt image: {existing_filename}")
        return None

    prompt = f"""
    You are a Data Asset Manager.
    
    1. ANALYZE: Look at this image. The associated English word is "{english_word}".
    2. VERIFY: Does the image actually match the word "{english_word}"?
    3. TRANSLATE: What is the Chinese word for this specific image?
    4. RENAME: Generate a clean, descriptive filename (snake_case, lower).
       - Format: {{english_word}}_{{visual_detail}}.jpg
       - Example: If word is "Apple" and image is a red apple: "apple_red_fruit.jpg"
       - Example: If word is "Apple" and image is a computer: "apple_logo_tech.jpg"
    
    Return JSON:
    {{
        "is_match": true/false,
        "chinese": "中文",
        "pinyin": "pinyin",
        "new_filename": "clean_name.jpg",
        "reason": "Brief reason if is_match is false"
    }}
    """

    try:
        response = model.generate_content([prompt, img])
        
        text = response.text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        return json.loads(text)
        
    except Exception as e:
        print(f"   ❌ API Error: {e}")
        return None

def run_cleanup():
    if not INPUT_KG.exists():
        print(f"❌ KG not found: {INPUT_KG}")
        return

    print(f"Loading Knowledge Graph...")
    g = Graph()
    g.parse(INPUT_KG, format="turtle")
    print(f"Loaded {len(g)} triples.")

    # Query: Find English words linked to Images
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?wordLabel ?imageFile WHERE {
        ?w a srs-kg:Word ;
           srs-kg:text ?wordLabel ;
           srs-kg:means ?c .
        ?c srs-kg:hasVisualization ?img .
        ?img srs-kg:imageFileName ?imageFile .
    }
    """
    results = list(g.query(query))
    print(f"Found {len(results)} total images in graph.")

    # --- RESUME LOGIC ---
    processed_files = set()
    write_header = True
    
    if OUTPUT_REPORT.exists():
        print(f"Found existing report at {OUTPUT_REPORT.name}. Scanning for resume point...")
        with open(OUTPUT_REPORT, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Make sure CSV isn't empty/corrupt
            if reader.fieldnames:
                write_header = False
                for row in reader:
                    if 'Old_Filename' in row:
                        processed_files.add(row['Old_Filename'])
        print(f"✅ Resuming: Skipping {len(processed_files)} already processed images.")

    # Prepare Report (Append Mode 'a' if resuming, Write Mode 'w' if new)
    mode = 'a' if not write_header else 'w'
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_REPORT, mode, newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["English_Word", "Old_Filename", "New_Filename", "Chinese", "Match?", "Reason"])

        count = 0
        for row in results:
            count += 1
            word = str(row.wordLabel)
            old_file = str(row.imageFile)
            
            # CHECKPOINT CHECK
            if old_file in processed_files:
                # Optional: Print every 100 skips just to show life
                if count % 100 == 0:
                    print(f"[{count}/{len(results)}] Skipping {old_file} (Done)", end='\r')
                continue

            print(f"[{count}/{len(results)}] {word} | {old_file}...", end="", flush=True)
            
            result = get_clean_filename(word, old_file)
            
            if result:
                new_name = result.get('new_filename', 'error.jpg')
                chinese = result.get('chinese', '')
                match = result.get('is_match', False)
                reason = result.get('reason', '')
                
                status_icon = "✅" if match else "❌"
                print(f" -> {status_icon} Rename to: {new_name}")
                
                writer.writerow([word, old_file, new_name, chinese, match, reason])
                # Force write to disk immediately so we don't lose data if script crashes now
                f.flush() 
                
                time.sleep(0.2) 
            else:
                print(" -> Skipped (Error)")

    print(f"\n✅ Report updated: {OUTPUT_REPORT}")

if __name__ == "__main__":
    run_cleanup()