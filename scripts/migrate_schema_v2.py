#!/usr/bin/env python3
"""
Schema Migration Script (v2)
---------------------------
Migrates Knowledge Graph data to match the new ontology standard (v2.0).

Transformations:
1. srs-kg:text -> rdfs:label
   - If node has both, keep rdfs:label.
   - If only srs-kg:text, convert to rdfs:label.
2. srs-kg:demonstratesGrammar -> srs-kg:illustratesGrammar
3. Audit srs-kg:hasPinyin for Literal values (should be URIs).

Usage:
    python scripts/migrate_schema_v2.py [path/to/graph.ttl]
"""

import sys
import logging
from pathlib import Path
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")

def migrate_graph(file_path):
    path = Path(file_path)
    if not path.exists():
        logger.error(f"File not found: {path}")
        return

    logger.info(f"Loading graph from {path}...")
    g = Graph()
    try:
        g.parse(path, format="turtle")
    except Exception as e:
        logger.error(f"Failed to parse {path}: {e}")
        return

    logger.info(f"Initial triple count: {len(g)}")
    
    # Track changes
    changes_made = 0
    
    # 1. Migrate srs-kg:text -> rdfs:label
    # Find all subjects with srs-kg:text
    text_triples = list(g.triples((None, SRS_KG.text, None)))
    logger.info(f"Found {len(text_triples)} triples with srs-kg:text")

    for s, p, o in text_triples:
        # Check if rdfs:label already exists
        labels = list(g.objects(s, RDFS.label))
        
        if labels:
            # Already has label
            # Check if values match
            if o in labels:
                logger.debug(f"Redundant srs-kg:text for {s}, matching rdfs:label. Removing.")
                g.remove((s, SRS_KG.text, o))
                changes_made += 1
            else:
                # Conflict found: Preserve as synonym
                logger.info(f"Preserved alias '{o}' for {s} (Label: '{labels[0]}')")
                g.add((s, SKOS.altLabel, o))
                g.remove((s, SRS_KG.text, o))
                changes_made += 1
        else:
            # No label, convert text to label
            g.add((s, RDFS.label, o))
            g.remove((s, SRS_KG.text, o))
            changes_made += 1
            
    # 2. Migrate srs-kg:demonstratesGrammar -> srs-kg:illustratesGrammar
    grammar_triples = list(g.triples((None, SRS_KG.demonstratesGrammar, None)))
    logger.info(f"Found {len(grammar_triples)} triples with srs-kg:demonstratesGrammar")
    
    for s, p, o in grammar_triples:
        g.add((s, SRS_KG.illustratesGrammar, o))
        g.remove((s, SRS_KG.demonstratesGrammar, o))
        changes_made += 1

    # 3. Audit srs-kg:hasPinyin
    pinyin_triples = list(g.triples((None, SRS_KG.hasPinyin, None)))
    logger.info(f"Auditing {len(pinyin_triples)} srs-kg:hasPinyin triples")
    
    literal_pinyin_count = 0
    for s, p, o in pinyin_triples:
        if isinstance(o, Literal):
            logger.warning(f"Legacy Pinyin format (Literal) found for {s}: '{o}'. Should be URI.")
            literal_pinyin_count += 1
            
    if literal_pinyin_count > 0:
        logger.warning(f"Found {literal_pinyin_count} srs-kg:hasPinyin triples pointing to Literals.")

    # Save output
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        # Force _v3 suffix as per user request (legacy default)
        output_path = path.with_name(f"{path.stem}_v3{path.suffix}")
    
    logger.info(f"Saving migrated graph to {output_path}...")
    g.serialize(destination=output_path, format="turtle")
    
    logger.info(f"Migration complete. {changes_made} changes applied.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
    else:
        # Default to rescued file as per user request
        target_file = "knowledge_graph/world_model_rescued.ttl"
        
    migrate_graph(target_file)
