#!/usr/bin/env python3
"""
Migrate mastered grammar URIs from old format to new format.

When grammar points were repopulated, they got new URIs. This script:
1. Loads old URIs from the database
2. Tries to match them to new URIs in the knowledge graph
3. Updates the database with the new URIs
"""

import sys
import sqlite3
import requests
from pathlib import Path
from urllib.parse import urlencode
from typing import Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

DB_PATH = project_root / "data" / "srs4autism.db"
FUSEKI_ENDPOINT = "http://localhost:3030/srs4autism/query"


def get_all_grammar_points_from_kg() -> Dict[str, Dict]:
    """Get all grammar points from knowledge graph, indexed by various keys"""
    sparql = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT DISTINCT ?gp_uri ?label_en ?label_zh ?cefr ?structure WHERE {
        ?gp_uri a srs-kg:GrammarPoint .
        FILTER(!CONTAINS(STR(?gp_uri), "grammar-en-"))
        OPTIONAL { ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en" || LANG(?label_en) = "") }
        OPTIONAL { ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }
        OPTIONAL { ?gp_uri srs-kg:cefrLevel ?cefr }
        OPTIONAL { ?gp_uri srs-kg:structure ?structure }
    }
    """
    
    try:
        params = urlencode({"query": sparql})
        url = f"{FUSEKI_ENDPOINT}?{params}"
        response = requests.get(url, headers={"Accept": "application/sparql-results+json"}, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        grammar_points = {}
        for binding in data.get('results', {}).get('bindings', []):
            uri = binding['gp_uri']['value']
            label_en = binding.get('label_en', {}).get('value', '')
            label_zh = binding.get('label_zh', {}).get('value', '')
            cefr = binding.get('cefr', {}).get('value', '')
            structure = binding.get('structure', {}).get('value', '')
            
            grammar_points[uri] = {
                'label_en': label_en,
                'label_zh': label_zh,
                'cefr': cefr,
                'structure': structure
            }
        
        return grammar_points
    except Exception as e:
        print(f"❌ Error querying knowledge graph: {e}")
        return {}


def extract_grammar_info_from_old_uri(old_uri: str) -> Dict[str, str]:
    """Extract information from old URI to help match"""
    # Old format: gp-a1-001-basic-sentence-structure
    # Extract level and number
    parts = old_uri.split('/')[-1].split('-')
    info = {}
    
    if len(parts) >= 3:
        level_part = parts[1].upper()  # a1 -> A1
        number_part = parts[2]  # 001
        info['level'] = level_part
        info['number'] = number_part
        info['slug'] = '-'.join(parts[3:]) if len(parts) > 3 else ''
    
    return info


def find_matching_new_uri(old_uri: str, grammar_points: Dict[str, Dict]) -> Optional[str]:
    """Try to find a matching new URI for an old URI"""
    old_info = extract_grammar_info_from_old_uri(old_uri)
    
    if not old_info.get('level') or not old_info.get('number'):
        return None
    
    # Strategy 1: Match by level and number in URI
    # Look for URIs containing the level and number (e.g., gp-A1-001 or gp-a1-001)
    level = old_info['level']
    number = old_info['number']
    
    candidates = []
    for new_uri, gp_data in grammar_points.items():
        uri_lower = new_uri.lower()
        # Check if URI contains the level and number
        if f"gp-{level.lower()}-{number}" in uri_lower or f"gp-{level}-{number}" in uri_lower:
            candidates.append((new_uri, gp_data))
    
    if len(candidates) == 1:
        return candidates[0][0]
    elif len(candidates) > 1:
        # Multiple candidates - this shouldn't happen, but if it does, return the first
        print(f"⚠️  Multiple candidates for {old_uri}, using first match")
        return candidates[0][0]
    
    return None


def migrate_uris(dry_run: bool = True) -> Tuple[int, int]:
    """Migrate old URIs to new URIs"""
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return 0, 0
    
    print("=" * 80)
    print("Migrate Mastered Grammar URIs")
    print("=" * 80)
    print()
    
    # Load all grammar points from KG
    print("📖 Loading grammar points from knowledge graph...")
    grammar_points = get_all_grammar_points_from_kg()
    print(f"✅ Loaded {len(grammar_points)} grammar points from KG")
    print()
    
    # Load old URIs from database
    print("📖 Loading mastered grammar from database...")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT profile_id, grammar_uri 
        FROM mastered_grammar 
        ORDER BY profile_id, grammar_uri
    """)
    old_entries = cursor.fetchall()
    print(f"✅ Found {len(old_entries)} mastered grammar entries")
    print()
    
    # Find mappings
    print("🔍 Finding URI mappings...")
    mappings = {}
    not_found = []
    
    for profile_id, old_uri in old_entries:
        if old_uri in grammar_points:
            # URI already exists (exact match)
            mappings[old_uri] = old_uri
        else:
            # Try to find matching new URI
            new_uri = find_matching_new_uri(old_uri, grammar_points)
            if new_uri:
                mappings[old_uri] = new_uri
            else:
                not_found.append((profile_id, old_uri))
    
    print(f"✅ Found mappings for {len(mappings)} URIs")
    if not_found:
        print(f"⚠️  Could not find matches for {len(not_found)} URIs:")
        for profile_id, uri in not_found[:10]:
            print(f"     {profile_id}: {uri}")
        if len(not_found) > 10:
            print(f"     ... and {len(not_found) - 10} more")
    print()
    
    # Update database
    if not dry_run and mappings:
        print("💾 Updating database...")
        updated_count = 0
        for old_uri, new_uri in mappings.items():
            if old_uri != new_uri:
                cursor.execute("""
                    UPDATE mastered_grammar 
                    SET grammar_uri = ? 
                    WHERE grammar_uri = ?
                """, (new_uri, old_uri))
                updated_count += 1
        
        conn.commit()
        print(f"✅ Updated {updated_count} URIs in database")
    elif dry_run:
        update_count = sum(1 for old, new in mappings.items() if old != new)
        print(f"🔍 Dry run: Would update {update_count} URIs")
    
    conn.close()
    
    print()
    print("=" * 80)
    if dry_run:
        print("DRY RUN COMPLETE - No changes made")
        print("Run with --apply to actually update the database")
    else:
        print("MIGRATION COMPLETE")
    print("=" * 80)
    
    return len(mappings), len(not_found)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Migrate mastered grammar URIs')
    parser.add_argument('--apply', action='store_true', help='Actually update the database (default is dry run)')
    args = parser.parse_args()
    
    migrate_uris(dry_run=not args.apply)

