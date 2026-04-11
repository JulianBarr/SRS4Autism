import json
import re
import os

def parse_legacy_desc(raw_desc):
    """防呆解析：从旧描述中剥离字母和年龄"""
    if not raw_desc:
        return "", "", ""
        
    raw_desc = str(raw_desc).strip()
    age_group = ""
    label = ""
    
    if "/" in raw_desc or "／" in raw_desc or "|" in raw_desc:
        parts = re.split(r'[/／\|]', raw_desc)
        age_group = parts[-1].strip()
        raw_desc = "/".join(parts[:-1]).strip()

    label_match = re.match(r'^([A-Z])[\.、\s]+(.*)$', raw_desc)
    if label_match:
        label = label_match.group(1)
        raw_desc = label_match.group(2).strip()
        
    return label, age_group, raw_desc

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(base_dir, "21_heep_hong_language_enriched_abox.json")
    output_file = os.path.join(base_dir, "language_workspace.md")

    print(f"📖 正在读取并展开 5 层级树: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(output_file, 'w', encoding='utf-8') as md:
        # Level 1: Module
        module_name = data.get("module") or "语言"
        md.write(f"# Module: {module_name}\n\n")

        for sub in data.get("submodules", []):
            # Level 2: Submodule
            sub_title = sub.get("title") or "未命名子模块"
            md.write(f"## Submodule: {sub_title}\n\n")

            for obj in sub.get("objectives", []):
                # Level 3: Objective
                obj_title = obj.get("title") or "未命名项目"
                md.write(f"### Objective: {obj_title}\n\n")

                for phasal in obj.get("phasal_objectives", []):
                    # Level 4: Phasal Objective
                    index = phasal.get("index") or ""
                    title = phasal.get("title") or ""
                    md.write(f"#### {index} {title}\n")
                    
                    shared_mats = phasal.get('shared_materials') or []
                    if shared_mats:
                        md.write(f"**Shared Materials:** {', '.join(shared_mats)}\n")
                        
                    shared_precautions = phasal.get('shared_precautions') or ""
                    if shared_precautions:
                        md.write(f"**Shared Precautions:** {shared_precautions}\n")
                        
                    shared_acts = phasal.get('shared_activity_suggestions') or []
                    if shared_acts:
                        md.write(f"**Shared Activities:**\n")
                        if isinstance(shared_acts, str):
                            shared_acts = [a.strip() for a in shared_acts.split('\n') if a.strip()]
                        for act in shared_acts:
                            md.write(f"- {act}\n")
                    md.write("\n")

                    # Level 5: Goals (Sub-goals)
                    goals = phasal.get("sub_goals") or phasal.get("goals") or []
                    for g in goals:
                        label = g.get("label") or ""
                        age = g.get("age_group") or ""
                        desc = g.get("description") or ""
                        
                        if not label and not age and desc:
                            label, age, desc = parse_legacy_desc(desc)
                            
                        md.write(f"##### [{label}] {desc} | {age}\n")
                        
                        materials = g.get("materials") or []
                        if materials:
                            md.write(f"**Materials:** {', '.join(materials)}\n")
                            
                        precautions = g.get("precautions") or ""
                        if precautions:
                            md.write(f"**Precautions:** {precautions}\n")
                            
                        activities = g.get("activity_suggestions") or []
                        if activities:
                            md.write(f"**Activities:**\n")
                            if isinstance(activities, str):
                                activities = [a.strip() for a in activities.split('\n') if a.strip()]
                            for act in activities:
                                md.write(f"- {act}\n")
                        md.write("\n")
                    
                    md.write("---\n\n")

    print(f"✅ 带层级骨架的 Markdown 已生成: {output_file}")

if __name__ == "__main__":
    main()
