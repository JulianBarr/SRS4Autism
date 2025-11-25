#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Restore A1/A2 Chinese grammar points from knowledge graph to JSON file.

This script extracts A1 and A2 grammar points from the knowledge graph TTL files
and adds them back to the chinese_grammar_knowledge_graph.json file, which was
overwritten with only intermediate (B1+) grammar points.
"""

import os
import sys
import json
from pathlib import Path
from urllib.parse import unquote

try:
    from rdflib import Graph, Namespace, Literal
    from rdflib.namespace import RDF, RDFS
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Configuration
DATA_DIR = project_root / 'data' / 'content_db'
KG_FILES = [
    project_root / 'knowledge_graph' / 'world_model_cwn.ttl',
    project_root / 'knowledge_graph' / 'world_model.ttl',
    project_root / 'knowledge_graph' / 'world_model_merged.ttl'
]
GRAMMAR_FILE = DATA_DIR / 'chinese_grammar_knowledge_graph.json'

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
INST = Namespace("http://srs4autism.com/instance/")


def extract_grammar_from_kg(kg_file: Path) -> list:
    """Extract A1 and A2 Chinese grammar points from knowledge graph."""
    if not kg_file.exists():
        print(f"  ⚠️  File not found: {kg_file}")
        return []
    
    print(f"  📖 Loading {kg_file.name}...")
    graph = Graph()
    try:
        graph.parse(str(kg_file), format="turtle")
        print(f"     Loaded {len(graph)} triples")
    except Exception as e:
        print(f"     ⚠️  Error loading: {e}")
        return []
    
    # Query for A1 and A2 Chinese grammar points
    # Chinese grammar: URI does NOT start with "grammar-en-"
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX srs-inst: <http://srs4autism.com/instance/>
    
    SELECT DISTINCT ?gp_uri ?label_en ?label_zh ?structure ?explanation ?cefr WHERE {
        ?gp_uri a srs-kg:GrammarPoint .
        ?gp_uri srs-kg:cefrLevel ?cefr .
        FILTER(?cefr = "A1" || ?cefr = "A2")
        FILTER(!CONTAINS(STR(?gp_uri), "grammar-en-"))
        OPTIONAL { ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en" || LANG(?label_en) = "") }
        OPTIONAL { ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }
        OPTIONAL { ?gp_uri srs-kg:structure ?structure }
        OPTIONAL { ?gp_uri srs-kg:explanation ?explanation }
    }
    ORDER BY ?cefr ?label_en
    """
    
    results = graph.query(query)
    grammar_points = {}
    
    for row in results:
        gp_uri = str(row.gp_uri)
        cefr = str(row.cefr)
        
        # Get English label
        label_en = str(row.label_en) if row.label_en else ""
        
        # Get Chinese label
        label_zh = str(row.label_zh) if row.label_zh else ""
        
        # Get structure
        structure = str(row.structure) if row.structure else ""
        
        # Get explanation
        explanation = str(row.explanation) if row.explanation else ""
        
        # Use English label as grammar_point name, or Chinese if no English
        grammar_point_name = label_en if label_en else label_zh
        
        if gp_uri not in grammar_points:
            grammar_points[gp_uri] = {
                'grammar_point': grammar_point_name,
                'level': cefr,
                'structure': structure,
                'explanation': explanation,
                'examples': []
            }
    
    # Now get examples for each grammar point
    print(f"     📝 Extracting examples...")
    for gp_uri in grammar_points.keys():
        gp_uri_ref = INST[gp_uri.split('/')[-1]] if gp_uri.startswith(str(INST)) else None
        if not gp_uri_ref:
            # Try to find the URI in the graph
            for s in graph.subjects(RDF.type, SRS_KG.GrammarPoint):
                if str(s) == gp_uri:
                    gp_uri_ref = s
                    break
        
        if gp_uri_ref:
            # Find sentences that demonstrate this grammar
            example_query = """
            PREFIX srs-kg: <http://srs4autism.com/schema/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?sent_label ?pinyin ?translation WHERE {
                ?sent a srs-kg:Sentence .
                ?sent srs-kg:demonstratesGrammar ?gp .
                ?sent rdfs:label ?sent_label .
                FILTER(LANG(?sent_label) = "zh")
                OPTIONAL { ?sent srs-kg:pinyin ?pinyin }
                OPTIONAL { ?sent srs-kg:translationEN ?translation . FILTER(LANG(?translation) = "en") }
            }
            """
            
            # Query for sentences linked to this grammar point
            for sent in graph.subjects(SRS_KG.demonstratesGrammar, gp_uri_ref):
                chinese = None
                pinyin = None
                english = None
                
                # Get Chinese label
                for label in graph.objects(sent, RDFS.label):
                    if hasattr(label, 'language') and label.language == 'zh':
                        chinese = str(label)
                        break
                    elif not hasattr(label, 'language'):
                        chinese = str(label)
                
                # Get pinyin
                for p in graph.objects(sent, SRS_KG.pinyin):
                    pinyin = str(p)
                    break
                
                # Get English translation
                for trans in graph.objects(sent, SRS_KG.translationEN):
                    if hasattr(trans, 'language') and trans.language == 'en':
                        english = str(trans)
                        break
                    elif not hasattr(trans, 'language'):
                        english = str(trans)
                
                if chinese:
                    grammar_points[gp_uri]['examples'].append({
                        'chinese': chinese,
                        'pinyin': pinyin or '',
                        'english': english or ''
                    })
    
    return list(grammar_points.values())


