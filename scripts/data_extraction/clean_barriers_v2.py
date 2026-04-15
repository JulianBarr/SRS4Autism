import json

def clean_barriers(input_file, output_file):
    print(f"Loading {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        nodes = json.load(f)
        
    print(f"🔍 Found {len(nodes)} raw nodes. Need to distill down to 24.")

    # 修复了 Substring 陷阱的精准字典
    STANDARD_BARRIERS = {
        "barrier-negative-behavior": ["negative"],
        "barrier-instructional-control": ["instructional", "control", "escape"],
        "barrier-defective-mand": ["mand"],
        # 移除了单纯的 tact，交给下方特殊逻辑处理，防止吞噬 contact
        "barrier-defective-motor-imitation": ["motor"],
        "barrier-defective-echoic": ["echoic"],
        "barrier-defective-vp-mts": ["vp-mts", "matching", "visual"],
        "barrier-defective-listener": ["listener"],
        "barrier-defective-intraverbal": ["intraverbal"],
        "barrier-defective-social": ["social"],
        "barrier-prompt-dependent": ["prompt"],
        "barrier-scrolling": ["scrolling"],
        "barrier-defective-scanning": ["scanning"],
        "barrier-failure-conditional-discriminations": ["conditional"],
        "barrier-failure-to-generalize": ["generalize"],
        "barrier-weak-motivators": ["motivat", "atypical"], # 移除了危险的 mo
        "barrier-response-requirement-weakens-mo": ["requirement"],
        "barrier-reinforcement-dependent": ["reinforcement"],
        "barrier-self-stimulation": ["stimulation", "stimming"],
        "barrier-articulation-problems": ["articulation"],
        "barrier-obsessive-compulsive": ["obsessive", "compulsive"],
        "barrier-hyperactivity": ["hyperactivity"],
        "barrier-failure-eye-contact": ["eye-contact", "attend"],
        "barrier-sensory-defensiveness": ["sensory"]
    }

    final_barriers = {}

    for node in nodes:
        raw_id = node.get("id", "").lower()
        score_text = node.get("scoring_criteria") or ""
        
        matched_standard_id = None
        
        # 特殊防碰撞逻辑：确保只有真正的 tact 被匹配，而不是 contact
        if "tact" in raw_id and "contact" not in raw_id:
            matched_standard_id = "barrier-defective-tact"
        else:
            for std_id, keywords in STANDARD_BARRIERS.items():
                if any(kw in raw_id for kw in keywords):
                    matched_standard_id = std_id
                    break
                    
        if matched_standard_id:
            existing_node = final_barriers.get(matched_standard_id)
            existing_score_len = len(existing_node.get("scoring_criteria") or "") if existing_node else 0
            
            if not existing_node or len(score_text) > existing_score_len:
                node["id"] = matched_standard_id
                final_barriers[matched_standard_id] = node

    cleaned_nodes = list(final_barriers.values())
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_nodes, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Success! Distilled down to exactly {len(cleaned_nodes)} barriers.")
    print(f"💾 Saved to {output_file}")

if __name__ == "__main__":
    INPUT = "vbmapp_barriers_master.json"
    OUTPUT = "vbmapp_barriers_cleaned.json"
    clean_barriers(INPUT, OUTPUT)
