import re
import sys
import os

def fix_workspace(input_file, output_file, offset=1):
    if not os.path.exists(input_file):
        print(f"❌ 找不到文件: {input_file}")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    blocks = []
    pending_lines = []
    in_tag = False

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # 匹配标签
        match = re.match(r'<(\d+),(\d+)>', line_stripped)
        if match:
            start = int(match.group(1)) + offset
            end = int(match.group(2)) + offset
            new_range = (start, end)

            # 如果是个新页面区间，则新建 Block
            if not blocks or blocks[-1]["range"] != new_range:
                blocks.append({"range": new_range, "lines": []})

            # 将游离在外的宏观标题（存储在 pending 中）吸附进当前 Block
            if pending_lines:
                blocks[-1]["lines"].extend(pending_lines)
                pending_lines = []

            in_tag = True
        elif line_stripped == '</>':
            in_tag = False
        else:
            if in_tag:
                # 标签内的内容，直接追加
                blocks[-1]["lines"].append(line_stripped)
            else:
                # 游离在外的宏观标题，暂存进 pending，等待下一个标签认领
                pending_lines.append(line_stripped)

    # 兜底：如果文件末尾还有游离文本
    if pending_lines and blocks:
        blocks[-1]["lines"].extend(pending_lines)

    # 写入完美的新文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for b in blocks:
            f.write(f"<{b['range'][0]},{b['range'][1]}>\n\n")
            for l in b["lines"]:
                f.write(f"{l}\n\n")
            f.write("</>\n\n")

    print(f"✅ 完美重构！已修正偏移 (+{offset})，合并了同页，所有宏观标题已收入标签内部。")

if __name__ == "__main__":
    input_name = sys.argv[1] if len(sys.argv) > 1 else "23-self-care-toc_workspace.md"
    output_name = sys.argv[2] if len(sys.argv) > 2 else "23-self-care-toc_workspace_fixed.md"
    
    fix_workspace(input_name, output_name)
