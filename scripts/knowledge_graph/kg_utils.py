#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Knowledge Graph Utility Functions

Common utilities for KG modification scripts, including automatic backup.
"""

import os
import sys
from pathlib import Path

# Add this directory to path so we can import kg_backup
_script_dir = Path(__file__).parent
sys.path.insert(0, str(_script_dir))


def save_graph_with_backup(graph, kg_file_path, create_timestamped=True):
    """
    Save a knowledge graph with automatic backup.
    
    This is a convenience wrapper that:
    1. Creates a backup of the existing KG file (if it exists)
    2. Saves the graph to the KG file
    
    Args:
        graph: RDFLib Graph object to save
        kg_file_path: Path to the KG file (Path or str)
        create_timestamped: If True, create timestamped backup. If False, overwrite .backup file
    
    Returns:
        True if save was successful, False otherwise
    """
    kg_file = Path(kg_file_path)
    
    # Backup before saving
    try:
        from kg_backup import backup_kg_file
        backup_kg_file(kg_file, create_timestamped=create_timestamped)
    except ImportError:
        # Fallback: simple backup if module not available
        import shutil
        backup_file = f"{kg_file}.backup"
        if kg_file.exists():
            shutil.copy2(kg_file, backup_file)
            print(f"  ✅ Created backup: {backup_file}")
    except Exception as e:
        print(f"  ⚠️  Warning: Could not create backup: {e}")
    
    # Save the graph
    try:
        graph.serialize(destination=str(kg_file), format="turtle")
        print(f"  ✅ Saved graph to: {kg_file}")
        print(f"     Total triples: {len(graph)}")
        return True
    except Exception as e:
        print(f"  ❌ ERROR saving graph: {e}")
        return False

