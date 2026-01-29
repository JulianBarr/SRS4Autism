#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deploy CUMA-Word-Entity Anki note type to Anki via Anki-Connect.
Handles Creation (Cold Start) and Updates.
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path

# Unset proxy environment variables to prevent localhost connection issues
for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
    if key in os.environ:
        del os.environ[key]

# Configuration
ANKI_CONNECT_URL = "http://localhost:8765"
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR / "templates" / "cuma_word_entity"

# Model configuration
MODEL_NAME = "CUMA-Word-Entity-v2"
MODEL_CONFIG = {
    "css_file": "cuma_word_entity.css",
    "fields": [
        "Word",
        "WordAudio",   # 裸文件名
        "WordPicture", # HTML img 标签
        "Category",
        "UUID",
        "_Remarks",    # New: For sync timestamps or debug notes
        "_KG_Map"      # New: For storing the Knowledge Graph URI
    ],
    "card_templates": {
        "Stage 1 - Receptive Easy": {
            "front": "stage1_receptive_easy_front.html",
            "back": "stage1_receptive_easy_back.html"
        },
        "Stage 2 - Expressive Easy": {
            "front": "stage2_expressive_easy_front.html",
            "back": "stage2_expressive_easy_back.html"
        },
        "Stage 3 - Receptive Hard": {
            "front": "stage3_receptive_hard_front.html",
            "back": "stage3_receptive_hard_back.html"
        },
        "Stage 4 - Expressive Hard": {
            "front": "stage4_expressive_hard_front.html",
            "back": "stage4_expressive_hard_back.html"
        }
    }
}


def read_file(file_path: Path) -> str:
    """Read a file and return its contents."""
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
    """Invoke Anki-Connect API."""
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
    """Check if a model exists in Anki."""
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
        print(f"   ✅ Model created successfully")
        return True
    except Exception as e:
        print(f"   ❌ Creation Failed: {e}")
        return False


def deploy_model(model_name: str, model_info: dict) -> bool:
    """Deploy or update the model."""
    print(f"\n📦 Processing Model: {model_name}...")
    
    # 1. Prepare CSS
    css_path = TEMPLATE_DIR / model_info["css_file"]
    if not css_path.exists():
        print(f"   ❌ CSS missing: {css_path}")
        return False
    css_content = read_file(css_path)
    
    # 2. Prepare Templates (Dict format for Update)
    templates_payload = {}
    
    for card_name, files in model_info["card_templates"].items():
        front_path = TEMPLATE_DIR / files["front"]
        back_path = TEMPLATE_DIR / files["back"]
        
        if not front_path.exists() or not back_path.exists():
            print(f"   ❌ Template files missing for {card_name}")
            return False
        
        front = read_file(front_path)
        back = read_file(back_path)
        
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
            css_content
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
                "model": {"name": model_name, "css": css_content}
            })
            print(f"   ✅ Update Complete")
            return True
        except Exception as e:
            print(f"   ❌ Update Failed: {e}")
            return False


def main():
    """Main deployment function."""
    print("="*50)
    print("CUMA-Word-Entity Template Deployer")
    print("="*50)
    
    if not TEMPLATE_DIR.exists():
        print(f"❌ Error: {TEMPLATE_DIR} does not exist")
        return 1
    
    # Check for data file
    data_file = TEMPLATE_DIR / "_cuma_logic_city_data.js"
    if data_file.exists():
        print(f"📄 Found data file: {data_file.name}")
        print(f"   ⚠️  Remember to copy this file to Anki's collection.media folder!")
    else:
        print(f"⚠️  Warning: Data file not found: {data_file.name}")
    
    # Deploy model
    if deploy_model(MODEL_NAME, MODEL_CONFIG):
        print("\n" + "="*50)
        print("🎉 Deployment Successful!")
        print("="*50)
        print("\n📋 Next Steps:")
        print("1. Copy _cuma_logic_city_data.js to Anki's collection.media folder")
        print("2. Customize the data in _cuma_logic_city_data.js with your word categories")
        print("3. Create notes using the CUMA-Word-Entity note type")
        return 0
    else:
        print("\n" + "="*50)
        print("❌ Deployment Failed")
        print("="*50)
        return 1


if __name__ == "__main__":
    exit(main())

