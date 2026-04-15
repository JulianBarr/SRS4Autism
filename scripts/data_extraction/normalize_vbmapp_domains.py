import json

def normalize_vbmapp_json(input_file, output_file):
    print(f"Loading {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        nodes = json.load(f)

    # The strict mapping dictionary to fix all LLM "concept drift"
    # Maps whatever the LLM spit out to our standard Graph Domain Names
    DOMAIN_MAP = {
        "Mand": "Mand",
        "Tact": "Tact",
        "Listener Responding": "Listener",
        "Listener": "Listener",
        "Visual Perceptual Skills and Matching-to-Sample (VP-MTS)": "VP-MTS",
        "VP-MTS": "VP-MTS",
        "Independent Play": "Play",
        "Play": "Play",
        "Social Behavior and Social Play": "Social",
        "Social": "Social",
        "MOTOR IMITATION — LEVEL 1": "Motor Imitation",
        "Motor Imitation": "Motor Imitation",
        "EARLY ECHOIC SKILLS ASSESSMENT (EESA)": "Echoic",
        "Echoic": "Echoic",
        "Spontaneous Vocal Behavior": "Vocal",
        "Vocal": "Vocal"
    }

    normalized_count = 0

    for node in nodes:
        original_domain = node.get("domain")
        
        if original_domain in DOMAIN_MAP:
            standardized_domain = DOMAIN_MAP[original_domain]
            if original_domain != standardized_domain:
                node["domain"] = standardized_domain
                normalized_count += 1
        else:
            print(f"Warning: Unknown domain found '{original_domain}' in node {node.get('id')}")

    # Save the sanitized JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(nodes, f, indent=4, ensure_ascii=False)
        
    print(f"Success! Normalized {normalized_count} domain text attributes.")
    print(f"Sanitized ontology saved to {output_file}")

if __name__ == "__main__":
    INPUT = "vbmapp_level1_master.json"
    OUTPUT = "vbmapp_level1_normalized.json"
    
    normalize_vbmapp_json(INPUT, OUTPUT)
