import json
import re
import os
import sys

def patch_markdown(md_file, json_file, output_file):
    if not os.path.exists(md_file) or not os.path.exists(json_file):
        print("❌ 找不到 Markdown 或 JSON 文件，请检查路径。")
        return

    # 1. 读取骨架 JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        skeleton = json.load(f)

    # 兼容大模型套了列表壳的情况
    if isinstance(skeleton, list):
        skeleton = skeleton[0] if skeleton else {}

    # 2. 建立精准映射字典 mapping["核心标题"] = ("Submodule名", "Objective名")
    mapping = {}
    for sub in skeleton.get("submodules", []):
        sub_title = sub.get("title", "").strip()
        for obj in sub.get("objectives", []):
            obj_title = obj.get("title", "").strip()
            for phasal in obj.get("phasal_objectives", []):
                title = phasal.get("title", "").strip()
                # 去除空格，提取纯核心词用于容错匹配
                clean_title = re.sub(r'\s+', '', title)
                mapping[clean_title] = (sub_title, obj_title)

    # 3. 读取 Reworked Markdown
    with open(md_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    out_lines = []
    
    # 状态机：跟踪所有层级的当前标题
    current_sub = None
    current_obj = None
    current_h4 = None

    for line in lines:
        # 【Level 2 去重】：处理已有的 Submodule
        m_sub = re.match(r'^##\s+Submodule:\s*(.*)', line)
        if m_sub:
            new_sub = m_sub.group(1).strip()
            if new_sub != current_sub:
                current_sub = new_sub
                # 级联重置：上级改变，下级状态必须清空
                current_obj = None
                current_h4 = None
                out_lines.append(line)
            continue

        # 【Level 3 去重】：处理已有的 Objective
        m_obj = re.match(r'^###\s+Objective:\s*(.*)', line)
        if m_obj:
            new_obj = m_obj.group(1).strip()
            if new_obj != current_obj:
                current_obj = new_obj
                # 级联重置：上级改变，下级状态必须清空
                current_h4 = None
                out_lines.append(line)
            continue

        # 【Level 4 去重 & 补漏】：处理项目 (####)
        m_h4 = re.match(r'^####\s+(.*)', line)
        if m_h4:
            raw_title = m_h4.group(1).strip()
            
            # 剥离 "项目一"、"项目"、"1.2" 等前缀，提取真正的主题词以供匹配
            core_title_match = re.search(r'(?:项目[一二三四五六七八九十]*|[\d\.]+)\s*：?\s*(.*)', raw_title)
            core_title = core_title_match.group(1) if core_title_match else raw_title
            core_title_clean = re.sub(r'\s+', '', core_title)

            matched_sub, matched_obj = None, None
            
            # 在 mapping 中匹配归属
            for k, v in mapping.items():
                if k in core_title_clean or core_title_clean in k:
                    matched_sub, matched_obj = v
                    break

            # 1. 补全缺失的上级标题
            if matched_sub and matched_obj:
                if matched_sub != current_sub:
                    out_lines.append(f"## Submodule: {matched_sub}\n\n")
                    current_sub = matched_sub
                    current_obj = None
                    current_h4 = None
                if matched_obj != current_obj:
                    out_lines.append(f"### Objective: {matched_obj}\n\n")
                    current_obj = matched_obj
                    current_h4 = None

            # 2. Level 4 自身的去重逻辑 (只有当项目名真正改变时才写入)
            if raw_title != current_h4:
                out_lines.append(line)
                current_h4 = raw_title

            continue

        # 普通文本（如五级目标、活动、材料）直接写入
        out_lines.append(line)

    # 4. 写出修复后的 Markdown
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)
        
    print(f"✅ 完美补救！已对 Level 2、3、4 标题执行【全层级去重】与【级联重置】。输出至: {output_file}")

if __name__ == "__main__":
    input_md = sys.argv[1] if len(sys.argv) > 1 else "24-emotions-toc_workspace_reworked.md"
    input_json = sys.argv[2] if len(sys.argv) > 2 else "24-social-emotions_skeleton.json"
    output_md = sys.argv[3] if len(sys.argv) > 3 else "24-emotions-toc_workspace_reworked_patched.md"
    
    patch_markdown(input_md, input_json, output_md)
