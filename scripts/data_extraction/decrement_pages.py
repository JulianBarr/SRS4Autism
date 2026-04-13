import re
import sys
import os

def decrement_pages(filename):
    if not os.path.exists(filename):
        print(f"❌ 找不到文件: {filename}")
        return

    # 读取文件内容
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换函数：将捕获到的页码转为整数并减 1
    def replacer(match):
        start = int(match.group(1)) - 1
        end = int(match.group(2)) - 1
        return f"<{start},{end}>"

    # 正则匹配 <数字,数字>
    new_content = re.sub(r'<(\d+),(\d+)>', replacer, content)

    # 覆盖写回原文件
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"✅ 搞定！已成功将 {filename} 中的所有 <页码,页码> 减去了 1。")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        decrement_pages(sys.argv[1])
    else:
        print("💡 用法: python decrement_pages.py <你的markdown文件>")
