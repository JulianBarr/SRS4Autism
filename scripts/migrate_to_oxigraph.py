#!/usr/bin/env python3
"""
Migration script to load TTL files from Fuseki into embedded Oxigraph store.

This script:
1. Initializes a new Oxigraph store using the KnowledgeGraphClient
2. Finds all .ttl files in the knowledge_graph/ directory (excluding backups)
3. Loads them into the new embedded store
4. Reports on the migration status
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database.kg_client import KnowledgeGraphClient, KnowledgeGraphError


def find_ttl_files(base_path: Path) -> list[Path]:
    """
    Find all .ttl files in the knowledge_graph directory, excluding backups.

    Args:
        base_path: Base path to search from

    Returns:
        List of Path objects for .ttl files
    """
    kg_dir = base_path / "knowledge_graph"
    if not kg_dir.exists():
        print(f"Warning: {kg_dir} does not exist")
        return []

    ttl_files = []
    for ttl_file in kg_dir.rglob("*.ttl"):
        # Skip backup directories
        if "backup" not in str(ttl_file):
            ttl_files.append(ttl_file)

    return sorted(ttl_files)


def get_file_priority(file_path: Path) -> int:
    """
    Determine loading priority for TTL files.
    Lower number = higher priority (loaded first).

    Args:
        file_path: Path to the TTL file

    Returns:
        Priority number (0 = highest priority)
    """
    filename = file_path.name.lower()

    # Load schema/ontology files first
    if "schema" in filename or "ontology" in filename:
        return 0

    # Then load core/base files
    if filename in ["world_model.ttl", "world_model_complete.ttl", "world_model_final.ttl"]:
        return 1

    # Everything else
    return 2


def main():
    """Main migration function."""
    print("=" * 80)
    print("Oxigraph Migration Script")
    print("=" * 80)
    print()

    # Initialize the client
    print("Initializing Oxigraph store...")
    try:
        client = KnowledgeGraphClient()
        print(f"✓ Store initialized at: {client.store_path}")
    except KnowledgeGraphError as e:
        print(f"✗ Failed to initialize store: {e}")
        return 1

    print()

    # Find TTL files
    print("Finding TTL files...")
    ttl_files = find_ttl_files(project_root)

    if not ttl_files:
        print("✗ No TTL files found in knowledge_graph/ directory")
        return 1

    print(f"✓ Found {len(ttl_files)} TTL files")
    print()

    # Sort by priority
    ttl_files.sort(key=get_file_priority)

    # Load files
    print("Loading files into Oxigraph store...")
    print("-" * 80)

    loaded = 0
    failed = 0

    for ttl_file in ttl_files:
        relative_path = ttl_file.relative_to(project_root)
        print(f"Loading: {relative_path}")

        try:
            # Format will be auto-detected from .ttl extension
            client.load_file(str(ttl_file))
            print(f"  ✓ Success")
            loaded += 1
        except KnowledgeGraphError as e:
            print(f"  ✗ Failed: {e}")
            failed += 1

        print()

    # Summary
    print("-" * 80)
    print("Migration Summary:")
    print(f"  Total files found: {len(ttl_files)}")
    print(f"  Successfully loaded: {loaded}")
    print(f"  Failed: {failed}")
    print()

    # Test the store
    print("Testing the store...")
    try:
        if client.health_check():
            print("✓ Health check passed")

            # Try a simple query to count triples
            count_query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
            results = client.query(count_query)
            bindings = results.get("results", {}).get("bindings", [])

            if bindings:
                triple_count = bindings[0].get("count", {}).get("value", "unknown")
                print(f"✓ Store contains {triple_count} triples")
        else:
            print("✗ Health check failed")
            return 1
    except KnowledgeGraphError as e:
        print(f"✗ Health check failed: {e}")
        return 1

    print()
    print("=" * 80)
    if failed == 0:
        print("Migration completed successfully!")
    else:
        print(f"Migration completed with {failed} errors")
    print("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
