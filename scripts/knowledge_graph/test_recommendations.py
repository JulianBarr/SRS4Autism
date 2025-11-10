#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the recommendations API"""
import sys
import json
import requests

# Get profile
response = requests.get('http://localhost:8000/profiles')
profiles = response.json()

if not profiles:
    print("No profiles found")
    sys.exit(1)

profile = profiles[0]
mastered_words = profile.get('mastered_words', '').split(', ')

print(f"Profile: {profile['name']}")
print(f"Total mastered words: {len(mastered_words)}")
print(f"\nTesting recommendations with ALL words...\n")

# Call recommendations API with ALL words
response = requests.post(
    'http://localhost:8000/kg/recommendations',
    json={'mastered_words': mastered_words, 'profile_id': profile['id']},
    timeout=60
)

print(f"Response status: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()
    print(f"Got {len(data['recommendations'])} recommendations\n")
    
    # Count by HSK level
    hsk_counts = {}
    for rec in data['recommendations']:
        hsk = rec['hsk']
        hsk_str = str(hsk) if hsk is not None else 'N/A'
        hsk_counts[hsk_str] = hsk_counts.get(hsk_str, 0) + 1
    
    print("Distribution by HSK level:")
    for hsk_str in sorted(hsk_counts.keys(), key=lambda x: int(x) if x != 'N/A' else 999):
        print(f"  HSK {hsk_str}: {hsk_counts[hsk_str]} words")
    print()
    
    print("Top 20 recommendations:")
    for i, rec in enumerate(data['recommendations'], 1):
        word = rec['word']
        pinyin = rec['pinyin']
        hsk = rec['hsk']
        score = rec['score']
        known = rec['known_chars']
        total = rec['total_chars']
        hsk_str = str(hsk) if hsk is not None else 'N/A'
        score_str = f"{score:.1f}" if isinstance(score, float) else str(score)
        print(f"  {i:2d}. {word:10s} ({pinyin:20s}) - HSK:{hsk_str:>4s}, Score:{score_str:>6s}, Chars:{known}/{total}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)

