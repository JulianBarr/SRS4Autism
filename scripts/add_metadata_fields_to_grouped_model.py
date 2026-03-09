#!/usr/bin/env python3
"""
Add _Remarks and _KG_Map fields to the existing "CUMA - Grouped Interactive Cloze" note type.

Run this if you created the model before _Remarks and _KG_Map were added to setup_grouped_model.py.
AnkiConnect does not support adding fields to existing models, so this script provides
instructions for manual addition.

Usage:
    python scripts/add_metadata_fields_to_grouped_model.py

If the fields are already present, the script will report success.
Otherwise, it will print step-by-step instructions to add them manually in Anki.
"""
import json
import urllib.request

MODEL_NAME = "CUMA - Grouped Interactive Cloze"
REQUIRED_FIELDS = ["_Remarks", "_KG_Map"]


def invoke(action, **params):
    request_json = json.dumps({"action": action, "params": params, "version": 6}).encode("utf-8")
    try:
        response = json.load(
            urllib.request.urlopen(
                urllib.request.Request("http://localhost:8765", request_json)
            )
        )
    except Exception as e:
        raise SystemExit(
            f"Failed to connect to Anki. Is Anki open with AnkiConnect installed? Error: {e}"
        )
    if response.get("error") is not None:
        raise SystemExit(f"AnkiConnect error: {response['error']}")
    return response["result"]


def main():
    print(f"Checking note type '{MODEL_NAME}'...")
    model_names = invoke("modelNames")
    if MODEL_NAME not in model_names:
        print(f"❌ Note type '{MODEL_NAME}' not found.")
        print("   Run: python scripts/setup_grouped_model.py")
        raise SystemExit(1)

    field_names = invoke("modelFieldNames", modelName=MODEL_NAME)
    missing = [f for f in REQUIRED_FIELDS if f not in field_names]

    if not missing:
        print("✅ _Remarks and _KG_Map are already present. No action needed.")
        return

    print(f"⚠️  Missing fields: {', '.join(missing)}")
    print()
    print("AnkiConnect cannot add fields to existing note types.")
    print("Add them manually in Anki:")
    print()
    print("  1. Open Anki")
    print("  2. Tools → Manage Note Types")
    print(f"  3. Select '{MODEL_NAME}' → Fields")
    print("  4. Click 'Add' and add each missing field:")
    for f in missing:
        print(f"     - {f}")
    print("  5. Click OK to save")
    print()
    print("Then run this script again to verify.")


if __name__ == "__main__":
    main()
