#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix the English Wikidata enrichment checkpoint by moving failed_permanent to failed_retriable.

This is useful when network errors were incorrectly categorized as permanent failures.
"""

import json
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
checkpoint_file = project_root / 'data' / 'content_db' / 'wikidata_enrichment_english_checkpoint.json'

if not checkpoint_file.exists():
    print(f"Checkpoint file not found: {checkpoint_file}")
    exit(1)

# Load checkpoint
with open(checkpoint_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

succeeded = set(data.get('succeeded', []))
failed_retriable = set(data.get('failed_retriable', []))
failed_permanent = set(data.get('failed_permanent', []))

print(f"Current checkpoint status:")
print(f"  Succeeded: {len(succeeded)}")
print(f"  Failed (retriable): {len(failed_retriable)}")
print(f"  Failed (permanent): {len(failed_permanent)}")
print()

# Move all failed_permanent to failed_retriable (they were likely timeouts)
if failed_permanent:
    print(f"Moving {len(failed_permanent)} items from failed_permanent to failed_retriable...")
    failed_retriable.update(failed_permanent)
    failed_permanent = set()
    
    # Save updated checkpoint
    data['succeeded'] = list(succeeded)
    data['failed_retriable'] = list(failed_retriable)
    data['failed_permanent'] = list(failed_permanent)
    
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Updated checkpoint:")
    print(f"  Succeeded: {len(succeeded)}")
    print(f"  Failed (retriable): {len(failed_retriable)}")
    print(f"  Failed (permanent): {len(failed_permanent)}")
    print()
    print("These items will now be retried on the next run.")
else:
    print("No items to move.")

