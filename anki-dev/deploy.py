#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deploy Anki templates to Anki via Anki-Connect.
Handles Creation (Cold Start) and Updates.
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path

# Configuration
ANKI_CONNECT_URL = "http://localhost:8765"
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR / "templates" / "pinyin"

# Model configurations
# NOTE: "fields" are required for creating new models.
MODELS = {
    "CUMA - Pinyin Element": {
        "css_file": "pinyin_element.css",
        "fields": [
            "Element", "ExampleChar", "Picture", 
            "Tone1", "Tone2", "Tone3", "Tone4", 
            "_Remarks", "_KG_Map", "Tags"
        ],
        "card_templates": {
            "Element Card": {
                "front": "pinyin_element_card_front.html",
                "back": "pinyin_element_card_back.html"
            }
        }
    },
    "CUMA - Pinyin Syllable": {
        "css_file": "pinyin_syllable.css",
        "fields": [
            "Element", "ExampleChar", "Picture",
            "Tone1", "Tone2", "Tone3", "Tone4",
            "WordPinyin", "WordHanzi", "WordPicture", "WordAudio",
            "_Remarks", "_KG_Map", "Tags"
        ],
        "card_templates": {
            "MCQ Confusor": {
                "front": "pinyin_syllable_card_mcq_confusor_front.html",
                "back": "pinyin_syllable_card_mcq_confusor_back.html"
            },
            "MCQ Recent": {
                "front": "pinyin_syllable_card_mcq_recent_front.html",
                "back": "pinyin_syllable_card_mcq_recent_back.html"
            },
            "MCQ Tone": {
                "front": "pinyin_syllable_card_mcq_tone_front.html",
                "back": "pinyin_syllable_card_mcq_tone_back.html"
            },
            "Pinyin to Word": {
                "front": "pinyin_syllable_card_pinyin_to_word_front.html",
                "back": "pinyin_syllable_card_pinyin_to_word_back.html"
            },
            "Word to Pinyin": {
                "front": "pinyin_syllable_card_word_to_pinyin_front.html",
                "back": "pinyin_syllable_card_word_to_pinyin_back.html"
            }
        }
    }
}


def read_file(file_path: Path) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
        raise
    except Exception as e:
        print(f"❌ Error reading file {file_path}: {e}")
        raise


def invoke_anki_connect(action: str, params: dict = None) -> any:
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    
    try:
        request_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            ANKI_CONNECT_URL, 
            data=request_data, 
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get("error"):
                raise Exception(result['error'])
            return result.get("result")
    except Exception as e:
        raise Exception(f"Anki-Connect Error: {e}")


def check_model_exists(model_name: str) -> bool:
    try:
        model_names = invoke_anki_connect("modelNames")
        return model_name in model_names
    except:
        return False


def create_model(model_name: str, fields: list, templates: dict, css: str) -> bool:
    """Creates a brand new model if it doesn't exist."""
    print(f"   ✨ Creating new model: {model_name}...")
    
    # Format templates for creation (Note: createModel uses a List, update uses a Dict. API quirk.)
    template_list = []
    for name, tpl_data in templates.items():
        template_list.append({
            "Name": name,
            "Front": tpl_data["Front"],
            "Back": tpl_data["Back"]
        })

    try:
        invoke_anki_connect("createModel", {
            "modelName": model_name,
            "inOrderFields": fields,
            "css": css,
            "cardTemplates": template_list
        })
        return True
    except Exception as e:
        print(f"   ❌ Creation Failed: {e}")
        return False


def deploy_model(model_name: str, model_info: dict, shared_css: str) -> bool:
    print(f"\n📦 Processing Model: {model_name}...")
    
    # 1. Prepare CSS
    css_path = TEMPLATE_DIR / model_info["css_file"]
    if not css_path.exists():
        print(f"   ❌ CSS missing: {css_path}")
        return False
    combined_css = shared_css + "\n\n" + read_file(css_path)
    
    # 2. Prepare Templates (Dict format for Update)
    templates_payload = {}
    
    for card_name, files in model_info["card_templates"].items():
        front = read_file(TEMPLATE_DIR / files["front"])
        back = read_file(TEMPLATE_DIR / files["back"])
        
        # Dictionary format required for updateModelTemplates
        templates_payload[card_name] = {
            "Front": front,
            "Back": back
        }
    
    # 3. Check Existence & Create or Update
    if not check_model_exists(model_name):
        # CREATE
        return create_model(
            model_name, 
            model_info["fields"], 
            templates_payload, 
            combined_css
        )
    else:
        # UPDATE
        try:
            print(f"   🔄 Updating templates...")
            invoke_anki_connect("updateModelTemplates", {
                "model": {"name": model_name, "templates": templates_payload}
            })
            
            print(f"   🎨 Updating CSS...")
            invoke_anki_connect("updateModelStyling", {
                "model": {"name": model_name, "css": combined_css}
            })
            print(f"   ✅ Update Complete")
            return True
        except Exception as e:
            print(f"   ❌ Update Failed: {e}")
            return False


def main():
    print("="*40 + "\nAnki Template Deployer v2.0\n" + "="*40)
    
    if not TEMPLATE_DIR.exists():
        print(f"❌ Error: {TEMPLATE_DIR} does not exist")
        return 1

    # Read Shared CSS
    shared_css = ""
    shared_path = TEMPLATE_DIR / "styles.css"
    if shared_path.exists():
        print(f"📄 Loaded shared styles.css")
        shared_css = read_file(shared_path)

    success_count = 0
    for name, info in MODELS.items():
        if deploy_model(name, info, shared_css):
            success_count += 1
            
    print("\n" + "="*40)
    print(f"Summary: {success_count}/{len(MODELS)} models deployed.")
    
    if success_count == len(MODELS):
        print("🎉 Success!")
        return 0
    return 1

if __name__ == "__main__":
    exit(main())
