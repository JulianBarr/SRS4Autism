import sys
import os
import json
import sqlite3
import re
import requests
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(".").resolve()
MEDIA_OBJECTS_DIR = PROJECT_ROOT / "content" / "media" / "objects"
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
KG_PATH = PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl"
SERVER_URL = "http://localhost:8000"

def print_pass(msg):
    print(f"✅ PASS: {msg}")

def print_fail(msg):
    print(f"❌ FAIL: {msg}")

def print_warn(msg):
    print(f"⚠️  WARN: {msg}")

def verify_filesystem():
    print("\n--- 1. Filesystem Verification ---")
    if not MEDIA_OBJECTS_DIR.exists():
        print_fail(f"Directory not found: {MEDIA_OBJECTS_DIR}")
        return None

    files = list(MEDIA_OBJECTS_DIR.glob("*"))
    if not files:
        print_fail("Objects directory is empty.")
        return None

    # Check naming convention (12+ hex chars)
    # Pattern: at least 12 hex chars, optional more, dot, extension
    hash_pattern = re.compile(r'^[a-f0-9]{12,}\.[a-z]+$', re.IGNORECASE)
    
    sample_file = files[0].name
    if hash_pattern.match(sample_file):
        print_pass(f"Found {len(files)} files. Sample '{sample_file}' matches hash pattern.")
        return sample_file
    else:
        print_fail(f"Sample file '{sample_file}' does NOT look like a hash. Migration might be incomplete.")
        return None

def verify_database():
    print("\n--- 2. Database Verification ---")
    if not DB_PATH.exists():
        print_fail(f"Database not found: {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Get a card that has an image
        cursor.execute("SELECT id, content FROM approved_cards WHERE content LIKE '%<img%' LIMIT 5")
        rows = cursor.fetchall()
        
        if not rows:
            print_warn("No cards with images found in DB to verify.")
            return

        valid_count = 0
        for card_id, content_json in rows:
            content = json.loads(content_json)
            # Check front or back for img tag
            html = content.get('front', '') + content.get('back', '')
            
            # Regex to find src. Expecting: /static/media/HASH.jpg OR just HASH.jpg
            # The migration summary said: "/static/media/{filename}"
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
            
            if img_match:
                src = img_match.group(1)
                # Check if it contains a hash-like string
                if re.search(r'[a-f0-9]{12,}\.[a-z]+', src):
                    valid_count += 1
                else:
                    print_fail(f"Card {card_id} has non-hash image source: {src}")
        
        if valid_count > 0:
            print_pass(f"Verified {valid_count} cards have hash-based image sources (e.g., /static/media/...).")
        else:
            print_fail("Found image cards, but none matched the hash pattern.")
            
    except Exception as e:
        print_fail(f"Database error: {e}")
    finally:
        if conn: conn.close()

def verify_knowledge_graph():
    print("\n--- 3. Knowledge Graph Verification ---")
    if not KG_PATH.exists():
        print_fail(f"KG not found: {KG_PATH}")
        return

    # Scan first 500 lines for srs-kg:imageFileName
    found_hash = False
    found_alias = False
    
    with open(KG_PATH, 'r', encoding='utf-8') as f:
        for _ in range(2000): # Check first 2000 lines
            line = f.readline()
            if not line: break
            
            # Check for hash filename
            if 'srs-kg:imageFileName' in line:
                if re.search(r'"[a-f0-9]{12,}\.[a-z]+"', line):
                    found_hash = True
            
            # Check for original name alias
            if 'srs-kg:originalName' in line:
                found_alias = True
                
            if found_hash and found_alias: break
    
    if found_hash:
        print_pass("Found 'srs-kg:imageFileName' pointing to hash filenames.")
    else:
        print_warn("Did not find hash filenames in the first 2000 lines of KG (might be further down).")

    if found_alias:
        print_pass("Found 'srs-kg:originalName' preserving old aliases.")
    else:
        print_warn("Did not find 'srs-kg:originalName' property (check migration logic).")

def verify_server(sample_filename):
    print("\n--- 4. Server Verification ---")
    if not sample_filename:
        print_warn("Skipping server test (no sample file found).")
        return

    url = f"{SERVER_URL}/static/media/{sample_filename}"
    print(f"Testing URL: {url}")
    
    try:
        response = requests.head(url, timeout=2)
        if response.status_code == 200:
            print_pass(f"Server is running and serving {sample_filename} correctly.")
        else:
            print_fail(f"Server returned status {response.status_code}. (Is the backend running?)")
            print("   Run: python backend/run.py")
    except requests.exceptions.ConnectionError:
        print_fail("Could not connect to localhost:8000. Is the backend running?")
        print("   Run: python backend/run.py")

if __name__ == "__main__":
    print("=== VERIFYING MEDIA ARCHITECTURE REFACTOR ===\n")
    sample_file = verify_filesystem()
    verify_database()
    verify_knowledge_graph()
    verify_server(sample_file)
    print("\n=== VERIFICATION COMPLETE ===")
