#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify that the IRI migration was successful.

This script checks that:
1. Fuseki is serving readable IRIs (not percent-encoded)
2. SPARQL queries still work correctly
3. Word lookups function properly
"""

import sys
import requests
from urllib.parse import urlencode

FUSEKI_ENDPOINT = "http://localhost:3030/srs4autism/query"

def query_sparql(sparql_query, output_format="application/sparql-results+json"):
    """Execute a SPARQL query against Jena Fuseki."""
    try:
        params = urlencode({"query": sparql_query})
        url = f"{FUSEKI_ENDPOINT}?{params}"
        response = requests.get(url, headers={"Accept": output_format}, timeout=10)
        response.raise_for_status()
        if output_format == "application/sparql-results+json":
            return response.json()
        return response.text
    except Exception as e:
        print(f"❌ Error querying Fuseki: {e}")
        return None

def test_readable_iris():
    """Test that IRIs are readable (not percent-encoded)."""
    print("=" * 80)
    print("Test 1: Checking IRI format (should be readable, not percent-encoded)")
    print("=" * 80)
    
    sparql = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT DISTINCT ?word WHERE {
        ?word a srs-kg:Word .
    } LIMIT 10
    """
    
    results = query_sparql(sparql)
    if not results:
        print("❌ Failed to query Fuseki. Is it running?")
        return False
    
    bindings = results.get("results", {}).get("bindings", [])
    if not bindings:
        print("❌ No words found in knowledge graph")
        return False
    
    has_percent_encoded = False
    has_readable = False
    
    print("\nSample word IRIs:")
    for i, row in enumerate(bindings[:5], 1):
        word_uri = row.get("word", {}).get("value", "")
        print(f"  {i}. {word_uri}")
        
        if "%" in word_uri:
            has_percent_encoded = True
        if any(ord(c) > 127 for c in word_uri):  # Contains non-ASCII (Chinese chars)
            has_readable = True
    
    if has_percent_encoded:
        print("\n❌ FAILED: Found percent-encoded IRIs (old format)")
        return False
    
    if has_readable:
        print("\n✅ PASSED: Found readable IRIs with Chinese characters")
        return True
    else:
        print("\n⚠️  WARNING: No Chinese characters in IRIs (might be English words only)")
        return True

def test_word_lookup():
    """Test that word lookups by text still work."""
    print("\n" + "=" * 80)
    print("Test 2: Word lookup by text property (should work regardless of IRI format)")
    print("=" * 80)
    
    test_words = ["主要", "朋友", "一"]
    
    for word in test_words:
        sparql = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?word ?pinyin ?hsk WHERE {{
            ?word a srs-kg:Word ;
                  srs-kg:text "{word}"@zh .
            OPTIONAL {{ ?word srs-kg:pinyin ?pinyin . }}
            OPTIONAL {{ ?word srs-kg:hskLevel ?hsk . }}
        }}
        """
        
        results = query_sparql(sparql)
        if not results:
            print(f"❌ Failed to query for word: {word}")
            continue
        
        bindings = results.get("results", {}).get("bindings", [])
        if bindings:
            word_uri = bindings[0].get("word", {}).get("value", "")
            pinyin = bindings[0].get("pinyin", {}).get("value", "")
            hsk = bindings[0].get("hsk", {}).get("value", "")
            print(f"✅ Found '{word}': {word_uri}")
            if pinyin:
                print(f"   Pinyin: {pinyin}")
            if hsk:
                print(f"   HSK Level: {hsk}")
        else:
            print(f"⚠️  Word '{word}' not found in knowledge graph")

def test_chinese_iri():
    """Test that we can find words with Chinese characters in their IRIs."""
    print("\n" + "=" * 80)
    print("Test 3: Finding words with Chinese characters in IRIs")
    print("=" * 80)
    
    sparql = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT DISTINCT ?word WHERE {
        ?word a srs-kg:Word .
        FILTER(CONTAINS(STR(?word), "一"))
    } LIMIT 5
    """
    
    results = query_sparql(sparql)
    if not results:
        print("❌ Failed to query Fuseki")
        return False
    
    bindings = results.get("results", {}).get("bindings", [])
    if bindings:
        print(f"\n✅ Found {len(bindings)} words with '一' in IRI:")
        for row in bindings:
            word_uri = row.get("word", {}).get("value", "")
            print(f"   {word_uri}")
        return True
    else:
        print("⚠️  No words found with Chinese characters in IRI")
        return False

def main():
    """Run all verification tests."""
    print("\n" + "=" * 80)
    print("IRI Migration Verification")
    print("=" * 80)
    print("\nMake sure Fuseki has been restarted with the new world_model_cwn.ttl file!")
    print("If using file-based dataset: ./fuseki-server --file=world_model_cwn.ttl /srs4autism\n")
    
    test1 = test_readable_iris()
    test_word_lookup()
    test3 = test_chinese_iri()
    
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    if test1 and test3:
        print("✅ Migration successful! IRIs are readable and queries work.")
    elif test1:
        print("⚠️  Migration partially successful. IRIs are readable but some tests failed.")
    else:
        print("❌ Migration may have failed. Please check Fuseki configuration.")
    print()

if __name__ == "__main__":
    main()


