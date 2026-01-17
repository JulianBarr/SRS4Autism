#!/usr/bin/env python3
"""
Load knowledge graph TTL files into the Oxigraph embedded store.

This script loads the knowledge graph data from TTL files into the
Oxigraph store used by the application. Run this once after setting
up the Oxigraph store or when updating the knowledge graph data.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.kg_client import KnowledgeGraphClient

def load_knowledge_graph():
    """Load knowledge graph files into Oxigraph store."""

    print("📦 Loading Knowledge Graph into Oxigraph...")

    # Initialize client (will use embedded Oxigraph store)
    client = KnowledgeGraphClient()

    # Determine which TTL file to load
    # Priority: world_model_complete.ttl (has all Chinese + English data)
    kg_files = [
        PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl",
        PROJECT_ROOT / "knowledge_graph" / "world_model.ttl",  # Fallback
    ]

    kg_file = None
    for file in kg_files:
        if file.exists():
            kg_file = file
            break

    if not kg_file:
        print("❌ Error: No knowledge graph TTL file found!")
        print(f"   Looked for files in: {PROJECT_ROOT / 'knowledge_graph'}")
        return False

    print(f"📁 Loading file: {kg_file.name}")
    print(f"   Path: {kg_file}")

    try:
        # Load the TTL file into the store
        client.load_file(str(kg_file))
        print("✅ Knowledge graph loaded successfully!")

        # Verify by running a simple query
        print("\n🔍 Verifying data load...")
        verify_query = """
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        SELECT (COUNT(?word) as ?count) WHERE {
            ?word a srs-kg:Word .
        }
        """
        result = client.query(verify_query)
        bindings = result.get("results", {}).get("bindings", [])

        if bindings:
            count = bindings[0].get("count", {}).get("value", "0")
            print(f"✅ Verification successful: {count} words found in knowledge graph")
        else:
            print("⚠️  Warning: Verification query returned no results")

        return True

    except Exception as e:
        print(f"❌ Error loading knowledge graph: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = load_knowledge_graph()
    sys.exit(0 if success else 1)
