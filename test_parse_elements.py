#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to verify element parsing"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scripts.knowledge_graph.add_missing_pinyin_elements import parse_elements_file

elements_file = Path('data/content_db/missing_pinyin_elements.dat')
print(f"Testing element parsing...")
print(f"File: {elements_file}")
print(f"Exists: {elements_file.exists()}")

if elements_file.exists():
    elements = parse_elements_file(elements_file)
    print(f"\nParsed {len(elements)} elements:")
    for elem, data in elements.items():
        if isinstance(data, dict):
            print(f"  {elem}: proper_name={data.get('proper_name')}, example_char={data.get('example_char')}, picture={data.get('picture_file')}")
        else:
            print(f"  {elem}: {data}")
else:
    print("File not found!")


