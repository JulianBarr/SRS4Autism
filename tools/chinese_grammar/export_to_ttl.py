#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Chinese Grammar Points from JSON to TTL (Debug Version).
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

class LevelInjector:
    def __init__(self):
        self.current_level = "A1"
        self.stats = {"A1": 0, "A2": 0, "B1": 0, "Unknown": 0}

    def update_and_get(self, gp_id: str, title: str) -> str:
        # Normalize inputs for matching
        sid = str(gp_id).strip()
        stitle = title.strip()
        
        # --- DEBUG CHECK ---
        # Check for "形容词 + 死了" (Target: A2)
        # ID: 237
        if self.current_level == "A1":
            if sid == "237" or "形容词" in stitle and "死了" in stitle:
                print(f"\n[DEBUG] 🚨 FOUND TRANSITION TRIGGER A1 -> A2")
                print(f"        ID: {sid} | Title: {stitle}")
                self.current_level = "A2"

        # Check for "形容词 + 极了" (Target: B1)
        # ID: pdf_0
        if self.current_level == "A2":
            if sid == "pdf_0" or "形容词" in stitle and "极了" in stitle:
                print(f"\n[DEBUG] 🚨 FOUND TRANSITION TRIGGER A2 -> B1")
                print(f"        ID: {sid} | Title: {stitle}")
                self.current_level = "B1"
        
        # Record stats
        if self.current_level in self.stats:
            self.stats[self.current_level] += 1
            
        return self.current_level

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

def convert_grammar_point_to_ttl(gp: Dict[str, Any], level_injector: LevelInjector) -> str:
    title = gp.get('grammar_point_cn', 'Unknown')
    gp_id = gp.get('id', '??')
    
    # Calculate Level
    level = level_injector.update_and_get(gp_id, title)
    
    # URI
    uri = f":Grammar_{slugify_for_uri(title)}"
    
    lines = [f"{uri} a srs-kg:GrammarPoint ;"]
    lines.append(f'    rdfs:label {format_literal(title, "zh")} ;')
    lines.append(f'    srs-kg:explanation {format_literal(gp.get("summary_cn", ""), "zh")} ;')
    
    # *** HERE IS THE LEVEL ***
    lines.append(f'    srs-kg:cefrLevel {format_literal(level)} ;')

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
    if not GRAMMAR_JSON.exists(): 
        print("❌ JSON file not found!")
        return

    print(f"📂 Reading: {GRAMMAR_JSON}")
    with open(GRAMMAR_JSON, 'r', encoding='utf-8') as f: 
        data = json.load(f)
    
    injector = LevelInjector()
    
    ttl_lines = [PREFIXES, ""]
    
    print("-" * 40)
    for i, gp in enumerate(data):
        # Quick progress visual
        if i % 50 == 0: print(f"... processed {i} items")
        
        block = convert_grammar_point_to_ttl(gp, injector)
        ttl_lines.append(block)
        ttl_lines.append("")
        
    with open(OUTPUT_TTL, 'w', encoding='utf-8') as f: 
        f.write('\n'.join(ttl_lines))
    
    print("-" * 40)
    print(f"✅ Export Complete: {OUTPUT_TTL}")
    print("📊 LEVEL STATISTICS:")
    print(f"   A1 Count: {injector.stats['A1']}")
    print(f"   A2 Count: {injector.stats['A2']}")
    print(f"   B1 Count: {injector.stats['B1']}")
    print("-" * 40)

    if injector.stats['A2'] == 0:
        print("❌ ERROR: Level A2 was never triggered! Check ID '237' or title '形容词 + 死了'")
    if injector.stats['B1'] == 0:
        print("❌ ERROR: Level B1 was never triggered! Check ID 'pdf_0' or title '形容词 + 极了'")

if __name__ == "__main__":
    export_json_to_ttl()
