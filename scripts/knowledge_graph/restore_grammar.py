#!/usr/bin/env python3
"""
Restore grammar points from backup to current world_model_cwn.ttl
"""

import sys
from pathlib import Path
from rdflib import Graph, Namespace

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Define namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")

BACKUP_FILE = project_root / "knowledge_graph" / "world_model_cwn.ttl.backup"
CURRENT_FILE = project_root / "knowledge_graph" / "world_model_cwn.ttl"
OUTPUT_FILE = project_root / "knowledge_graph" / "world_model_cwn_restored.ttl"

def main():
    print("=" * 80)
    print("Restoring Grammar Points from Backup")
    print("=" * 80)
    
    print("\nStep 1: Loading backup file...")
    backup_graph = Graph()
    backup_graph.bind("srs-kg", SRS_KG)
    backup_graph.parse(str(BACKUP_FILE), format="turtle")
    print(f"✅ Loaded {len(backup_graph)} triples from backup")
    
    print("\nStep 2: Loading current file...")
    current_graph = Graph()
    current_graph.bind("srs-kg", SRS_KG)
    current_graph.parse(str(CURRENT_FILE), format="turtle")
    print(f"✅ Loaded {len(current_graph)} triples from current file")
    
    print("\nStep 3: Extracting grammar points from backup...")
    grammar_triples = set()
    grammar_nodes = set()
    
    # Find all GrammarPoint nodes
    for s, p, o in backup_graph.triples((None, None, SRS_KG.GrammarPoint)):
        grammar_nodes.add(s)
    
    print(f"✅ Found {len(grammar_nodes)} grammar point nodes")
    
    # Extract all triples related to grammar points
    for grammar_node in grammar_nodes:
        # Get all triples where grammar node is subject
        for s, p, o in backup_graph.triples((grammar_node, None, None)):
            grammar_triples.add((s, p, o))
        # Get all triples where grammar node is object
        for s, p, o in backup_graph.triples((None, None, grammar_node)):
            grammar_triples.add((s, p, o))
    
    print(f"✅ Extracted {len(grammar_triples)} triples related to grammar points")
    
    print("\nStep 4: Adding grammar triples to current graph...")
    for triple in grammar_triples:
        current_graph.add(triple)
    
    print(f"✅ Current graph now has {len(current_graph)} triples")
    
    print("\nStep 5: Saving restored graph...")
    current_graph.serialize(destination=str(OUTPUT_FILE), format="turtle")
    print(f"✅ Saved to {OUTPUT_FILE}")
    
    print("\n" + "=" * 80)
    print("Summary:")
    print(f"  Grammar nodes restored: {len(grammar_nodes)}")
    print(f"  Grammar triples restored: {len(grammar_triples)}")
    print(f"  Total triples in restored file: {len(current_graph)}")
    print("=" * 80)
    
    print("\n⚠️  Manual step required:")
    print(f"  1. Review {OUTPUT_FILE}")
    print(f"  2. If correct, replace {CURRENT_FILE}")
    print(f"     mv {OUTPUT_FILE} {CURRENT_FILE}")
    print(f"  3. Re-merge KG files:")
    print(f"     cd scripts/knowledge_graph && python3 merge_kg_files.py")

if __name__ == "__main__":
    main()


