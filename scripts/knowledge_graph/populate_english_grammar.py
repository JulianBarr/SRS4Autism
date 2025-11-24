#!/usr/bin/env python3
"""
Populate English Grammar Knowledge Graph from CEFR-J Grammar Profile

This script:
1. Loads the CEFR-J Grammar Profile CSV
2. Creates GrammarPoint nodes for each grammar item
3. Adds properties: cefrLevel, sentence type, examples
4. Links grammar points to prerequisites
5. Saves to world_model_english.ttl
"""

import csv
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Define namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
DBO = Namespace("http://dbpedia.org/ontology/")
DBR = Namespace("http://dbpedia.org/resource/")

# File paths
CEFR_J_GRAMMAR_CSV = Path("/Users/maxent/src/olp-en-cefrj/cefrj-grammar-profile-20180315.csv")
KG_FILE = project_root / "knowledge_graph" / "world_model_english.ttl"


def normalize_code_to_uri(shorthand_code: str) -> str:
    """
    Convert shorthand code to URI-safe format
    Example: PP.I_am -> grammar-en-pp-i-am
    """
    normalized = shorthand_code.lower().replace('.', '-').replace('_', '-')
    normalized = re.sub(r'[^a-z0-9\-]', '', normalized)
    return f"grammar-en-{normalized}"


def parse_cefr_level(level_str: str) -> Optional[str]:
    """
    Parse CEFR level from string
    Examples: 
    - A1.1 -> A1
    - B1.1 -> B1
    - A1-A2 -> A1 (take first level)
    - B1-C1 -> B1 (take first level)
    - empty -> None
    """
    if not level_str or level_str.strip() == '':
        return None
    
    # Handle ranges like "A1-A2", "B1-C1" - take the first level
    level_str = level_str.split('-')[0].split('ー')[0]  # Handle both - and ー (Japanese dash)
    level_str = level_str.split('(')[0]  # Handle "A1-(A2)-B1" -> "A1"
    
    # Extract base level (A1, A2, B1, B2, C1, C2)
    match = re.match(r'([ABC][12])', level_str.upper())
    if match:
        return match.group(1)
    
    return None


def extract_category_from_code(shorthand_code: str) -> str:
    """
    Extract category from shorthand code
    Example: PP.I_am -> PP (Present Progressive)
    """
    parts = shorthand_code.split('.')
    return parts[0] if parts else "GENERAL"


def categorize_sentence_type(sentence_type: str) -> str:
    """
    Categorize sentence type
    AFF. DEC. -> affirmative_declarative
    NEG. DEC. -> negative_declarative
    AFF. INT. -> affirmative_interrogative
    NEG. INT. -> negative_interrogative
    """
    mapping = {
        'AFF. DEC.': 'affirmative_declarative',
        'NEG. DEC.': 'negative_declarative',
        'AFF. INT.': 'affirmative_interrogative',
        'NEG. INT.': 'negative_interrogative',
        'IMP.': 'imperative',
        'EXC.': 'exclamative'
    }
    return mapping.get(sentence_type.strip(), 'declarative')


def determine_prerequisites(grammar_id: int, shorthand_code: str, cefr_level: Optional[str]) -> List[int]:
    """
    Determine prerequisite grammar points based on ID patterns and CEFR levels
    
    For example:
    - 1-1 (I am not) requires 1 (I am)
    - 1-2 (Am I?) requires 1 (I am)
    """
    prerequisites = []
    
    # Parse ID to find base form
    # IDs like "1-1", "1-2" are variants of "1"
    if isinstance(grammar_id, str) and '-' in grammar_id:
        base_id = grammar_id.split('-')[0]
        try:
            prerequisites.append(int(base_id))
        except ValueError:
            pass
    
    return prerequisites


