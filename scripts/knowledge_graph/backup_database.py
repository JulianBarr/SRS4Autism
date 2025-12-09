#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple script to backup the database before running fixes
"""

import shutil
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"

def create_backup():
    """Create a backup of the SQLite database"""
    if not DB_PATH.exists():
        print("⚠️  Database file does not exist, nothing to backup")
        return None
    
    # Create backup directory if it doesn't exist
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped backup filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f"srs4autism_{timestamp}.db"
    
    # Copy database file
    shutil.copy2(DB_PATH, backup_path)
    
    # Get file size
    size_mb = backup_path.stat().st_size / (1024 * 1024)
    
    print(f"✅ Database backup created: {backup_path}")
    print(f"   Size: {size_mb:.2f} MB")
    return backup_path

if __name__ == "__main__":
    create_backup()

