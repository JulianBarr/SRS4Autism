import os
import re
import json
import argparse

def parse_markdown_to_json(md_file, output_json):
    if not os.path.exists(md_file):
        print(f"❌ 找不到文件: {md_file}")
        return

    with open(md_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    ontology = {
        "module": "",
        "submodules": []
    }

    current_sub = None
    current_obj = None
    current_phasal = None
    current_goal = None
    
    # 用于缓存当前 Goal 下的文本段落
    current_text_buffer = []

    def flush_goal_content():
        """把积累的文本解析为结构化字段并塞入当前的 Goal 中"""
        if current_goal and current_text_buffer:
            full_text = "\n".join(current_text_buffer).strip()
            if full_text and not full_text.startswith("[]"):
                # 初始化字段
                activities = []
                materials = []
                precautions = []
                passing_criteria = ""

                # 简单的启发式文本分类 (根据常见前缀划分)
                blocks = re.split(r'\n(?=\* \*\*|\*\*|活动建议|材料|注意事项|Passing Criteria)', full_text)
                
                for block in blocks:
                    b_str = block.strip()
                    if not b_str: continue
                    
                    b_lower = b_str.lower()
                    if "passing criteria" in b_lower or "通过准则" in b_lower:
                        passing_criteria = re.sub(r'^(\* \*\*|\*\*)?(Passing Criteria|通过准则)[:：]?(\*\*|\*)?\s*', '', b_str, flags=re.IGNORECASE).strip()
                    elif "材料" in b_lower or "教具" in b_lower or "material" in b_lower:
                        items = [re.sub(r'^[-*]\s*', '', item.strip()) for item in b_str.split('\n') if item.strip()]
                        if items: materials.extend(items[1:] if items[0].startswith('**') or '材料' in items[0] else items)
                    elif "注意" in b_lower or "precaution" in b_lower:
                        precautions.append(b_str)
                    else:
                        # 默认作为活动建议
                        activities.append(b_str)

                current_goal["activities"] = activities
                current_goal["materials"] = list(set(materials)) # 去重
                current_goal["precautions"] = precautions
                if passing_criteria:
                    current_goal["passing_criteria"] = passing_criteria
                    
            current_text_buffer.clear()

    for line in lines:
        raw_line = line.strip()
        if not raw_line:
            continue

        # 匹配标题层级
        if raw_line.startswith('# '):
            flush_goal_content()
            ontology["module"] = raw_line.replace('# Module:', '').replace('#', '').strip()
        
        elif raw_line.startswith('## '):
            flush_goal_content()
            sub_title = raw_line.replace('## Submodule:', '').replace('##', '').strip()
            current_sub = {"title": sub_title, "objectives": []}
            ontology["submodules"].append(current_sub)
            current_obj = None
            current_phasal = None
            current_goal = None
            
        elif raw_line.startswith('### '):
            flush_goal_content()
            if current_sub is not None:
                obj_title = raw_line.replace('### Objective:', '').replace('###', '').strip()
                current_obj = {"title": obj_title, "phasal_objectives": []}
                current_sub["objectives"].append(current_obj)
                current_phasal = None
                current_goal = None
                
        elif raw_line.startswith('#### '):
            flush_goal_content()
            if current_obj is not None:
                # 尝试分离 index 和 title (例如: 项目一 仰卧)
                match = re.match(r'^####\s+(项目[一二三四五六七八九十]+)\s+(.*)', raw_line)
                if match:
                    index, title = match.groups()
                else:
                    index, title = "", raw_line.replace('####', '').strip()
                
                current_phasal = {"index": index, "title": title, "goals": []}
                current_obj["phasal_objectives"].append(current_phasal)
                current_goal = None
                
        elif raw_line.startswith('##### '):
            flush_goal_content()
            if current_phasal is not None:
                desc = raw_line.replace('#####', '').strip()
                current_goal = {"description": desc}
                current_phasal["goals"].append(current_goal)
        
        # 匹配非标题正文（过滤掉标签如 <18,18> 和 </>）
        elif not re.match(r'^<.*>$', raw_line) and not raw_line.startswith('<!--'):
            if current_goal is not None:
                current_text_buffer.append(raw_line)

    # 循环结束后，处理最后一个 goal 的缓冲文本
    flush_goal_content()

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(ontology, f, ensure_ascii=False, indent=2)

    print(f"🎉 完美！Markdown 已成功转换为精美的 A-Box JSON: {output_json}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Patched Motor Markdown to A-Box JSON")
    parser.add_argument("md_file", help="去重后的 patched markdown 文件")
    parser.add_argument("-o", "--output", default="motor_abox.json", help="输出的 JSON 文件路径")
    
    args = parser.parse_args()
    parse_markdown_to_json(args.md_file, args.output)
