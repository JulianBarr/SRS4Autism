#!/usr/bin/env python3
"""
Merge Chinese and English knowledge graph files into one unified file.
"""
import sys
from pathlib import Path
from rdflib import Graph

PROJECT_ROOT = Path(__file__).parent.parent.parent
CHINESE_KG = PROJECT_ROOT / "knowledge_graph" / "world_model_cwn.ttl"
ENGLISH_KG = PROJECT_ROOT / "knowledge_graph" / "world_model_english.ttl"
MERGED_KG = PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl"

def main():
    print("Merging Chinese and English knowledge graphs...")
    
    merged = Graph()
    
    # Load Chinese KG
    if CHINESE_KG.exists():
        print(f"Loading Chinese KG: {CHINESE_KG}")
        merged.parse(str(CHINESE_KG), format="turtle")
        print(f"✅ Loaded {len(merged)} triples from Chinese KG")
    else:
        print(f"⚠️  Chinese KG not found: {CHINESE_KG}")
    
    # Load English KG
    if ENGLISH_KG.exists():
        print(f"Loading English KG: {ENGLISH_KG}")
        english_graph = Graph()
        english_graph.parse(str(ENGLISH_KG), format="turtle")
        print(f"✅ Loaded {len(english_graph)} triples from English KG")
        
        # Merge
        for triple in english_graph:
            merged.add(triple)
        print(f"✅ Merged English KG into combined graph")
    else:
        print(f"⚠️  English KG not found: {ENGLISH_KG}")
    
    # Save merged file
    print(f"\nSaving merged KG to: {MERGED_KG}")
    merged.serialize(destination=str(MERGED_KG), format="turtle")
    print(f"✅ Saved {len(merged)} total triples to merged file")
    print(f"\n📝 Next step: Restart Fuseki with the merged file:")
    print(f"   ./fuseki-server --file={MERGED_KG} /srs4autism")

if __name__ == "__main__":
    main()

