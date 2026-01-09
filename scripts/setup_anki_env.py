#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup Anki Environment for Pinyin Typing Level 2

This script ensures Anki is ready to receive notes by:
1. Checking if deck exists, creating if not
2. Checking if note type exists, creating if not
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import requests
except ImportError:
    print("❌ requests not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DECK_NAME = "SRS4Autism::Pinyin::Level2_Typing"
MODEL_NAME = "CUMA-Pinyin-Typing-Lv2-v2"

# Model fields - UniqueId must be first to ensure uniqueness
MODEL_FIELDS = [
    "UniqueId",
    "Hanzi",
    "TargetSyllable",
    "TargetIndex",
    "FullPinyinRaw",
    "Audio",
    "Image",
    "LessonID"
]


def invoke_anki_connect(action: str, params: dict = None) -> any:
    """Invoke an Anki-Connect action."""
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    
    try:
        response = requests.post(ANKI_CONNECT_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("error"):
            raise Exception(f"Anki-Connect error: {result['error']}")
        
        return result.get("result")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to connect to Anki-Connect: {e}")


def check_anki_connect():
    """Check if Anki-Connect is running."""
    try:
        version = invoke_anki_connect("version")
        print(f"✅ Anki-Connect is running (version: {version})")
        return True
    except Exception as e:
        print(f"❌ Anki-Connect is not running: {e}")
        print("\nPlease ensure:")
        print("1. Anki is running")
        print("2. AnkiConnect add-on is installed (code: 2055492159)")
        print("3. No firewall is blocking localhost:8765")
        return False


def ensure_deck_exists():
    """Check if deck exists, create if not."""
    try:
        deck_names = invoke_anki_connect("deckNames")
        
        if DECK_NAME in deck_names:
            print(f"✅ Deck '{DECK_NAME}' already exists")
            return True
        else:
            print(f"📦 Creating deck '{DECK_NAME}'...")
            invoke_anki_connect("createDeck", {"deck": DECK_NAME})
            print(f"✅ Deck '{DECK_NAME}' created successfully")
            return True
    except Exception as e:
        print(f"❌ Error ensuring deck exists: {e}")
        return False


def ensure_model_exists():
    """Check if note type exists, create if not."""
    try:
        model_names = invoke_anki_connect("modelNames")
        
        if MODEL_NAME in model_names:
            print(f"✅ Note type '{MODEL_NAME}' already exists")
            return True
        else:
            print(f"📝 Creating note type '{MODEL_NAME}'...")
            
            # Define card templates using ONLY the fields we defined
            # Fields: UniqueId, Hanzi, TargetSyllable, TargetIndex, FullPinyinRaw, Audio, Image, LessonID
            # Note: Uses Anki's {{type:TargetSyllable}} for typing input
            front_template = """<div class="card">
    <div class="image">{{Image}}</div>
    
    <div id="pinyin-display" class="pinyin-context"></div>
    
    {{type:TargetSyllable}}
    
    <div class="instruction">Type the missing sound...</div>
    <div class="audio">{{Audio}}</div>

    <div id="raw-pinyin" style="display:none">{{FullPinyinRaw}}</div>
    <div id="target-index" style="display:none">{{TargetIndex}}</div>
</div>

<script>
    (function() {
        var raw = document.getElementById("raw-pinyin").innerText.trim();
        var idxStr = document.getElementById("target-index").innerText.trim();
        var display = document.getElementById("pinyin-display");
        
        if (raw && idxStr !== "") {
            // Split by space to handle pinyin words
            var parts = raw.split(" ");
            var idx = parseInt(idxStr, 10);
            
            if (idx >= 0 && idx < parts.length) {
                // Replace the target syllable with a blue ? placeholder
                parts[idx] = "<span class='cloze-gap'>?</span>";
                display.innerHTML = parts.join(" ");
            } else {
                display.innerText = raw;
            }
        }
    })();
</script>
"""
            
            back_template = """<div class="card">
    <div class="image">{{Image}}</div>
    
    <div class="pinyin-context">{{FullPinyinRaw}}</div>
    
    <hr id="answer">
    
    {{type:TargetSyllable}}
    
    <div class="hanzi">{{Hanzi}}</div>
    
    <div class="audio">{{Audio}}</div>
    <div class="debug">{{UniqueId}}</div>
</div>
"""
            
            templates = [{
                "Name": "Card 1",
                "Front": front_template,
                "Back": back_template
            }]
            
            css = """
/* CONTAINER */
.card {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 24px;
    text-align: center;
    color: #374151; /* Dark Gray text */
    background-color: #f9fafb; /* Light Gray bg */
    padding: 20px;
}

/* MEDIA */
.image img {
    max-width: 90%;
    max-height: 350px;
    border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    margin-bottom: 20px;
    background-color: white; /* Ensure transparent PNGs look good */
}

/* PINYIN CONTEXT */
.pinyin-context {
    font-size: 42px;
    font-weight: 700;
    color: #1f2937;
    margin: 15px 0;
    letter-spacing: 2px;
    line-height: 1.4;
}

/* CLOZE HIGHLIGHT (The blank spot) */
.cloze-gap {
    color: #3b82f6; /* Bright Blue */
    border-bottom: 4px solid #3b82f6;
    padding: 0 15px;
    display: inline-block;
    min-width: 50px;
}

/* --- ANKI TYPING INPUT FIX --- */
/* This is the input box on the Front */
input#typeans {
    font-family: "Courier New", monospace;
    font-size: 32px;
    text-align: center;
    color: #000000 !important;       /* FORCE BLACK TEXT */
    background-color: #ffffff !important; /* FORCE WHITE BG */
    border: 3px solid #3b82f6;
    border-radius: 8px;
    padding: 10px;
    margin-top: 15px;
    width: 200px;
    outline: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* --- FEEDBACK (Back Side) --- */
/* The comparison section */
code#typeans {
    font-family: "Courier New", monospace;
    font-size: 32px;
    padding: 5px 10px;
    border-radius: 6px;
    background-color: #ffffff;
}
.typeGood {
    background-color: #d1fae5 !important;
    color: #047857 !important;
    font-weight: bold;
}
.typeBad {
    background-color: #fee2e2 !important;
    color: #b91c1c !important;
    font-weight: bold;
}
.typeMissed {
    background-color: #f3f4f6 !important;
    color: #9ca3af !important;
    text-decoration: line-through;
}

/* HANZI & META */
.hanzi {
    font-size: 64px;
    margin-top: 30px;
    color: #111827;
    font-weight: bold;
}
.instruction {
    font-size: 16px;
    color: #6b7280;
    margin-top: 10px;
    font-style: italic;
}
.debug { display: none; }
"""
            
            invoke_anki_connect("createModel", {
                "modelName": MODEL_NAME,
                "inOrderFields": MODEL_FIELDS,
                "css": css,
                "cardTemplates": templates
            })
            
            print(f"✅ Note type '{MODEL_NAME}' created successfully")
            return True
    except Exception as e:
        print(f"❌ Error ensuring note type exists: {e}")
        return False


def main():
    """Main execution flow."""
    print("=" * 80)
    print("Setup Anki Environment for Pinyin Typing Level 2")
    print("=" * 80)
    print()
    
    # Check Anki-Connect connection
    if not check_anki_connect():
        return 1
    
    print()
    
    # Ensure deck exists
    if not ensure_deck_exists():
        return 1
    
    print()
    
    # Ensure model exists
    if not ensure_model_exists():
        return 1
    
    print()
    print("=" * 80)
    print("✅ Setup complete! Anki is ready to receive typing course notes.")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    exit(main())

