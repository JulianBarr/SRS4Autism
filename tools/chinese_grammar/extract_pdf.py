#!/usr/bin/env python3
"""
Chinese Grammar Extraction Agent (PDF Version)
Uses PDF Outline (TOC) to slice content and extract grammar points.
"""

import os
import json
import sys
import time
import requests
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

# ============================================================================
# 1. CONFIGURATION
# ============================================================================

TEST_LIMIT = None  # None = 跑全量
SAVE_INTERVAL = 5
# 请确认你的 PDF 文件名是否正确
PDF_FILENAME = "book_chinese_grammar_intermediary.pdf"
PDF_PATH = Path(__file__).parent / PDF_FILENAME
OUTPUT_PATH = Path(__file__).parent / "grammar_staging_pdf.json" # 区分输出文件
MIN_CONTENT_LENGTH = 100
# 垃圾过滤
SKIP_KEYWORDS = ["Contents", "Foreword", "Copyright", "Index", "Wiki", "Introduction", "Preface", "Appendix", "Glossary"]

# ============================================================================
# 2. NETWORK & MODEL (与 EPUB 版完全一致)
# ============================================================================

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
PROXY_URL = "http://127.0.0.1:1087"

os.environ["HTTP_PROXY"] = PROXY_URL
os.environ["HTTPS_PROXY"] = PROXY_URL

if not API_KEY:
    print("❌ FATAL: GOOGLE_API_KEY not found.")
    sys.exit(1)

def check_connectivity():
    try:
        requests.get("https://www.google.com", proxies={"http": PROXY_URL, "https": PROXY_URL}, timeout=5)
        return True
    except:
        return False

if not check_connectivity():
    print("❌ Connectivity Check Failed. Check Proxy.")
    sys.exit(1)

def get_best_model():
    try:
        genai.configure(api_key=API_KEY, transport='rest')
        candidates = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if not candidates: return None
        # 优先找 Pro，其次 Flash
        chosen = next((m for m in candidates if 'pro' in m.lower()), 
                 next((m for m in candidates if 'flash' in m.lower()), candidates[0]))
        print(f"✅ Model: {chosen}")
        return genai.GenerativeModel(chosen)
    except Exception as e:
        print(f"❌ Model Error: {e}")
        sys.exit(1)

model = get_best_model()

# ============================================================================
# 3. PDF SPECIFIC EXTRACTION (核心差异)
# ============================================================================

def extract_sections_from_pdf(pdf_path: Path) -> List[Dict[str, str]]:
    print(f"\n📖 Reading PDF: {pdf_path.name}...")
    
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"❌ Error opening PDF: {e}")
        return []

    # 获取目录结构 (lvl, title, page)
    toc = doc.get_toc()
    
    if not toc:
        print("❌ Error: No Table of Contents (Outline) found in this PDF.")
        print("   Without bookmarks, we cannot automatically split chapters.")
        return []

    print(f"   Found {len(toc)} TOC entries.")
    
    sections = []
    
    for i in range(len(toc)):
        lvl, title, page_num = toc[i]
        
        # 这里的 page_num 是从 1 开始的，PyMuPDF 是从 0 开始
        start_page = page_num - 1
        
        # 确定结束页：是下一章的开始页，或者是文档末尾
        if i < len(toc) - 1:
            end_page = toc[i+1][2] - 1
        else:
            end_page = doc.page_count
            
        # 安全检查
        if start_page < 0: start_page = 0
        if end_page > doc.page_count: end_page = doc.page_count
        
        # 提取这一范围内的所有文本
        chapter_text = ""
        # 限制每章最多读 10 页，防止某个目录项包含了半本书
        real_end = min(end_page, start_page + 10) 
        
        for p in range(start_page, real_end):
            chapter_text += doc.load_page(p).get_text()
            
        # 清洗文本 (去掉过多的换行)
        clean_text = chapter_text.replace('\n', ' ').replace('  ', ' ')
        
        if len(clean_text) >= MIN_CONTENT_LENGTH:
            sections.append({
                'header': title.strip(),
                'content': clean_text
            })
            
    print(f"✅ Extracted {len(sections)} sections from PDF.")
    return sections

# ============================================================================
# 4. SHARED LOGIC (复用)
# ============================================================================

def load_existing_data():
    if not OUTPUT_PATH.exists(): return []
    try:
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def save_data(data):
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 Saved ({len(data)} records)")

def should_skip(header):
    return any(k.lower() in header.lower() for k in SKIP_KEYWORDS)

def extract_grammar_point(section):
    # Prompt 稍微针对 PDF 的 OCR 噪音做一点鲁棒性调整
    prompt = f"""
    You are a Chinese Grammar Expert. 
    Extract a structured grammar card from this text (OCR extracted from PDF).
    
    Title: {section['header']}
    Content: {section['content'][:4000]}
    
    Return ONLY JSON. No markdown.
    {{
        "grammar_point_cn": "Standard Chinese Name (e.g. 把字句)",
        "anchor_example": "One short representative sentence",
        "summary_cn": "Simple explanation",
        "mandatory_keywords": ["word1", "word2"],
        "pragmatic_scenarios": ["scenario1"],
        "is_useful_for_child": boolean
    }}
    If NOT a grammar point, return null.
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"): text = text.replace("```json", "").replace("```", "")
        if text.lower() == 'null': return None
        return json.loads(text)
    except: return None

def main():
    if not PDF_PATH.exists():
        print(f"❌ PDF not found: {PDF_PATH}")
        return

    all_data = load_existing_data()
    processed_headers = {item.get('source_header') for item in all_data if item.get('source_header')}
    
    sections = extract_sections_from_pdf(PDF_PATH)
    valid_sections = [s for s in sections if not should_skip(s['header'])]
    
    print(f"📊 Processing {len(valid_sections)} valid chapters...")
    
    new_count = 0
    session_count = 0
    
    try:
        for i, section in enumerate(valid_sections):
            header = section['header']
            if header in processed_headers: continue
            if TEST_LIMIT is not None and session_count >= TEST_LIMIT: break

            print(f"[{i+1}/{len(valid_sections)}] Processing: {header}")
            data = extract_grammar_point(section)
            
            if data:
                print(f"   ✅ SUCCESS: {data.get('grammar_point_cn')}")
                data['id'] = f"pdf_{i}" # 使用前缀区分 PDF 数据
                data['status'] = 'pending'
                data['source_header'] = header
                
                all_data.append(data)
                processed_headers.add(header)
                new_count += 1
                session_count += 1
                
                if new_count % SAVE_INTERVAL == 0: save_data(all_data)
            else:
                print("   ⚪ Skipped")
                
    except KeyboardInterrupt:
        print("\n⚠️ Paused.")
    
    save_data(all_data)
    print(f"\n🎉 Done. Total: {len(all_data)}")

if __name__ == "__main__":
    main()
