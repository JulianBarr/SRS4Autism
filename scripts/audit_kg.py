import re
import json

def brute_force_decode(file_path):
    print(f"🕵️  Brute-force scanning {file_path} for structure...")
    
    samples = []
    class_counts = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Split by blocks ending in a dot
        blocks = re.split(r'\s+\.\n', content)

        for block in blocks:
            block = block.strip()
            if not block or block.startswith('@'): continue

            # Extract Subject (ID)
            subj_match = re.match(r'^(srs-inst:[^\s;]+)', block)
            # Extract Type (a srs-kg:...)
            type_match = re.search(r'\s+a\s+([^\s;]+)', block)
            # Extract all labels
            labels = re.findall(r'rdfs:label\s+"([^"]+)"', block)
            
            if type_match:
                cls = type_match.group(1)
                class_counts[cls] = class_counts.get(cls, 0) + 1
                
                # If we have labels, this is a content node
                if labels and len(samples) < 30:
                    samples.append({
                        "id": subj_match.group(1) if subj_match else "unknown",
                        "type": cls,
                        "labels": labels,
                        "raw_hint": block[:150].replace('\n', ' ') # Peek at the first 150 chars
                    })

    print("\n--- DETECTED CLASSES ---")
    for cls, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{cls}: {count}")

    print("\n--- DATA SAMPLES ---")
    print(json.dumps(samples, indent=2, ensure_ascii=False))

brute_force_decode("knowledge_graph/world_model_legacy_backup.ttl")
