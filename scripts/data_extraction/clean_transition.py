import json

def clean_transition(input_file, output_file):
    print(f"Loading {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        nodes = json.load(f)
        
    print(f"🔍 Found {len(nodes)} raw nodes. Need to distill down to 18.")

    # 定义 18 个标准转换指标的映射关键词
    STANDARD_TRANSITION = {
        "trans-01-milestones": ["1-milestone", "overall-milestone"],
        "trans-02-barriers": ["2-barrier", "overall-barrier"],
        "trans-03-behaviors": ["3-negative", "barriers-negative"],
        "trans-04-routines": ["4-routines", "routines-group"],
        "trans-05-social": ["5-social", "social-behavior-play"],
        "trans-06-independent-work": ["6-works-independently", "independent-academic"],
        "trans-07-generalization": ["7-generalization", "trans-generalization"],
        "trans-08-reinforcers": ["8-reinforcer", "variation-reinforcers"],
        "trans-09-acquisition": ["9-rate-of-acquisition", "trans-rate-acquisition"],
        "trans-10-retention": ["10-retention", "trans-retention"],
        "trans-11-natural-environment": ["11-natural", "natural-environment"],
        "trans-12-transfer": ["12-transfer", "transfer-new-verbal"],
        "trans-13-adaptability": ["13-adaptability", "trans-adaptability"],
        "trans-14-spontaneity": ["14-spontaneous", "trans-spontaneous"],
        "trans-15-play": ["15-self-directed-play", "independent-play-skills"],
        "trans-16-self-help": ["16-general-self-help", "trans-general-self-help"],
        "trans-17-toileting": ["17-toileting", "trans-toileting"],
        "trans-18-eating": ["18-eating", "trans-eating"]
    }

    final_items = {}

    for node in nodes:
        raw_id = node.get("id", "").lower()
        raw_title = node.get("title", "").lower()
        score_text = node.get("scoring_criteria") or ""
        
        matched_id = None
        # 匹配逻辑：优先查 ID，再查标题
        for std_id, keywords in STANDARD_TRANSITION.items():
            if any(kw in raw_id for kw in keywords) or any(kw in raw_title for kw in keywords):
                matched_id = std_id
                break
                
        if matched_id:
            existing_node = final_items.get(matched_id)
            # 保留计分标准更详细（更长）的节点
            if not existing_node or len(score_text) > len(existing_node.get("scoring_criteria") or ""):
                node["id"] = matched_id
                final_items[matched_id] = node

    cleaned_nodes = list(final_items.values())
    # 按 ID 排序，保证整洁
    cleaned_nodes.sort(key=lambda x: x["id"])
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_nodes, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Success! Distilled down to exactly {len(cleaned_nodes)} transition items.")
    print(f"💾 Saved to {output_file}")

if __name__ == "__main__":
    INPUT = "vbmapp_transition_master.json"
    OUTPUT = "vbmapp_transition_cleaned.json"
    clean_transition(INPUT, OUTPUT)
