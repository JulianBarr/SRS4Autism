import json
import re
import os

def split_materials(mat_str):
    """
    智能切分材料字符串，按逗号/顿号切分，但完美保护括号内的内容不被切碎。
    例如："玩具车（如：巴士、的士）、苹果" -> ["玩具车（如：巴士、的士）", "苹果"]
    """
    mats = []
    current_mat = ""
    depth = 0
    for char in mat_str:
        if char in "([（【":
            depth += 1
        elif char in ")]）】":
            depth -= 1
            if depth < 0: depth = 0
            
        if depth == 0 and char in ",，、":
            if current_mat.strip():
                mats.append(current_mat.strip())
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
    state_indent = 0
    shared_precautions_text = ""
    current_activities = []

    h1_pat = re.compile(r'^#\s+Module:\s*(.*)')
    h2_pat = re.compile(r'^##\s+Submodule:\s*(.*)')
    h3_pat = re.compile(r'^###\s+Objective:\s*(.*)')
    h4_pat = re.compile(r'^####\s+(.*)')
    h5_pat = re.compile(r'^#####\s+(.*)')

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
            current_objective = {"title": h3_pat.match(stripped).group(1).strip(), "phasal_objectives": []}
            if current_submodule is not None:
                current_submodule["objectives"].append(current_objective)
            current_phasal = None
            current_goal = None
            current_state = None
            continue

        if h4_pat.match(stripped):
            # 离开上一个 #### 前，保存最后一个 Goal 的活动
            if current_goal is not None and current_activities:
                current_goal["activity_suggestions"] = "\n".join(current_activities)

            raw_title = h4_pat.match(stripped).group(1).strip()
            index = ""
            title = raw_title
            
            idx_match = re.match(r'^([\d\.]+)\s+(.*)', raw_title)
            if idx_match:
                index = idx_match.group(1)
                title = idx_match.group(2)
            else:
                idx_match2 = re.match(r'^(项目[一二三四五六七八九十]+)：?\s*(.*)', raw_title)
                if idx_match2:
                    index = idx_match2.group(1)
                    title = idx_match2.group(2)

            current_phasal = {
                "index": index,
                "title": title,
                "goals": []
            }
            if current_objective is not None:
                current_objective["phasal_objectives"].append(current_phasal)
            
            current_goal = None
            current_activities = []
            shared_precautions_text = ""
            current_state = None
            continue

        if h5_pat.match(stripped):
            # ============================================================
            # 【原子性恢复】每一个 ##### 都是一张独立的卡片 (New Goal Object)
            # ============================================================
            if current_goal is not None and current_activities:
                current_goal["activity_suggestions"] = "\n".join(current_activities)
                
            raw_desc = h5_pat.match(stripped).group(1).strip()
            
            letter_match = re.match(r'^((?:\[[A-Z]\])+)\s*(.*)', raw_desc)
            if letter_match:
                letters = letter_match.group(1).replace('[', '').replace(']', ', ').strip(', ')
                raw_desc = f"{letters}. {letter_match.group(2)}"
            else:
                empty_match = re.match(r'^\[\]\s*(.*)', raw_desc)
                if empty_match:
                    raw_desc = empty_match.group(1).strip()
                
            if '|' in raw_desc:
                parts = raw_desc.rsplit('|', 1)
                goal_desc = f"{parts[0].strip()} / {parts[1].strip()}"
            else:
                match = re.search(r'\s*/\s*([\d>\-]+\s*(?:岁|个月).*)$', raw_desc)
                if match:
                    goal_desc = f"{raw_desc[:match.start()].strip()} / {match.group(1).strip()}"
                else:
                    goal_desc = raw_desc
            
            # 创建全新的 Goal 字典（卡片）
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
            
            # 重置当前活动的收集池
            current_activities = []
            current_state = None
            continue

        # ============================================================
        # 缩进感知与多语言触发器
        # ============================================================
        indent_match = re.match(r'^(\s*)', raw_line)
        current_indent = len(indent_match.group(1)) if indent_match else 0
        
        clean_stripped = re.sub(r'\*\*', '', stripped)
        
        is_sprec = re.match(r'^(?:[\*\-]\s*)?(Shared Precautions|共同注意事项)\s*[:：]?\s*(.*)', clean_stripped, re.IGNORECASE)
        is_prec = re.match(r'^(?:[\*\-]\s*)?(Precautions|注意事项)\s*[:：]?\s*(.*)', clean_stripped, re.IGNORECASE)
        is_mat = re.match(r'^(?:[\*\-]\s*)?(Materials|材料|教具)\s*[:：]?\s*(.*)', clean_stripped, re.IGNORECASE)
        is_act = re.match(r'^(?:[\*\-]\s*)?(Activities|活动建议|活动|玩法|步骤)\s*\d*\s*[:：]?\s*(.*)', clean_stripped, re.IGNORECASE)
        
        is_bullet = bool(re.match(r'^[\*\-]\s+', stripped))

        if is_sprec:
            current_state = "shared_precautions"
            state_indent = current_indent
            val = is_sprec.group(2).strip()
            if val: shared_precautions_text += ("\n" + val if shared_precautions_text else val)
            continue

        if is_prec:
            current_state = "precautions"
            state_indent = current_indent
            val = is_prec.group(2).strip()
            if val and current_goal is not None:
                current_goal["precautions"] = (current_goal["precautions"] + "\n" + val) if current_goal["precautions"] else val
            continue

        if is_mat:
            current_state = "materials"
            state_indent = current_indent
            val = is_mat.group(2).strip()
            if val and current_goal is not None:
                for m in split_materials(val):
                    if m not in current_goal["materials"]:
                        current_goal["materials"].append(m)
            continue

        if is_act:
            current_state = "activities"
            state_indent = current_indent
            # 【重要修复】：仅抓取冒号后面的内容。如果是纯表头 "* 活动建议："，val 将为空，就不会把 "活动建议：" 当成活动录入了！
            val = is_act.group(2).strip()
            if val and current_goal is not None:
                current_activities.append(val)
            continue

        if is_bullet:
            # 缩进感知弹出逻辑：如果子弹点缩进 <= 刚才的材料/注意事项，说明退出了材料状态，回到了同级的活动状态！
            if current_state in ["materials", "precautions", "shared_precautions"]:
                if current_indent <= state_indent:
                    current_state = "activities"
            
            val = re.sub(r'^[\*\-]\s+', '', clean_stripped)
            if not val: continue
            
            if current_state == "activities" and current_goal is not None:
                current_activities.append(val)
            elif current_state == "materials" and current_goal is not None:
                for m in split_materials(val):
                    if m not in current_goal["materials"]:
                        current_goal["materials"].append(m)
            elif current_state == "precautions" and current_goal is not None:
                current_goal["precautions"] = (current_goal["precautions"] + "\n" + val) if current_goal["precautions"] else val
            elif current_state == "shared_precautions":
                shared_precautions_text += ("\n" + val if shared_precautions_text else val)
        else:
            # 纯文本多行续写
            if not current_state: continue
            val = clean_stripped
            
            if current_state == "activities" and current_goal is not None:
                if current_activities:
                    current_activities[-1] += "\n" + val
                else:
                    current_activities.append(val)
            elif current_state == "materials" and current_goal is not None:
                for m in split_materials(val):
                    if m not in current_goal["materials"]:
                        current_goal["materials"].append(m)
            elif current_state == "precautions" and current_goal is not None:
                current_goal["precautions"] = (current_goal["precautions"] + "\n" + val) if current_goal["precautions"] else val
            elif current_state == "shared_precautions":
                shared_precautions_text += ("\n" + val if shared_precautions_text else val)

    # 保存文件末尾最后收集到的活动
    if current_goal is not None and current_activities:
        current_goal["activity_suggestions"] = "\n".join(current_activities)

    # 导出 JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Successfully converted {input_file} to {output_file} (Atomic Cards Restored!)")

if __name__ == "__main__":
    input_filename = "22-cognition-toc_workspace_reworked.md"
    output_filename = "22_cognition_enriched_abox.json"
    parse_md_to_json(input_filename, output_filename)
