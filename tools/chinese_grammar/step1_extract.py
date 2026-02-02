#!/usr/bin/env python3
"""
Chinese Grammar Extraction Agent
Extracts grammar points from EPUB using Gemini 1.5 Pro and saves to staging JSON.
"""

import os
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import google.generativeai as genai


# Configuration
EPUB_PATH = Path.home() / "src/chinese_grammar/book_elementary.epub"
OUTPUT_PATH = Path(__file__).parent / "grammar_staging.json"

# Initialize Gemini
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-pro")


def extract_text_from_epub(epub_path: Path) -> List[Dict[str, str]]:
    """
    Parse EPUB and extract sections based on h1/h2/h3 headers.
    Returns list of dicts with 'header' and 'content' keys.
    """
    book = epub.read_epub(str(epub_path))
    sections = []
    
    current_header = None
    current_content = []
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            # Find all headers and content
            for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'div']):
                if element.name in ['h1', 'h2', 'h3']:
                    # Save previous section if it has enough content
                    if current_header and len(' '.join(current_content)) >= 100:
                        sections.append({
                            'header': current_header,
                            'content': ' '.join(current_content).strip()
                        })
                    
                    # Start new section
                    current_header = element.get_text().strip()
                    current_content = []
                elif element.name in ['p', 'div']:
                    text = element.get_text().strip()
                    if text:
                        current_content.append(text)
            
            # Save last section if it has enough content
            if current_header and len(' '.join(current_content)) >= 100:
                sections.append({
                    'header': current_header,
                    'content': ' '.join(current_content).strip()
                })
    
    return sections


def extract_grammar_point(section: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Use Gemini to extract structured grammar point from a section.
    Returns None if extraction fails.
    """
    prompt = f"""你是一位中文语法专家。请从以下文本中提取语法点信息，并严格按照JSON格式返回。

文本标题: {section['header']}
文本内容: {section['content']}

请提取以下信息，并以JSON格式返回：
{{
    "grammar_point_cn": "语法点的标准中文名称（例如：把字句）",
    "anchor_example": "一个简短、有代表性的例句，作为UI缩略图（例如：我把苹果吃了）",
    "summary_cn": "用简单的中文解释这个语法点的逻辑（面向家长/教师）",
    "mandatory_keywords": ["语法标记词列表", "例如：把", "了"],
    "pragmatic_scenarios": ["实际使用场景1", "实际使用场景2", "例如：抱怨结果"],
    "is_useful_for_child": true或false（这个语法点是否对6-12岁儿童有用）
}}

重要要求：
1. 只返回JSON，不要其他文字
2. mandatory_keywords必须是字符串数组
3. pragmatic_scenarios必须是字符串数组
4. is_useful_for_child必须是布尔值
5. 如果文本不是语法点，返回null
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Try to extract JSON from response
        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split('\n')
            text = '\n'.join(lines[1:-1]) if lines[-1].startswith('```') else '\n'.join(lines[1:])
        
        # Parse JSON
        grammar_data = json.loads(text)
        
        # Validate required fields
        required_fields = [
            'grammar_point_cn', 'anchor_example', 'summary_cn',
            'mandatory_keywords', 'pragmatic_scenarios', 'is_useful_for_child'
        ]
        if all(field in grammar_data for field in required_fields):
            return grammar_data
        else:
            print(f"Warning: Missing fields in response for section: {section['header']}")
            return None
            
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON for section '{section['header']}': {e}")
        print(f"Response text: {text[:200]}...")
        return None
    except Exception as e:
        print(f"Error extracting grammar point for section '{section['header']}': {e}")
        return None


def main():
    """Main extraction pipeline."""
    print(f"Reading EPUB from: {EPUB_PATH}")
    
    if not EPUB_PATH.exists():
        print(f"Error: EPUB file not found at {EPUB_PATH}")
        return
    
    # Extract sections from EPUB
    print("Extracting sections from EPUB...")
    sections = extract_text_from_epub(EPUB_PATH)
    print(f"Found {len(sections)} sections with sufficient content")
    
    # Load existing staging data if it exists
    existing_data = []
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        print(f"Loaded {len(existing_data)} existing records")
    
    # Extract grammar points
    extracted_points = []
    for i, section in enumerate(sections, 1):
        print(f"\nProcessing section {i}/{len(sections)}: {section['header']}")
        
        grammar_point = extract_grammar_point(section)
        if grammar_point:
            # Add metadata
            grammar_point['id'] = str(uuid.uuid4())
            grammar_point['status'] = 'pending'
            grammar_point['source_header'] = section['header']
            grammar_point['source_content_preview'] = section['content'][:200] + "..."
            
            extracted_points.append(grammar_point)
            print(f"  ✓ Extracted: {grammar_point['grammar_point_cn']}")
        else:
            print(f"  ✗ Failed to extract grammar point")
    
    # Merge with existing data (avoid duplicates by checking IDs)
    existing_ids = {item['id'] for item in existing_data if 'id' in item}
    new_points = [p for p in extracted_points if p['id'] not in existing_ids]
    
    # Combine and save
    all_data = existing_data + new_points
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved {len(new_points)} new grammar points to {OUTPUT_PATH}")
    print(f"  Total records: {len(all_data)}")


if __name__ == "__main__":
    main()
