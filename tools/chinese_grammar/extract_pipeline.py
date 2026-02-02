#!/usr/bin/env python3
"""
Chinese Grammar Extraction Agent v4 (Auto-Save & Resume)
Features:
- Auto-detects best Gemini model
- Forces REST protocol for stability
- SAVES PROGRESS every 5 items
- RESUMES from where you left off
"""

import os
import json
import sys
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# ============================================================================
# 1. CONFIGURATION
# ============================================================================

TEST_LIMIT = None  # None = 跑全量
SAVE_INTERVAL = 5  # 每处理 5 个存一次盘
EPUB_PATH = Path(__file__).parent / "book_elementary.epub"
OUTPUT_PATH = Path(__file__).parent / "grammar_staging.json"
MIN_CONTENT_LENGTH = 200
SKIP_KEYWORDS = ["Contents", "Foreword", "Copyright", "Index", "Wiki", "Introduction", "Preface", "Appendix", "Glossary", "References"]

# ============================================================================
# 2. NETWORK & MODEL SETUP
# ============================================================================

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
PROXY_URL = "http://127.0.0.1:1087"  # Shadowsocks Port

# Force Proxy
os.environ["HTTP_PROXY"] = PROXY_URL
os.environ["HTTPS_PROXY"] = PROXY_URL

if not API_KEY:
    print("❌ FATAL: GOOGLE_API_KEY not found.")
    sys.exit(1)

def check_connectivity():
    print(f"📡 Testing connectivity via {PROXY_URL}...")
    try:
        requests.get("https://www.google.com", proxies={"http": PROXY_URL, "https": PROXY_URL}, timeout=5)
        print("✅ Connection Verified!")
        return True
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return False

if not check_connectivity():
    sys.exit(1)

def get_best_model():
    try:
        genai.configure(api_key=API_KEY, transport='rest')
        print("🔍 Scanning available models...")
        candidates = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        if not candidates:
            print("❌ No models found.")
            sys.exit(1)

        chosen = next((m for m in candidates if 'pro' in m.lower()), 
                 next((m for m in candidates if 'flash' in m.lower()), candidates[0]))
            
        print(f"✅ Selected Model: {chosen}")
        return genai.GenerativeModel(chosen)

    except Exception as e:
        print(f"❌ Error listing models: {e}")
        sys.exit(1)

model = get_best_model()

# ============================================================================
# 3. UTILS: SAVE & LOAD
# ============================================================================

def load_existing_data():
    if not OUTPUT_PATH.exists():
        return []
    try:
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️  Warning: JSON file corrupted, starting fresh.")
        return []

def save_data(data):
    """Safe atomic save"""
    temp_path = OUTPUT_PATH.with_suffix('.tmp')
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, OUTPUT_PATH)
    print(f"💾 Progress Saved ({len(data)} records)")

# ============================================================================
# 4. CORE LOGIC
# ============================================================================

def extract_text_from_epub(epub_path: Path) -> List[Dict[str, str]]:
    print(f"\n📖 Reading EPUB: {epub_path}")
    book = epub.read_epub(str(epub_path))
    sections = []
    current_header = None
    current_content = []
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'div']):
                if element.name in ['h1', 'h2', 'h3']:
                    if current_header and len(' '.join(current_content)) >= MIN_CONTENT_LENGTH:
                        sections.append({'header': current_header, 'content': ' '.join(current_content).strip()})
                    current_header = element.get_text().strip()
                    current_content = []
                elif element.name in ['p', 'div']:
                    t = element.get_text().strip()
                    if t: current_content.append(t)
            
            if current_header and len(' '.join(current_content)) >= MIN_CONTENT_LENGTH:
                sections.append({'header': current_header, 'content': ' '.join(current_content).strip()})
    return sections

def should_skip(header):
    return any(k.lower() in header.lower() for k in SKIP_KEYWORDS)

def extract_grammar_point(section):
    prompt = f"""
    You are a Chinese Grammar Expert. 
    Extract a structured grammar card from this text.
    
    Title: {section['header']}
    Content: {section['content'][:3000]}
    
    Return ONLY JSON. No markdown.
    {{
        "grammar_point_cn": "Standard Chinese Name (e.g. 把字句)",
        "anchor_example": "One short representative sentence (e.g. 我把苹果吃了)",
        "summary_cn": "Simple explanation",
        "mandatory_keywords": ["word1", "word2"],
        "pragmatic_scenarios": ["scenario1"],
        "is_useful_for_child": boolean
    }}
    If NOT a grammar point, return null.
    """
    try:
        # print(f"   🤖 Asking Gemini...") 
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "")
        if text.lower() == 'null': return None
        return json.loads(text)
    except Exception as e:
        # print(f"   ⚠️  API Error: {e}")
        return None

def main():
    # 1. Load History
    all_data = load_existing_data()
    # Create a lookup set of already processed headers
    processed_headers = {item.get('source_header') for item in all_data if item.get('source_header')}
    
    print(f"📂 Loaded {len(all_data)} existing records.")

    # 2. Load EPUB
    sections = extract_text_from_epub(EPUB_PATH)
    valid_sections = [s for s in sections if not should_skip(s['header'])]
    
    print(f"📊 Total valid sections: {len(valid_sections)}")
    
    # 3. Processing Loop
    new_count = 0
    session_count = 0
    
    try:
        for i, section in enumerate(valid_sections):
            header = section['header']
            
            # --- RESUME LOGIC ---
            if header in processed_headers:
                # print(f"⏭️  Skipping already processed: {header}")
                continue
            
            # Check Limit
            if TEST_LIMIT is not None and session_count >= TEST_LIMIT:
                print(f"\n🛑 Reached session limit ({TEST_LIMIT}).")
                break

            print(f"[{i+1}/{len(valid_sections)}] Processing: {header}")
            
            # --- API CALL ---
            data = extract_grammar_point(section)
            
            if data:
                print(f"   ✅ SUCCESS: {data.get('grammar_point_cn')}")
                data['id'] = str(i) # Use index as simple ID
                data['status'] = 'pending'
                data['source_header'] = header # Critical for Resume logic
                
                all_data.append(data)
                processed_headers.add(header)
                new_count += 1
                session_count += 1
                
                # --- AUTO-SAVE ---
                if new_count % SAVE_INTERVAL == 0:
                    save_data(all_data)
            else:
                print("   ⚪ Skipped (Not grammar)")
                # Optionally mark as processed so we don't retry failed ones?
                # For now, we don't add to processed_headers so we can retry later if code improves.
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by User! Saving progress...")
    
    # Final Save
    save_data(all_data)
    print(f"\n🎉 Session Finished. Added {new_count} new items. Total: {len(all_data)}")

if __name__ == "__main__":
    main()
