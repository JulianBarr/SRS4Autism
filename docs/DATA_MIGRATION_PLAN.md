# Data Migration Plan

## Overview

This document outlines the strategy for safely migrating and modifying data in the SRS4Autism system to prevent data loss.

## Core Principles

### 1. **Always Backup Before Modifying**
```bash
# Backup strategy
cp data/profiles/child_profiles.json data/profiles/child_profiles.json.backup.$(date +%Y%m%d_%H%M%S)
```

### 2. **Use Git to Track Changes**
```bash
# Check current state
git status
git diff data/profiles/child_profiles.json

# Commit before major changes
git add data/profiles/child_profiles.json
git commit -m "Snapshot before [description of change]"
```

### 3. **Inspect Data Before Modifying**
Always check the actual content of fields before modifying them:

```python
import json

# GOOD: Check before modifying
with open('data/profiles/child_profiles.json', 'r') as f:
    profiles = json.load(f)
    
for profile in profiles:
    mastered_grammar = profile.get('mastered_grammar')
    
    # Inspect actual value
    if mastered_grammar is None:
        print(f"Profile {profile['name']}: mastered_grammar is null")
    elif mastered_grammar == '':
        print(f"Profile {profile['name']}: mastered_grammar is empty string")
    else:
        print(f"Profile {profile['name']}: mastered_grammar has data: {len(mastered_grammar)} chars")
```

### 4. **Use Non-Destructive Migrations**
- Prefer **adding** new fields over modifying existing ones
- Use **database migrations** with rollback capabilities
- Create **migration scripts** that can be run multiple times safely (idempotent)

## Data Files Requiring Protection

### Critical Data Files
1. **`data/profiles/child_profiles.json`**
   - Contains user profiles, mastered words, mastered grammar
   - **Backup frequency:** Before any modification
   - **Recovery:** Git restore or timestamped backup

2. **`data/content_db/approved_cards.json`**
   - Contains curated educational content
   - **Backup frequency:** Weekly + before modifications

3. **`data/content_db/chat_history.json`**
   - Contains conversation history
   - **Backup frequency:** Daily

4. **`knowledge_graph/world_model_merged.ttl`**
   - Contains the knowledge graph
   - **Backup frequency:** Before KG updates

## Migration Script Template

```python
#!/usr/bin/env python3
"""
Migration: [Brief description]
Date: [YYYY-MM-DD]
Author: [Name]
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

def backup_file(file_path):
    """Create timestamped backup"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{file_path}.backup.{timestamp}"
    shutil.copy(file_path, backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def migrate(data):
    """
    Perform the migration.
    Returns: (modified_data, changes_made)
    """
    changes = 0
    
    for profile in data:
        # Example: Add new field only if it doesn't exist
        if 'new_field' not in profile:
            profile['new_field'] = default_value
            changes += 1
    
    return data, changes

def main():
    file_path = Path('data/profiles/child_profiles.json')
    
    # Step 1: Backup
    backup_path = backup_file(file_path)
    
    # Step 2: Load data
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Step 3: Inspect current state
    print(f"📊 Current state:")
    for i, profile in enumerate(data):
        print(f"  Profile {i}: {profile.get('name')}")
        # Inspect relevant fields
    
    # Step 4: Confirm migration
    response = input("\\nProceed with migration? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled.")
        return
    
    # Step 5: Migrate
    migrated_data, changes = migrate(data)
    print(f"✅ Migration complete: {changes} changes made")
    
    # Step 6: Save
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(migrated_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Data saved to {file_path}")
    print(f"⚠️  Backup available at {backup_path}")

if __name__ == '__main__':
    main()
```

## Recovery Procedures

### Recovering from Git

```bash
# View file history
git log --oneline data/profiles/child_profiles.json

# View specific commit
git show <commit_hash>:data/profiles/child_profiles.json

# Restore from specific commit
git checkout <commit_hash> -- data/profiles/child_profiles.json

# Restore from HEAD (last commit)
git checkout HEAD -- data/profiles/child_profiles.json
```

### Recovering from Backup

```bash
# List available backups
ls -lt data/profiles/*.backup.*

# Restore from backup
cp data/profiles/child_profiles.json.backup.20250101_120000 data/profiles/child_profiles.json
```

## Best Practices for AI Assistants

### Pre-Modification Checklist
- [ ] Inspect current data state
- [ ] Create backup
- [ ] Check git status
- [ ] Verify field contains expected data type
- [ ] Test migration on a copy first
- [ ] Get user confirmation for destructive changes

### Forbidden Operations (Without Explicit User Permission)
- ❌ Overwriting existing non-empty data fields
- ❌ Deleting user data
- ❌ Modifying data without backup
- ❌ Running migrations without dry-run first
- ❌ Committing changes automatically

### Recommended Operations
- ✅ Adding new fields with default values
- ✅ Enriching existing data (adding to lists, not replacing)
- ✅ Transforming data with explicit user approval
- ✅ Creating backups before any modification
- ✅ Using non-destructive updates (append, not replace)

## Database Schema Evolution

### Adding New Fields
```python
# GOOD: Add new field with default
if 'new_field' not in profile:
    profile['new_field'] = default_value
```

### Modifying Existing Fields
```python
# BAD: Directly overwrite
profile['mastered_grammar'] = ''

# GOOD: Check before modifying
if profile.get('mastered_grammar') is None:
    # Only modify if truly null
    profile['mastered_grammar'] = ''
elif profile.get('mastered_grammar') == '':
    # Field is already empty string, skip
    pass
else:
    # Field has data, preserve it!
    print(f"Warning: mastered_grammar already has data, skipping")
```

## Automated Backup System

### Recommended Backup Script

```bash
#!/bin/bash
# backup_data.sh - Run daily via cron

BACKUP_DIR="data/backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup critical data files
cp data/profiles/child_profiles.json "$BACKUP_DIR/"
cp data/content_db/approved_cards.json "$BACKUP_DIR/"
cp data/content_db/chat_history.json "$BACKUP_DIR/"

# Create compressed archive
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"

# Keep only last 30 days of backups
find data/backups -name "*.tar.gz" -mtime +30 -delete

echo "Backup created: $BACKUP_DIR.tar.gz"
```

### Cron Job Setup
```bash
# Add to crontab (run daily at 2 AM)
0 2 * * * /path/to/SRS4Autism/backup_data.sh
```

## Incident Response

If data loss occurs:
1. **Stop immediately** - Don't make more changes
2. **Check git history** - `git log --all -- <file>`
3. **Check backups** - Look in `data/backups/` or `*.backup.*` files
4. **Restore from most recent safe state**
5. **Document what went wrong** - Update this guide
6. **Implement prevention** - Add checks to prevent recurrence

## Future Improvements

1. **Implement proper database** (SQLite/PostgreSQL) with:
   - Transaction support
   - Automatic backups
   - Schema migrations (e.g., Alembic)
   - Rollback capabilities

2. **Add data validation layer**:
   - Pydantic models for all data structures
   - Validation before save
   - Type checking

3. **Implement audit log**:
   - Track all data modifications
   - Record who/what/when/why
   - Enable data forensics

4. **Add unit tests for migrations**:
   - Test on sample data
   - Verify no data loss
   - Check idempotency

## Summary

**Golden Rule: Never modify user data without explicit permission and backup.**

When in doubt:
1. Make a backup
2. Ask the user
3. Test on a copy first
4. Provide rollback instructions


