import json
import re
import os

def split_materials(mat_str):
    """
    智能切分材料字符串，按逗号/顿号切分，但完美保护括号内的内容不被切碎。
    """
    mats = []
    current_mat = ""
    depth = 0
    for char in mat_str:
        if char in "([（【": depth += 1
        elif char in ")]）】":
            depth -= 1
            if depth < 0: depth = 0
        if depth == 0 and char in ",，、":
            if current_mat.strip(): mats.append(current_mat.strip())
            current_mat = ""
        else:
            current_mat += char
    if current_mat.strip():
        mats.append(current_mat.strip())
    return mats

def parse_md_to_json(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    data = {
        "module": "",
        "submodules": []
    }

    current_submodule = None
    current_objective = None
    current_phasal = None
    current_goal = None

    current_state = None
    shared_precautions_text = ""
    current_activities = []

    h1_pat = re.compile(r'^#\s+Module:\s*(.*)')
    h2_pat = re.compile(r'^##\s+Submodule:\s*(.*)')
    h3_pat = re.compile(r'^###\s+Objective:\s*(.*)')
    h4_pat = re.compile(r'^####\s+(.*)')

    for line in lines:
        raw_line = line.rstrip('\n')
        stripped = raw_line.strip()
        
        # 跳过空行及保留的页码标签
        if not stripped or stripped == "</>" or re.match(r'^<\d+,\d+>$', stripped):
            continue

        if h1_pat.match(stripped):
            data["module"] = h1_pat.match(stripped).group(1).strip()
            current_state = None
            continue

        if h2_pat.match(stripped):
            current_submodule = {"title": h2_pat.match(stripped).group(1).strip(), "objectives": []}
            data["submodules"].append(current_submodule)
            current_objective = None
            current_phasal = None
            current_goal = None
            current_state = None
            continue

        if h3_pat.match(stripped):
            obj_title = h3_pat.match(stripped).group(1).strip()
            
            current_objective = {"title": obj_title, "phasal_objectives": []}
            if current_submodule is not None:
                current_submodule["objectives"].append(current_objective)
            
            # 【核心架构适配】：自理教材跳过了一级，用 ### 直接兼任了 Objective 和 Phasal Objective
            # 因此我们自动建一个容器来装载接下来的 Goals，保持 JSON Schema 全局统一。
            current_phasal = {
                "index": "",
                "title": obj_title,
                "goals": []
            }
            current_objective["phasal_objectives"].append(current_phasal)
            
            current_goal = None
            current_activities = []
            shared_precautions_text = ""
            current_state = None
            continue

        if h4_pat.match(stripped):
            # 【核心层级适配】：在自理教材中，#### 才是 Goal 卡片！
            if current_goal is not None and current_activities:
                current_goal["activity_suggestions"] = "\n".join(current_activities)

            raw_desc = h4_pat.match(stripped).group(1).strip()
            
            # 格式化前缀 (e.g., "A 吸啜奶瓶" -> "A. 吸啜奶瓶")
            letter_match = re.match(r'^([A-Z])\s+(.*)', raw_desc)
            if letter_match:
                raw_desc = f"{letter_match.group(1)}. {letter_match.group(2)}"
            
            # 标准化年龄分割
            if '|' in raw_desc:
                parts = raw_desc.rsplit('|', 1)
                goal_desc = f"{parts[0].strip()} / {parts[1].strip()}"
            else:
                match = re.search(r'\s*/\s*([\d>\-]+\s*(?:岁|个月|年).*)$', raw_desc)
                if match:
                    goal_desc = f"{raw_desc[:match.start()].strip()} / {match.group(1).strip()}"
                else:
                    goal_desc = raw_desc
            
            precautions_val = shared_precautions_text.strip() if shared_precautions_text.strip() else None
            current_goal = {
                "description": goal_desc,
                "materials": [],
                "passing_criteria": None,
                "precautions": precautions_val,
                "activity_suggestions": None
            }
            
            if current_phasal is not None:
                current_phasal["goals"].append(current_goal)
            
            current_activities = []
            current_state = None
            continue

        # ============================================================
        # Flat Blocks 状态机 (剔除了不需要的缩进反弹逻辑)
        # ============================================================
        clean_stripped = re.sub(r'\*\*', '', stripped)
        
        is_sprec = re.match(r'^(?:[\*\-]\s*)?(Shared Precautions|共同注意事项)\s*[:：]?\s*(.*)', clean_stripped, re.IGNORECASE)
        is_prec = re.match(r'^(?:[\*\-]\s*)?(Precautions|注意事项)\s*[:：]?\s*(.*)', clean_stripped, re.IGNORECASE)
        is_mat = re.match(r'^(?:[\*\-]\s*)?(Materials|材料|教具)\s*[:：]?\s*(.*)', clean_stripped, re.IGNORECASE)
        is_act = re.match(r'^(?:[\*\-]\s*)?(Activities|Activity|活动建议|活动|玩法|步骤)\s*\d*\s*[:：]?\s*(.*)', clean_stripped, re.IGNORECASE)
        
        is_bullet = bool(re.match(r'^[\*\-]\s+', stripped))

        if is_sprec:
            current_state = "shared_precautions"
            val = is_sprec.group(2).strip()
            if val: shared_precautions_text += ("\n" + val if shared_precautions_text else val)
            continue
        if is_prec:
            current_state = "precautions"
            val = is_prec.group(2).strip()
            if val and current_goal: current_goal["precautions"] = (current_goal["precautions"] + "\n" + val) if current_goal["precautions"] else val
            continue
        if is_mat:
            current_state = "materials"
            val = is_mat.group(2).strip()
            if val and current_goal:
                for m in split_materials(val):
                    if m not in current_goal["materials"]: current_goal["materials"].append(m)
            continue
        if is_act:
            current_state = "activities"
            val = is_act.group(2).strip()
            if val and current_goal: current_activities.append(val)
            continue

        if is_bullet:
            val = re.sub(r'^[\*\-]\s+', '', clean_stripped)
            if not val: continue
            if current_state == "activities" and current_goal:
                current_activities.append(val)
            elif current_state == "materials" and current_goal:
                for m in split_materials(val):
                    if m not in current_goal["materials"]: current_goal["materials"].append(m)
            elif current_state == "precautions" and current_goal:
                current_goal["precautions"] = (current_goal["precautions"] + "\n" + val) if current_goal["precautions"] else val
            elif current_state == "shared_precautions":
                shared_precautions_text += ("\n" + val if shared_precautions_text else val)
        else:
            if not current_state: continue
            val = clean_stripped
            if current_state == "activities" and current_goal:
                if current_activities: current_activities[-1] += "\n" + val
                else: current_activities.append(val)
            elif current_state == "materials" and current_goal:
                for m in split_materials(val):
                    if m not in current_goal["materials"]: current_goal["materials"].append(m)
            elif current_state == "precautions" and current_goal:
                current_goal["precautions"] = (current_goal["precautions"] + "\n" + val) if current_goal["precautions"] else val
            elif current_state == "shared_precautions":
                shared_precautions_text += ("\n" + val if shared_precautions_text else val)

    # 捕获文件最后一段活动的结尾
    if current_goal is not None and current_activities:
        current_goal["activity_suggestions"] = "\n".join(current_activities)

    # 导出 JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Successfully converted {input_file} to {output_file} (Self Care Edition!)")

if __name__ == "__main__":
    input_filename = "23-self-care-toc_workspace_fixed_reworked.md"
    output_filename = "23_self_care_enriched_abox.json"
    parse_md_to_json(input_filename, output_filename)
