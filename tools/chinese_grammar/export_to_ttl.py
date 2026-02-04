#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Chinese Grammar Points from JSON to TTL.
Version: 5.0 (Strict ID-Based Logic - The "Enough Thinking" Fix)
"""

import json
import re
from pathlib import Path
from typing import Dict, Any

# Project root
SCRIPT_DIR = Path(__file__).parent
GRAMMAR_JSON = SCRIPT_DIR / "grammar_approved.json"
OUTPUT_TTL = SCRIPT_DIR / "grammar_layer.ttl"

PREFIXES = """@prefix : <http://srs4autism.com/instance/> .
@prefix srs-kg: <http://srs4autism.com/schema/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

"""

class LevelCalculator:
    def __init__(self):
        self.numeric_level = "A1" # State for numeric IDs
        self.stats = {"A1": 0, "A2": 0, "B1": 0, "B2": 0, "Unknown": 0}

    def get_level(self, gp: Dict[str, Any]) -> str:
        gp_id = str(gp.get('id', '')).strip()
        title = gp.get('grammar_point_cn', '').strip()

        # RULE 1: B2 (If ID starts with 'pdf_b2_')
        if gp_id.startswith("pdf_b2_"):
            self.stats["B2"] += 1
            return "B2"

        # RULE 2: B1 (If ID starts with 'pdf_' but NOT 'pdf_b2_')
        if gp_id.startswith("pdf_"):
            self.stats["B1"] += 1
            return "B1"

        # RULE 3: A1/A2 (Numeric IDs)
        # Check for A1 -> A2 Transition (ID 237 or Title match)
        if self.numeric_level == "A1":
            if gp_id == "237" or ("形容词" in title and "死了" in title):
                self.numeric_level = "A2"
        
        self.stats[self.numeric_level] += 1
        return self.numeric_level

def slugify_for_uri(text: str) -> str:
    if not text: return "unknown"
    slug = re.sub(r'[^\w\u4e00-\u9fff]', '_', text)
    slug = re.sub(r'_+', '_', slug)
    return slug.strip('_')

def escape_turtle_string(text: str) -> str:
    if not text: return '""'
    text = text.replace('\\', '\\\\').replace('"', '\\"')
    text = text.replace('\n', '\\n').replace('\r', '\\r')
    return f'"{text}"'

def format_literal(value: Any, lang: str = None) -> str:
    if value is None: return ""
    escaped = escape_turtle_string(str(value))
    return f'{escaped}@{lang}' if lang else escaped

def convert_grammar_point_to_ttl(gp: Dict[str, Any], calculator: LevelCalculator) -> str:
    title = gp.get('grammar_point_cn', 'Unknown')
    
    # *** STRICT LEVEL CALCULATION ***
    level = calculator.get_level(gp)
    
    uri = f":Grammar_{slugify_for_uri(title)}"
    
    lines = [f"{uri} a srs-kg:GrammarPoint ;"]
    lines.append(f'    rdfs:label {format_literal(title, "zh")} ;')
    lines.append(f'    srs-kg:explanation {format_literal(gp.get("summary_cn", ""), "zh")} ;')
    lines.append(f'    srs-kg:cefrLevel {format_literal(level)} ;') # Correct Level

    if gp.get("anchor_example"):
        lines.append(f'    srs-kg:anchorExample {format_literal(gp["anchor_example"], "zh")} ;')
        
    for s in gp.get('pragmatic_scenarios', []):
        if s: lines.append(f'    srs-kg:pragmaticContext {format_literal(s, "zh")} ;')
        
    for k in gp.get('mandatory_keywords', []):
        if k: lines.append(f'    srs-kg:keyword {format_literal(k)} ;')

    is_useful = "true" if gp.get('is_useful_for_child') else "false"
    lines.append(f'    srs-kg:isChildFriendly {is_useful} ;')
    
    lines.append(f'    srs-kg:sourceType {format_literal(gp.get("source_type", "epub"))} .')
    
    return '\n'.join(lines)

def export_json_to_ttl():
    if not GRAMMAR_JSON.exists(): return
    with open(GRAMMAR_JSON, 'r', encoding='utf-8') as f: data = json.load(f)
    
    calculator = LevelCalculator()
    ttl_lines = [PREFIXES, ""]
    
    for gp in data:
        ttl_lines.append(convert_grammar_point_to_ttl(gp, calculator))
        ttl_lines.append("")
        
    with open(OUTPUT_TTL, 'w', encoding='utf-8') as f: f.write('\n'.join(ttl_lines))
    
    print("-" * 40)
    print(f"✅ Exported {len(data)} items to {OUTPUT_TTL}")
    print("📊 CORRECTED LEVEL STATISTICS:")
    for lvl in ["A1", "A2", "B1", "B2"]:
        print(f"   {lvl}: {calculator.stats[lvl]}")
    print("-" * 40)

if __name__ == "__main__":
    export_json_to_ttl()
