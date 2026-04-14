import fitz  # PyMuPDF
import os
import argparse
import json
import io
from PIL import Image
import google.generativeai as genai

def extract_toc_images(pdf_path):
    """将 TOC PDF 渲染为图像序列"""
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
        
    # 【防御性容错装甲】：如果大模型在外层套了列表 []，自动扒掉！
    if isinstance(toc_data, list):
        if len(toc_data) > 0:
            toc_data = toc_data[0]
        else:
            toc_data = {}
        
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
        "\n请严格返回一个 JSON 对象，Key 是标题列表中的原话，Value 是你在图中看到的整数页码。不要包含代码块包裹。"
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

    # 生成 Markdown (应用【包裹原则】与【聚合原则】)
    with open(output_md, 'w', encoding='utf-8') as f:
        current_range = None

        def close_tag():
            nonlocal current_range
            if current_range:
                f.write("</>\n\n")
                current_range = None

        def open_tag(s, e):
            nonlocal current_range
            if current_range != (s, e):
                close_tag()
                f.write(f"<{s},{e}>\n\n")
                current_range = (s, e)

        module_name = toc_data.get("module", "")
        # 注意：为了让大模型知道全貌，我们将 Module 等也收入第一个标签
        first_node = nodes[0] if nodes else None
        if first_node:
            open_tag(first_node["_start_page"], first_node["_range_end"])

        if module_name:
            f.write(f"# Module: {module_name}\n\n")
        
        for sub in toc_data.get("submodules", []):
            for obj in sub.get("objectives", []):
                # 遍历 phasal 来决定标签切换
                for phasal in obj.get("phasal_objectives", []):
                    s, e = phasal["_start_page"], phasal["_range_end"]
                    
                    # 检查是否需要切换标签
                    if current_range != (s, e):
                        open_tag(s, e)
                        # 如果是新标签的开始，补上 Submodule 和 Objective 的标题上下文
                        f.write(f"## Submodule: {sub.get('title', '')}\n\n")
                        f.write(f"### Objective: {obj.get('title', '')}\n\n")

                    f.write(f"#### {phasal.get('index', '')} {phasal.get('title', '')}".strip() + "\n\n")
                    
                    # 如果 skeleton 里已经有 goals，预填占位符
                    goals = phasal.get("goals", [])
                    if goals:
                        for g in goals:
                            f.write(f"##### {g.get('description', '')}\n\n")
                    else:
                        # 如果没有，留一个空占位符给大模型填
                        f.write(f"##### [] \n\n")
        
        close_tag()

    print(f"✅ Workspace 完美生成: {output_md}")
    print("🚀 结构已聚合，标题已内置。确认页码无误后可直接跑 process_ultimate_emotions.py。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_file", help="TOC PDF")
    parser.add_argument("--toc_json", required=True, help="Skeleton JSON")
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()
    
    out = args.output if args.output else f"{os.path.splitext(os.path.basename(args.pdf_file))[0]}_workspace.md"
    generate_workspace(args.pdf_file, out, args.toc_json)
