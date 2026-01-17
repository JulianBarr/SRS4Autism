import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# We work on the BACKUP to start fresh and avoid double-cleaning
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_backup.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_legacy_clean.ttl"

def main():
    print(f"🚀 Starting Surgical Fix on {INPUT_FILE.name}...")
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        # 1. PROTECT PREFIXES: If line starts with @prefix, leave it exactly as is
        if line.strip().startswith("@prefix"):
            new_lines.append(line)
            continue
        
        # 2. FIX QUOTES INSIDE IDs: 
        # Look for srs-inst: IDs that contain spaces or quotes BEFORE the ' a ' marker
        if "srs-inst:" in line and " a " in line:
            # Match the part between srs-inst: and ' a '
            parts = re.split(r'(srs-inst:)', line, 1)
            prefix = parts[1]
            # Split the rest by the ' a ' relationship marker
            rest = re.split(r'(\s+a\s+)', parts[2], 1)
            id_body = rest[0]
            the_rest = rest[1] + rest[2]
            
            # Clean the ID body: Replace EVERYTHING that isn't a letter/number/dash with underscore
            # This turns: gp-B1-159-Expressing "always" with "conglai"
            # Into: gp-B1-159-Expressing_always_with_conglai
            clean_id = re.sub(r'[^a-zA-Z0-9\-]', '_', id_body)
            clean_id = re.sub(r'_+', '_', clean_id).strip('_')
            
            line = f"{parts[0]}{prefix}{clean_id}{the_rest}"

        # 3. CLEAN REMAINING URIs (Simple cases)
        # Handle the rest of the line but protect the strings
        line_parts = line.split('"')
        for i in range(len(line_parts)):
            if i % 2 == 0: # Outside quotes
                # Clean any srs-inst: URIs that still have spaces (e.g. in objects)
                def clean_obj(m):
                    return m.group(1) + re.sub(r'[^a-zA-Z0-9\-]', '_', m.group(2)).strip('_')
                
                line_parts[i] = re.sub(r'(srs-inst:)([^\s;.]+)', clean_obj, line_parts[i])
        
        new_lines.append('"'.join(line_parts))

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"✅ Surgical Fix Complete. Saved to: {OUTPUT_FILE.name}")

if __name__ == "__main__":
    main()
