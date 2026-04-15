import json

def normalize_vbmapp_json(input_file, output_file):
    print(f"Loading {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        nodes = json.load(f)

    # 涵盖了 Level 1 到 Level 3 所有可能出现的漂移名称的终极字典
    DOMAIN_MAP = {
        "Mand": "Mand",
        "Tact": "Tact",
        "Listener Responding": "Listener",
        "Listener": "Listener",
        "Visual Perceptual Skills and Matching-to-Sample (VP-MTS)": "VP-MTS",
        "Visual Perceptual Skills and Matching-to-Sample": "VP-MTS",
        "VP-MTS": "VP-MTS",
        "Independent Play": "Play",
        "Play": "Play",
        "Social Behavior and Social Play": "Social",
        "Social Play": "Social", 
        "Social": "Social",
        "MOTOR IMITATION — LEVEL 1": "Motor Imitation",
        "Motor Imitation": "Motor Imitation",
        "EARLY ECHOIC SKILLS ASSESSMENT (EESA)": "Echoic",
        "Echoic (EESA Subtest)": "Echoic", 
        "Echoic": "Echoic",
        "Listener Responding by Function, Feature, and Class (LRFFC)": "LRFFC",
        "LRFFC": "LRFFC",
        "Intraverbal": "Intraverbal",
        "Classroom Routines and Group Skills": "Group",
        "Group": "Group",
        "Linguistic Structure": "Linguistics",
        "Linguistics": "Linguistics",
        "Reading": "Reading",
        "Writing": "Writing",
        "Math": "Math"
    }

    normalized_domain_count = 0
    fixed_level_count = 0

    for node in nodes:
        # 1. 归一化 Domain 命名
        original_domain = node.get("domain")
        
        if original_domain in DOMAIN_MAP:
            standardized_domain = DOMAIN_MAP[original_domain]
            if original_domain != standardized_domain:
                node["domain"] = standardized_domain
                normalized_domain_count += 1
        else:
            print(f"Warning: Unknown domain found '{original_domain}' in node {node.get('id')}")
            
        # 2. 强制修复 Level (修复 "幽灵 Level 2")
        if node.get("level") != 3:
            node["level"] = 3
            fixed_level_count += 1

    # 保存干净的 JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(nodes, f, indent=4, ensure_ascii=False)
        
    print(f"Success! Normalized {normalized_domain_count} domain names.")
    print(f"Forced Level 3 on {fixed_level_count} nodes.")
    print(f"Sanitized ontology saved to {output_file}")

if __name__ == "__main__":
    INPUT = "vbmapp_level3_master.json"
    OUTPUT = "vbmapp_level3_normalized.json"
    
    normalize_vbmapp_json(INPUT, OUTPUT)
