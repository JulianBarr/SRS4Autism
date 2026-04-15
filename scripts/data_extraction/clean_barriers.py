import json

def clean_barriers(input_file, output_file):
    print(f"Loading {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        nodes = json.load(f)
        
    print(f"🔍 Found {len(nodes)} raw nodes. Need to distill down to 24.")

    # 定义 24 个标准障碍的核心关键词映射
    # Key: 标准的唯一 ID
    # Value: 一个数组，包含了大模型可能生成的所有异体字/同义词 ID 关键词
    STANDARD_BARRIERS = {
        "barrier-negative-behavior": ["negative"],
        "barrier-instructional-control": ["instructional", "control", "escape"],
        "barrier-defective-mand": ["mand"],
        "barrier-defective-tact": ["tact"],
        "barrier-defective-motor-imitation": ["motor-imitation"],
        "barrier-defective-echoic": ["echoic"],
        "barrier-defective-vp-mts": ["matching", "vp-mts", "visual-perceptual"],
        "barrier-defective-listener": ["listener"],
        "barrier-defective-intraverbal": ["intraverbal"],
        "barrier-defective-social": ["social"],
        "barrier-prompt-dependent": ["prompt"],
        "barrier-scrolling": ["scrolling"],
        "barrier-defective-scanning": ["scanning"],
        "barrier-failure-conditional-discriminations": ["conditional"],
        "barrier-failure-to-generalize": ["generalize"],
        "barrier-weak-motivators": ["motivat", "mo"], # 涵盖 motivation, motivators, mo
        "barrier-response-requirement-weakens-mo": ["requirement"],
        "barrier-reinforcement-dependent": ["reinforcement"],
        "barrier-self-stimulation": ["stimulation", "stimming"],
        "barrier-articulation-problems": ["articulation"],
        "barrier-obsessive-compulsive": ["obsessive", "compulsive"],
        "barrier-hyperactivity": ["hyperactivity"],
        "barrier-failure-eye-contact": ["eye-contact", "attend-to-people"],
        "barrier-sensory-defensiveness": ["sensory"]
    }

    final_barriers = {}

    for node in nodes:
        raw_id = node.get("id", "").lower()
        score_text = node.get("scoring_criteria") or ""
        
        # 寻找这个 raw_id 属于哪个标准障碍
        matched_standard_id = None
        for std_id, keywords in STANDARD_BARRIERS.items():
            if any(kw in raw_id for kw in keywords):
                matched_standard_id = std_id
                break
                
        if matched_standard_id:
            # 如果这个标准障碍还没被添加，或者新找到的节点包含更长的计分标准（过滤掉 N/A 的废节点）
            existing_node = final_barriers.get(matched_standard_id)
            existing_score_len = len(existing_node.get("scoring_criteria") or "") if existing_node else 0
            
            if not existing_node or len(score_text) > existing_score_len:
                # 统一使用标准 ID
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
