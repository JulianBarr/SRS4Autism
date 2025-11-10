#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Continuous translation runner with proper path handling"""
import subprocess
import time
import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
EXTRACT_SCRIPT = SCRIPT_DIR / "extract_mastered_words.py"

print("=" * 80)
print("Starting continuous translation process...")
print("=" * 80)
print(f"Script: {EXTRACT_SCRIPT}")
print(f"Working dir: {PROJECT_ROOT}")
print()

last_count = 0
max_runs = 200
count = 0  # Initialize count

for run in range(max_runs):
    print(f"\n--- Run {run+1}/{max_runs} ---")
    
    # Run extraction using python3 and proper paths
    result = subprocess.run(
        ['python3', str(EXTRACT_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT)
    )
    
    # Check cache size before and after
    cache_file = PROJECT_ROOT / "data/content_db/translation_cache.json"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cache_before = len(json.load(f))
    else:
        cache_before = 0
    
    # Check for progress
    lines = result.stdout.split('\n')
    wrote_line = [l for l in lines if 'wrote' in l and 'unique' in l]
    
    if wrote_line:
        # Extract count
        import re
        match = re.search(r'(\d+) unique', wrote_line[0])
        if match:
            count = int(match.group(1))
            
            # Check cache size after
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cache_after = len(json.load(f))
                if cache_after > cache_before:
                    print(f"  📝 Cache updated: {cache_before} → {cache_after} (+{cache_after - cache_before})")
            
            # Update profile if changed
            if count != last_count:
                # Update profile
                update_result = subprocess.run(['python3', '-c', '''
import json
with open("data/content_db/mastered_words_list.txt", "r") as f:
    words = [line.strip() for line in f if line.strip()]
mastered_str = ", ".join(words)
with open("backend/data/profiles/child_profiles.json", "r") as f:
    profiles = json.load(f)
profiles[0]["mastered_words"] = mastered_str
with open("backend/data/profiles/child_profiles.json", "w") as f:
    json.dump(profiles, f, ensure_ascii=False, indent=2)
print(f"✅ Updated profile: {len(words)} words")
                '''], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
                print(update_result.stdout)
                last_count = count
                print(f"✅ Run {run+1}: Now have {count} words")
            
            # Check if done
            if count >= 2500:
                print("\n" + "=" * 80)
                print("✅ Translation complete!")
                print("=" * 80)
                break
    
    # Quota check
    if 'Quota exceeded' in result.stdout:
        print(f"  ⏸️  Quota hit, waiting 90s for reset...")
        time.sleep(90)  # Wait longer to ensure quota reset
    else:
        # Check if any new translations happened
        translated_match = [l for l in lines if 'translated' in l.lower() and 'words' in l.lower()]
        if translated_match:
            print(f"  ✅ {translated_match[-1]}")
        time.sleep(10)  # Delay between runs
    
    if run % 10 == 0 and run > 0:
        print(f"\n--- Progress check: {count} words after {run} runs ---\n")

print(f"\nFinal count: {last_count} words")

