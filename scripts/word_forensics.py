import re
import json

def word_forensics(file_path):
    print(f"🕵️  Focusing on Word/Concept nodes in {file_path}...")
    
    word_samples = []
    concept_samples = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        # We'll read line by line to be memory efficient for 41MB
        current_block = []
        for line in f:
            current_block.append(line)
            if line.strip().endswith('.') or line.strip().endswith(';'):
                block_str = "".join(current_block)
                
                # Check if this block is a Word or Concept
                if "a srs-kg:Word" in block_str or "a srs-kg:Concept" in block_str:
                    # Extract ID
                    id_match = re.search(r'srs-inst:([^\s;]+)', block_str)
                    # Extract Chinese label
                    zh_match = re.search(r'\"([^\"]+)\"@zh', block_str)
                    # Extract English label/translation
                    en_match = re.search(r'\"([^\"]+)\"@en', block_str)
                    # Extract HSK
                    hsk_match = re.search(r'srs-kg:hskLevel\s+"?(\d)"?', block_str)

                    data = {
                        "id": id_match.group(1) if id_match else "unknown",
                        "zh": zh_match.group(1) if zh_match else None,
                        "en": en_match.group(1) if en_match else None,
                        "hsk": hsk_match.group(1) if hsk_match else None,
                        "raw_preview": block_str[:200].replace('\n', ' ')
                    }

                    if "a srs-kg:Word" in block_str and len(word_samples) < 10:
                        word_samples.append(data)
                    elif "a srs-kg:Concept" in block_str and len(concept_samples) < 10:
                        concept_samples.append(data)
                
                if len(word_samples) >= 10 and len(concept_samples) >= 10:
                    break
                
                if line.strip().endswith('.'):
                    current_block = []

    print("\n--- WORD SAMPLES ---")
    print(json.dumps(word_samples, indent=2, ensure_ascii=False))
    print("\n--- CONCEPT SAMPLES ---")
    print(json.dumps(concept_samples, indent=2, ensure_ascii=False))

word_forensics("knowledge_graph/world_model_legacy_backup.ttl")
