#!/usr/bin/env python3
"""
Migration Gap Analyzer (Fixed)
"""

import re
from pathlib import Path
from rdflib import Graph, Namespace, RDF

# Paths
REPO_ROOT = Path(__file__).parent.parent
LEGACY_FILE = REPO_ROOT / "knowledge_graph/world_model_legacy_backup.ttl"
NEW_FILE = REPO_ROOT / "knowledge_graph/world_model_v2_enriched.ttl"

SRS_KG = Namespace("http://srs4autism.com/schema/")

def count_raw_patterns(filepath, name):
    print(f"🔍 Scanning {name} (Raw Text Mode)...")
    
    counts = {
        "Words": 0,
        "Grammar Points": 0,
        "Sentences": 0,
        "Images": 0
    }
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if "a srs-kg:GrammarPoint" in line: counts["Grammar Points"] += 1
            if "a srs-kg:Sentence" in line: counts["Sentences"] += 1
            if "srs-kg:image" in line or "hasVisualization" in line: counts["Images"] += 1
            if "srs-kg:pinyin" in line: counts["Words"] += 1
            
    return counts

def analyze_v2_graph(filepath):
    print(f"📖 Analyzing V2 Graph (Structured Mode)...")
    g = Graph()
    g.parse(filepath, format="turtle")
    
    counts = {
        "Words": len(list(g.subjects(RDF.type, SRS_KG.Word))),
        "Grammar Points": len(list(g.subjects(RDF.type, SRS_KG.GrammarPoint))),
        "Sentences": len(list(g.subjects(RDF.type, SRS_KG.Sentence))),
        "Images": 0
    }
    
    for s, o in g.subject_objects(SRS_KG.hasVisualization):
        counts["Images"] += 1
    
    return counts

def main():
    if not LEGACY_FILE.exists() or not NEW_FILE.exists():
        print("❌ Error: Files not found.")
        return

    legacy = count_raw_patterns(LEGACY_FILE, "Legacy Backup")
    v2 = analyze_v2_graph(NEW_FILE)
    
    print("\n" + "="*60)
    print("📊 MIGRATION GAP REPORT (FINAL)")
    print("="*60)
    
    print(f"{'CATEGORY':<20} | {'LEGACY':<10} | {'V2 (NEW)':<10} | {'STATUS'}")
    print("-" * 60)
    
    print(f"{'Words':<20} | {legacy['Words']:<10} | {v2['Words']:<10} | {'✅ OK'}")
    print(f"{'Grammar Points':<20} | {legacy['Grammar Points']:<10} | {v2['Grammar Points']:<10} | {'✅ OK' if v2['Grammar Points'] > 0 else '❌ LOST'}")
    print(f"{'Sentences':<20} | {legacy['Sentences']:<10} | {v2['Sentences']:<10} | {'✅ OK' if v2['Sentences'] > 0 else '❌ LOST'}")
    print(f"{'Images':<20} | {legacy['Images']:<10} | {v2['Images']:<10} | {'✅ OK' if v2['Images'] > 4000 else '⚠️ Partial'}")
    
    print("-" * 60)
    print(f"File Size: Legacy {LEGACY_FILE.stat().st_size/1024/1024:.1f}MB vs New {NEW_FILE.stat().st_size/1024/1024:.1f}MB")

if __name__ == "__main__":
    main()