def load_cefrj_grammar(csv_path: Path) -> List[Dict]:
    """Load CEFR-J Grammar Profile from CSV"""
    grammar_points = []
    
    print(f"📖 Loading CEFR-J Grammar Profile from: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip empty rows
            if not row.get('Shorthand Code'):
                continue
            
            # Try CEFR-J Level first, fall back to Core Inventory if empty
            cefr_j_level = row.get('CEFR-J Level', '').strip()
            core_inventory = row.get('Core Inventory', '').strip()
            
            cefr_level = parse_cefr_level(cefr_j_level)
            # If no CEFR level from CEFR-J Level column, try Core Inventory
            if not cefr_level and core_inventory and core_inventory != 'N/A':
                cefr_level = parse_cefr_level(core_inventory)
            
            grammar_point = {
                'id': row['ID'],
                'shorthand_code': row['Shorthand Code'],
                'grammatical_item': row['Grammatical Item'],
                'sentence_type': row.get('Sentence Type', ''),
                'cefr_level_raw': cefr_j_level or core_inventory,  # Store the source
                'cefr_level': cefr_level,
                'core_inventory': core_inventory,
                'notes': row.get('Notes', ''),
                'category': extract_category_from_code(row['Shorthand Code'])
            }
            
            grammar_points.append(grammar_point)
    
    print(f"✅ Loaded {len(grammar_points)} grammar points")
    return grammar_points


def populate_grammar_kg(graph: Graph, grammar_points: List[Dict]) -> Dict[str, int]:
    """Populate knowledge graph with grammar points"""
    stats = {
        'total': 0,
        'by_level': defaultdict(int),
        'by_category': defaultdict(int),
        'by_sentence_type': defaultdict(int)
    }
    
    print("\n🔨 Creating GrammarPoint nodes...")
    
    # Create a mapping of ID to URI for prerequisites
    id_to_uri = {}
    
    for gp in grammar_points:
        # Create grammar point URI
        uri_suffix = normalize_code_to_uri(gp['shorthand_code'])
        grammar_uri = SRS_KG[uri_suffix]
        
        # Store mapping
        id_to_uri[gp['id']] = grammar_uri
        
        # Create grammar point node
        graph.add((grammar_uri, RDF.type, SRS_KG.GrammarPoint))
        
        # Add label
        graph.add((grammar_uri, RDFS.label, Literal(gp['grammatical_item'], lang='en')))
        
        # Add shorthand code
        graph.add((grammar_uri, SRS_KG.code, Literal(gp['shorthand_code'])))
        
        # Add CEFR level if available
        if gp['cefr_level']:
            graph.add((grammar_uri, SRS_KG.cefrLevel, Literal(gp['cefr_level'])))
            stats['by_level'][gp['cefr_level']] += 1
        
        # Add category
        graph.add((grammar_uri, SRS_KG.category, Literal(gp['category'])))
        stats['by_category'][gp['category']] += 1
        
        # Add sentence type
        if gp['sentence_type']:
            sentence_type_normalized = categorize_sentence_type(gp['sentence_type'])
            graph.add((grammar_uri, SRS_KG.sentenceType, Literal(sentence_type_normalized)))
            stats['by_sentence_type'][sentence_type_normalized] += 1
        
        # Add notes if available
        if gp['notes']:
            graph.add((grammar_uri, SRS_KG.notes, Literal(gp['notes'])))
        
        # Add core inventory marker
        if gp['core_inventory']:
            graph.add((grammar_uri, SRS_KG.coreInventory, Literal(gp['core_inventory'])))
        
        stats['total'] += 1
    
    print(f"\n🔗 Adding prerequisite relationships...")
    
    # Second pass: add prerequisites
    prerequisite_count = 0
    for gp in grammar_points:
        grammar_uri = id_to_uri[gp['id']]
        
        # Determine prerequisites
        prerequisites = determine_prerequisites(gp['id'], gp['shorthand_code'], gp['cefr_level'])
        
        for prereq_id in prerequisites:
            prereq_id_str = str(prereq_id)
            if prereq_id_str in id_to_uri:
                prereq_uri = id_to_uri[prereq_id_str]
                graph.add((grammar_uri, SRS_KG.requiresPrerequisite, prereq_uri))
                prerequisite_count += 1
    
    print(f"✅ Added {prerequisite_count} prerequisite relationships")
    
    return dict(stats)


def main():
    print("=" * 80)
    print("Populate English Grammar Knowledge Graph from CEFR-J")
    print("=" * 80)
    
    # Check if CSV file exists
    if not CEFR_J_GRAMMAR_CSV.exists():
        print(f"❌ CEFR-J Grammar CSV not found: {CEFR_J_GRAMMAR_CSV}")
        sys.exit(1)
    
    # Load existing knowledge graph or create new
    print(f"\n📊 Loading existing knowledge graph: {KG_FILE}")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.bind("dbo", DBO)
    graph.bind("dbr", DBR)
    
    if KG_FILE.exists():
        try:
            graph.parse(str(KG_FILE), format="turtle")
            print(f"✅ Loaded {len(graph)} existing triples")
        except Exception as e:
            print(f"⚠️  Could not load existing graph: {e}")
            print("   Creating new graph...")
    else:
        print("📝 Creating new knowledge graph")
    
    # Load CEFR-J grammar data
    grammar_points = load_cefrj_grammar(CEFR_J_GRAMMAR_CSV)
    
    # Populate knowledge graph
    stats = populate_grammar_kg(graph, grammar_points)
    
    # Print statistics
    print("\n" + "=" * 80)
    print("📊 Statistics")
    print("=" * 80)
    print(f"Total grammar points: {stats['total']}")
    
    print(f"\n📈 By CEFR Level:")
    for level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
        count = stats['by_level'].get(level, 0)
        if count > 0:
            print(f"  {level}: {count}")
    
    print(f"\n📂 Top 10 Categories:")
    for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {category}: {count}")
    
    print(f"\n📝 By Sentence Type:")
    for stype, count in sorted(stats['by_sentence_type'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {stype}: {count}")
    
    # Save knowledge graph
    print(f"\n💾 Saving knowledge graph to: {KG_FILE}")
    graph.serialize(destination=str(KG_FILE), format="turtle")
    print(f"✅ Saved {len(graph)} triples")
    
    print("\n" + "=" * 80)
    print("✅ English Grammar Knowledge Graph population complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()

