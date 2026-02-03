#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Chinese Grammar Points from JSON to Turtle (TTL) format.
Version: 2.1 (Added CEFR Level)
"""

import json
import re
from pathlib import Path
from typing import Dict, Any

# Project root
SCRIPT_DIR = Path(__file__).parent
GRAMMAR_JSON = SCRIPT_DIR / "grammar_approved.json"
OUTPUT_TTL = SCRIPT_DIR / "grammar_layer.ttl"

# RDF Namespaces
PREFIXES = """@prefix : <http://srs4autism.com/instance/> .
@prefix srs-kg: <http://srs4autism.com/schema/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

"""

def slugify_for_uri(text: str) -> str:
    if not text: return "unknown"
    # Keep Chinese chars, alphanumeric, and underscores
    slug = re.sub(r'[^\w\u4e00-\u9fff]', '_', text)
    slug = re.sub(r'_+', '_', slug)
    return slug.strip('_')

def escape_turtle_string(text: str) -> str:
    if not text: return '""'
    text = text.replace('\\', '\\\\').replace('"', '\\"')
    text = text.replace('\n', '\\n').replace('\r', '\\r')
    return f'"{text}"'

def format_literal(value: Any, lang: str = None, datatype: str = None) -> str:
    if value is None: return ""
    escaped = escape_turtle_string(str(value))
    if lang: return f'{escaped}@{lang}'
    elif datatype: return f'{escaped}^^xsd:{datatype}'
    else: return escaped

def convert_grammar_point_to_ttl(gp: Dict[str, Any]) -> str:
    title = gp.get('grammar_point_cn', 'Unknown')
    safe_title = slugify_for_uri(title)
    uri = f":Grammar_{safe_title}"
    
    lines = []
    lines.append(f"{uri} a srs-kg:GrammarPoint ;")
    
    # 1. Basic Info
    label = gp.get('grammar_point_cn', '')
    if label: lines.append(f'    rdfs:label {format_literal(label, lang="zh")} ;')
    
    explanation = gp.get('summary_cn', '')
    if explanation: lines.append(f'    srs-kg:explanation {format_literal(explanation, lang="zh")} ;')

    # 2. CEFR Level (Added!)
    level = gp.get('level', '')
    if level: lines.append(f'    srs-kg:cefrLevel {format_literal(level)} ;')

    # 3. Pragmatic Info
    anchor_example = gp.get('anchor_example', '')
    if anchor_example: lines.append(f'    srs-kg:anchorExample {format_literal(anchor_example, lang="zh")} ;')
    
    for scenario in gp.get('pragmatic_scenarios', []):
        if scenario: lines.append(f'    srs-kg:pragmaticContext {format_literal(scenario, lang="zh")} ;')
    
    for keyword in gp.get('mandatory_keywords', []):
        if keyword: lines.append(f'    srs-kg:keyword {format_literal(keyword)} ;')
    
    is_child_friendly = gp.get('is_useful_for_child', None)
    if is_child_friendly is not None:
        bool_value = "true" if is_child_friendly else "false"
        lines.append(f'    srs-kg:isChildFriendly {bool_value} ;')
    
    source_type = gp.get('source_type', '')
    if source_type: lines.append(f'    srs-kg:sourceType {format_literal(source_type)} ;')
    
    # Close the triple
    if lines:
        last_line = lines[-1]
        lines[-1] = last_line[:-2] + ' .' if last_line.endswith(' ;') else last_line + ' .'
    
    return '\n'.join(lines)

def export_json_to_ttl():
    if not GRAMMAR_JSON.exists(): return
    with open(GRAMMAR_JSON, 'r', encoding='utf-8') as f: data = json.load(f)
    
    print(f"🔄 Exporting {len(data)} grammar points (with CEFR levels)...")
    ttl_lines = [PREFIXES, ""]
    for gp in data:
        ttl_lines.append(convert_grammar_point_to_ttl(gp))
        ttl_lines.append("")
        
    with open(OUTPUT_TTL, 'w', encoding='utf-8') as f: f.write('\n'.join(ttl_lines))
    print(f"✅ Exported to {OUTPUT_TTL}")

if __name__ == "__main__":
    export_json_to_ttl()
