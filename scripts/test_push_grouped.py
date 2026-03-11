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
    # SRS test: each Note must contain ONLY examples for the SAME target_word.
    # "哪怕" and "究竟" must NOT be mixed in one Note.
    examples = [
        {"target_word": "哪怕", "front": "哪怕下雨，我[[c1::也]]去。", "back": "Even if it rains, I'll go."},
        {"target_word": "哪怕", "front": "哪怕他很忙，[[c1::也]]会来。", "back": "Even if busy, he'll come."},
        {"target_word": "究竟", "front": "你[[c1::究竟]]想说什么？", "back": "What exactly do you want to say?"},
        {"target_word": "究竟", "front": "这件事[[c1::究竟]]怎么回事？", "back": "What on earth is going on?"},
        # Fallback: knowledge_point when no target_word (e.g. grammar patterns)
        {"knowledge_point": "一边...一边...", "front": "他[[c1::一边]]吃饭[[c1::一边]]看电视。", "back": "He eats while watching TV."},
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
