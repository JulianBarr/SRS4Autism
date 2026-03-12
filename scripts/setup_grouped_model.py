import json
import urllib.request
from pathlib import Path

def invoke(action, **params):
    requestJson = json.dumps({'action': action, 'params': params, 'version': 6}).encode('utf-8')
    try:
        response = json.load(urllib.request.urlopen(urllib.request.Request('http://localhost:8765', requestJson)))
    except Exception as e:
        raise Exception(f"Failed to connect to Anki. Is Anki open and AnkiConnect installed? Error: {e}")
    
    if response.get('error') is not None:
        raise Exception(response['error'])
    return response['result']

def create_grouped_model():
    print("Reading template files...")
    base_dir = Path("docs/anki_templates")
    
    try:
        front_raw = (base_dir / "Interactive_Cloze_Front.html").read_text(encoding="utf-8")
        back_raw = (base_dir / "Interactive_Cloze_Back.html").read_text(encoding="utf-8")
        css = (base_dir / "Interactive_Cloze_Styling.css").read_text(encoding="utf-8")
    except FileNotFoundError as e:
        print(f"Error: Could not find template file. Make sure you run this from the project root.\n{e}")
        return

    fields = []
    card_templates = []

    print("Building 5-slot schema...")
    for i in range(1, 6):
        # 1. Define the paired fields for this slot
        fields.extend([f"Text{i}", f"Extra{i}"])
        # 2. Build Front Template
        # Swap out the generic {{Text}} for the specific {{TextN}}
        front_replaced = front_raw.replace("{{Text}}", f"{{{{Text{i}}}}}")
        # WRAP IN CONDITIONAL: This ensures Anki won't generate Card 4 if Text4 is empty!
        front_card = f"{{{{#Text{i}}}}}\n{front_replaced}\n{{{{/Text{i}}}}}"
        
        # 3. Build Back Template
        # Swap out the generic {{Extra}} and its conditionals for {{ExtraN}}
        back_replaced = back_raw.replace("{{Extra}}", f"{{{{Extra{i}}}}}")
        back_replaced = back_replaced.replace("{{#Extra}}", f"{{{{#Extra{i}}}}}")
        back_replaced = back_replaced.replace("{{/Extra}}", f"{{{{/Extra{i}}}}}")
        
        # 4. Append the card type
        card_templates.append({
            "Name": f"Example Card {i}",
            "Front": front_card,
            "Back": back_replaced
        })
    # Add metadata fields for production CUMA compatibility
    fields.extend(["_Remarks", "_KG_Map"])

    model_name = "CUMA - Grouped Interactive Cloze"
    model_names = invoke("modelNames")
    if model_name in model_names:
        # Model exists: add missing fields, then sync templates and CSS
        existing_fields = invoke("modelFieldNames", modelName=model_name)
        for field_name in ["_Remarks", "_KG_Map"]:
            if field_name not in existing_fields:
                try:
                    invoke("modelFieldAdd", modelName=model_name, fieldName=field_name)
                    print(f"✅ Added field '{field_name}' to existing note type.")
                except Exception as e:
                    print(f"⚠️ Could not add '{field_name}': {e}")

        # Build templates payload for updateModelTemplates
        # Format: { "Example Card 1": {"Front": "...", "Back": "..."}, ... }
        templates_payload = {
            card["Name"]: {"Front": card["Front"], "Back": card["Back"]}
            for card in card_templates
        }

        try:
            invoke("updateModelTemplates", model={"name": model_name, "templates": templates_payload})
            invoke("updateModelStyling", model={"name": model_name, "css": css})
            print("✅ Templates and CSS updated successfully.")
        except Exception as e:
            print(f"❌ Failed to update templates/CSS: {e}")
        return

    print("Pushing 'CUMA - Grouped Interactive Cloze' to Anki...")
    try:
        result = invoke("createModel",
               modelName=model_name,
               inOrderFields=fields,
               css=css,
               isCloze=False, # We keep this False because your JS handles the cloze logic, not Anki's native engine
               cardTemplates=card_templates)
        
        print("✅ Success! Note Type created in Anki.")
    except Exception as e:
        print(f"❌ Failed to create model: {e}")

if __name__ == "__main__":
    create_grouped_model()
