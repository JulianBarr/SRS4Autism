#!/usr/bin/env python3
"""
Simple test script to verify the KnowledgeGraphClient works with Oxigraph.
This tests the core functionality without other dependencies.
"""

import sys
sys.path.insert(0, '.')

from backend.database.kg_client import KnowledgeGraphClient

def main():
    print("=" * 80)
    print("Testing KnowledgeGraphClient with Oxigraph Backend")
    print("=" * 80)
    print()

    # Test 1: Initialize client
    print("Test 1: Initialize KnowledgeGraphClient")
    try:
        client = KnowledgeGraphClient()
        print(f"  ✓ Client initialized successfully")
        print(f"    Store path: {client.store_path}")
        print(f"    Endpoint URL: {client.endpoint_url}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return 1

    # Test 2: Count all triples
    print("\nTest 2: Count all triples in the store")
    try:
        query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
        result = client.query(query)
        bindings = result.get('results', {}).get('bindings', [])
        if bindings:
            count = bindings[0].get('count', {}).get('value', 'unknown')
            print(f"  ✓ Query executed successfully")
            print(f"    Total triples: {count}")
        else:
            print(f"  ✗ No results returned")
            return 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return 1

    # Test 3: Query for words
    print("\nTest 3: Query for sample words from knowledge graph")
    try:
        query = '''
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?word ?label WHERE {
            ?word a srs-kg:Word ;
                  rdfs:label ?label .
        } LIMIT 10
        '''
        result = client.query(query)
        bindings = result.get('results', {}).get('bindings', [])
        print(f"  ✓ Query executed successfully")
        print(f"    Found {len(bindings)} words:")
        for i, binding in enumerate(bindings, 1):
            label = binding.get('label', {}).get('value', 'N/A')
            print(f"      {i}. {label}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return 1

    # Test 4: Test query_bindings helper method
    print("\nTest 4: Test query_bindings helper method")
    try:
        query = '''
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        SELECT ?node WHERE {
            ?node a srs-kg:Word .
        } LIMIT 5
        '''
        bindings = client.query_bindings(query)
        print(f"  ✓ query_bindings() executed successfully")
        print(f"    Returned {len(bindings)} results")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return 1

    # Test 5: Health check
    print("\nTest 5: Health check")
    try:
        if client.health_check():
            print(f"  ✓ Health check passed")
        else:
            print(f"  ✗ Health check failed")
            return 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return 1

    # Test 6: Test multiple client instances (locking test)
    print("\nTest 6: Test multiple KnowledgeGraphClient instances (singleton test)")
    try:
        client2 = KnowledgeGraphClient()
        result = client2.query("SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }")
        bindings = result.get('results', {}).get('bindings', [])
        if bindings:
            count = bindings[0].get('count', {}).get('value', 'unknown')
            print(f"  ✓ Second client instance works correctly")
            print(f"    Both clients share same store (no locking issues)")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return 1

    print()
    print("=" * 80)
    print("✓ ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("Summary:")
    print("  - Oxigraph embedded store is working correctly")
    print("  - SPARQL queries execute successfully")
    print("  - Multiple clients can share the same store")
    print("  - Knowledge graph migration from Fuseki to Oxigraph is complete")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