def main():
    print("=" * 80)
    print("Restore A1/A2 Chinese Grammar Points from Knowledge Graph")
    print("=" * 80)
    print()
    
    # Extract grammar points from all KG files
    all_grammar = []
    seen_uris = set()
    
    for kg_file in KG_FILES:
        grammar_points = extract_grammar_from_kg(kg_file)
        for gp in grammar_points:
            # Use grammar_point name + level as unique key
            key = (gp['grammar_point'], gp['level'])
            if key not in seen_uris:
                all_grammar.append(gp)
                seen_uris.add(key)
    
    print(f"\n✅ Extracted {len(all_grammar)} unique A1/A2 grammar points")
    
    # Count by level
    a1_count = sum(1 for gp in all_grammar if gp['level'] == 'A1')
    a2_count = sum(1 for gp in all_grammar if gp['level'] == 'A2')
    print(f"   A1: {a1_count}")
    print(f"   A2: {a2_count}")
    
    # Load existing JSON file
    existing_grammar = []
    if GRAMMAR_FILE.exists():
        print(f"\n📖 Loading existing grammar file: {GRAMMAR_FILE}")
        try:
            with open(GRAMMAR_FILE, 'r', encoding='utf-8') as f:
                existing_grammar = json.load(f)
            print(f"   Found {len(existing_grammar)} existing grammar points")
            
            # Count existing by level
            existing_levels = {}
            for gp in existing_grammar:
                level = gp.get('level', 'Unknown')
                existing_levels[level] = existing_levels.get(level, 0) + 1
            print(f"   Existing levels: {existing_levels}")
        except Exception as e:
            print(f"   ⚠️  Error loading existing file: {e}")
            existing_grammar = []
    else:
        print(f"\n📝 Creating new grammar file: {GRAMMAR_FILE}")
    
    # Merge: Keep existing B1+ entries, add A1/A2 entries
    # Remove any existing A1/A2 entries first (in case they're incomplete)
    existing_grammar = [gp for gp in existing_grammar if gp.get('level') not in ['A1', 'A2']]
    
    # Combine: A1/A2 first, then existing
    merged_grammar = all_grammar + existing_grammar
    
    print(f"\n💾 Saving merged grammar file...")
    print(f"   Total grammar points: {len(merged_grammar)}")
    print(f"   A1/A2: {len(all_grammar)}")
    print(f"   B1+: {len(existing_grammar)}")
    
    # Create backup
    if GRAMMAR_FILE.exists():
        backup_file = GRAMMAR_FILE.with_suffix('.json.backup')
        print(f"\n📦 Creating backup: {backup_file}")
        import shutil
        shutil.copy2(GRAMMAR_FILE, backup_file)
    
    # Save merged file
    try:
        with open(GRAMMAR_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged_grammar, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully saved to {GRAMMAR_FILE}")
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("Restoration Complete!")
    print("=" * 80)
    print(f"\n📊 Final counts:")
    final_levels = {}
    for gp in merged_grammar:
        level = gp.get('level', 'Unknown')
        final_levels[level] = final_levels.get(level, 0) + 1
    for level, count in sorted(final_levels.items()):
        print(f"   {level}: {count}")


if __name__ == "__main__":
    main()

