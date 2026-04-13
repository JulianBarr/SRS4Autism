import fitz  # PyMuPDF
import os
import argparse
import json
import io
from PIL import Image
import google.generativeai as genai

def extract_toc_images(pdf_path):
    """将扫描版 TOC PDF 渲染为图像序列"""
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    doc.close()
    return images

def generate_workspace(pdf_path, output_md, toc_json):
    if not os.path.exists(pdf_path):
        return print(f"❌ Error: 找不到 PDF 文件 {pdf_path}")
    if not os.path.exists(toc_json):
        return print(f"❌ Error: 找不到 JSON 文件 {toc_json}")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return print("❌ Error: 请设置 GEMINI_API_KEY 环境变量")
    genai.configure(api_key=api_key)

    print(f"📄 正在解析目录图片: {pdf_path}...")
    toc_images = extract_toc_images(pdf_path)
    
    with open(toc_json, 'r', encoding='utf-8') as tf:
        toc_data = json.load(tf)
        
    # 展平项目标题，准备进行视觉识别
    nodes = []
    target_titles = []
    for sub in toc_data.get("submodules", []):
        for obj in sub.get("objectives", []):
            for phasal in obj.get("phasal_objectives", []):
                nodes.append(phasal)
                full_title = f"{phasal.get('index', '')} {phasal.get('title', '')}".strip()
                target_titles.append(full_title)

    print(f"👁️ 正在调用 Gemini 视觉识别页码 (目标条目: {len(target_titles)})...")
    
    prompt = [
        *toc_images,
        "这是一份教材的目录图片。请识别并返回下列标题对应的页码数字。\n",
        "【标题列表】\n" + json.dumps(target_titles, ensure_ascii=False),
        "\n请返回一个 JSON 对象，Key 是标题，Value 是整数页码。不要包含任何 Markdown 代码块包裹。"
    ]

    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        generation_config={"response_mime_type": "application/json", "temperature": 0.1}
    )
    
    try:
        response = model.generate_content(prompt)
        mapping = json.loads(response.text)
        print("✅ 页码识别成功。")
    except Exception as e:
        print(f"❌ 识别失败: {e}")
        return
        
    # 映射页码并计算区间
    last_page = 1
    for node in nodes:
        title = f"{node.get('index', '')} {node.get('title', '')}".strip()
        page = mapping.get(title)
        node["_start_page"] = int(page) if page and str(page).isdigit() else last_page
        last_page = node["_start_page"]
            
    for i in range(len(nodes)):
        start = nodes[i]["_start_page"]
        next_start = start
        for j in range(i+1, len(nodes)):
            if nodes[j]["_start_page"] > start:
                next_start = nodes[j]["_start_page"]
                break
        nodes[i]["_range_end"] = (next_start - 1) if next_start > start else start

    # 生成遵循“容纳原则”的 Markdown
    with open(output_md, 'w', encoding='utf-8') as f:
        module_name = toc_data.get("module", "")
        if module_name:
            f.write(f"# Module: {module_name}\n\n")
        
        for sub in toc_data.get("submodules", []):
            f.write(f"## Submodule: {sub.get('title', '')}\n\n")
            
            for obj in sub.get("objectives", []):
                f.write(f"### Objective: {obj.get('title', '')}\n\n")
                
                for phasal in obj.get("phasal_objectives", []):
                    start_pg = phasal["_start_page"]
                    end_pg = phasal["_range_end"]
                    
                    # 关键原则：页码标签包裹 #### 和 #####
                    f.write(f"<{start_pg},{end_pg}>\n\n")
                    f.write(f"#### {phasal.get('index', '')} {phasal.get('title', '')}".strip() + "\n\n")
                    
                    # 自动注入从 JSON 中提取的五级目标
                    for goal in phasal.get("goals", []):
                        # 格式化为 ##### [A] 目标描述
                        desc = goal.get("description", "")
                        f.write(f"##### {desc}\n\n")
                        
                    f.write("</>\n\n")

    print(f"✅ Workspace 已生成: {output_md}")
    print("👉 现在的格式已将标题和目标全部包在标签内。请检查页码区间后即可重跑 process_ultimate.py。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_file", help="TOC PDF 文件")
    parser.add_argument("--toc_json", required=True, help="Skeleton JSON 文件")
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()
    
    output_file = args.output if args.output else f"{os.path.splitext(os.path.basename(args.pdf_file))[0]}_workspace.md"
    generate_workspace(args.pdf_file, output_file, args.toc_json)
