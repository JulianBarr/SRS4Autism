#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Knowledge Graph Backup Utility

Provides automatic backup functionality for knowledge graph files before modifications.
All KG modification scripts should use this to ensure data safety.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime


def backup_kg_file(kg_file_path, backup_dir=None, create_timestamped=True):
    """
    Create a backup of a knowledge graph file before modification.
    
    Args:
        kg_file_path: Path to the KG file to backup (Path or str)
        backup_dir: Directory to store backups (default: same directory as KG file)
        create_timestamped: If True, create timestamped backup. If False, overwrite .backup file
    
    Returns:
        Path to the backup file created, or None if backup failed
    """
    kg_file = Path(kg_file_path)
    
    if not kg_file.exists():
        print(f"⚠️  Warning: KG file does not exist: {kg_file}")
        return None
    
    # Determine backup directory
    if backup_dir is None:
        backup_dir = kg_file.parent
    else:
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Create backup filename
    if create_timestamped:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{kg_file.stem}_{timestamp}{kg_file.suffix}"
    else:
        backup_file = backup_dir / f"{kg_file.name}.backup"
    
    try:
        # Copy file to backup location
        shutil.copy2(kg_file, backup_file)
        print(f"✅ Created backup: {backup_file}")
        print(f"   Original: {kg_file} ({kg_file.stat().st_size / 1024 / 1024:.2f} MB)")
        print(f"   Backup:   {backup_file} ({backup_file.stat().st_size / 1024 / 1024:.2f} MB)")
        return backup_file
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return None


def get_latest_backup(kg_file_path, backup_dir=None):
    """
    Get the most recent backup file for a given KG file.
    
    Args:
        kg_file_path: Path to the KG file
        backup_dir: Directory where backups are stored (default: same directory as KG file)
    
    Returns:
        Path to the latest backup file, or None if no backups found
    """
    kg_file = Path(kg_file_path)
    
    if backup_dir is None:
        backup_dir = kg_file.parent
    else:
        backup_dir = Path(backup_dir)
    
    # Look for timestamped backups
    pattern = f"{kg_file.stem}_*{kg_file.suffix}"
    timestamped_backups = sorted(backup_dir.glob(pattern), reverse=True)
    
    # Also check for .backup file
    simple_backup = backup_dir / f"{kg_file.name}.backup"
    
    backups = []
    if timestamped_backups:
        backups.extend(timestamped_backups)
    if simple_backup.exists():
        backups.append(simple_backup)
    
    if backups:
        # Return most recent (by modification time)
        return max(backups, key=lambda p: p.stat().st_mtime)
    
    return None


def restore_from_backup(kg_file_path, backup_file=None, backup_dir=None):
    """
    Restore a KG file from a backup.
    
    Args:
        kg_file_path: Path to the KG file to restore
        backup_file: Specific backup file to restore from (if None, uses latest)
        backup_dir: Directory where backups are stored
    
    Returns:
        True if restore was successful, False otherwise
    """
    kg_file = Path(kg_file_path)
    
    # Get backup file
    if backup_file is None:
        backup_file = get_latest_backup(kg_file_path, backup_dir)
        if backup_file is None:
            print(f"❌ No backup found for {kg_file}")
            return False
    else:
        backup_file = Path(backup_file)
        if not backup_file.exists():
            print(f"❌ Backup file does not exist: {backup_file}")
            return False
    
    try:
        # Create backup of current file before restoring
        if kg_file.exists():
            current_backup = backup_dir / f"{kg_file.name}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(kg_file, current_backup)
            print(f"✅ Backed up current file to: {current_backup}")
        
        # Restore from backup
        shutil.copy2(backup_file, kg_file)
        print(f"✅ Restored {kg_file} from backup: {backup_file}")
        return True
    except Exception as e:
        print(f"❌ Error restoring from backup: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python kg_backup.py backup <kg_file> [backup_dir]")
        print("  python kg_backup.py restore <kg_file> [backup_file]")
        print("  python kg_backup.py list <kg_file> [backup_dir]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "backup":
        if len(sys.argv) < 3:
            print("Error: KG file path required")
            sys.exit(1)
        kg_file = sys.argv[2]
        backup_dir = sys.argv[3] if len(sys.argv) > 3 else None
        backup_kg_file(kg_file, backup_dir)
    
    elif command == "restore":
        if len(sys.argv) < 3:
            print("Error: KG file path required")
            sys.exit(1)
        kg_file = sys.argv[2]
        backup_file = sys.argv[3] if len(sys.argv) > 3 else None
        restore_from_backup(kg_file, backup_file)
    
    elif command == "list":
        if len(sys.argv) < 3:
            print("Error: KG file path required")
            sys.exit(1)
        kg_file = sys.argv[2]
        backup_dir = sys.argv[3] if len(sys.argv) > 3 else None
        backup = get_latest_backup(kg_file, backup_dir)
        if backup:
            print(f"Latest backup: {backup}")
        else:
            print("No backups found")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

