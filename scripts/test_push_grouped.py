#!/usr/bin/env python3
"""
Test script for pushing grouped examples to Anki (CUMA - Grouped Interactive Cloze).

Run from project root (with venv activated):
    python scripts/test_push_grouped.py

Requires: Anki running with AnkiConnect add-on.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from anki_integration.anki_connect import AnkiConnect


def main():
    examples = [
        {
            "knowledge_point": "就算...也...",
            "front": "就算明天下雨，我[也]要去。",
            "back": "Even if it rains tomorrow, I'm still going.",
        },
        {
            "knowledge_point": "就算...也...",
            "front": "就算他很忙，[也]会来参加聚会。",
            "back": "Even if he's busy, he'll still come to the party.",
        },
        {
            "knowledge_point": "就算...也...",
            "front": "就算你不同意，我[也]要坚持。",
            "back": "Even if you disagree, I still insist.",
        },
        {
            "knowledge_point": "一边...一边...",
            "front": "他[一边]吃饭[一边]看电视。",
            "back": "He eats while watching TV.",
        },
        {
            "knowledge_point": "一边...一边...",
            "front": "她[一边]走路[一边]听音乐。",
            "back": "She walks while listening to music.",
        },
    ]

    print("Testing push_grouped_examples_to_anki...")
    print(f"Examples: {len(examples)}")
    print()

    anki = AnkiConnect()
    if not anki.ping():
        print("❌ Cannot connect to Anki. Is Anki open with AnkiConnect installed?")
        sys.exit(1)

    result = anki.push_grouped_examples_to_anki(
        examples=examples,
        deck_name="CUMA_Test_Lab",
        allow_duplicate=False,
    )

    print(f"✅ Success: {result['success_count']} notes created")
    print(f"❌ Failed: {result['failed_count']}")
    print(f"Note IDs: {result['note_ids']}")
    if result["errors"]:
        for err in result["errors"]:
            print(f"  - {err}")
    print()
    print("Check the CUMA_Test_Lab deck in Anki to verify the grouped cards.")


if __name__ == "__main__":
    main()
