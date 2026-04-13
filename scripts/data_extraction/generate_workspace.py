import fitz  # PyMuPDF
import os
import argparse
import json
import io
from PIL import Image
import google.generativeai as genai

def extract_toc_images(pdf_path):
    """将纯图片 PDF 的每一页渲染为高清图像，准备交给大模型查阅"""
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
        return print(f"❌ Error: 找不到 TOC JSON 文件 {toc_json}")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return print("❌ Error: 找不到 GEMINI_API_KEY 环境变量，请先设置！")
    genai.configure(api_key=api_key)

    print(f"📄 侦测到纯图片目录，正在将 {pdf_path} 转换为图像序列...")
    toc_images = extract_toc_images(pdf_path)
    
    print(f"🧠 正在加载 {toc_json} 结构体...")
    with open(toc_json, 'r', encoding='utf-8') as tf:
        toc_data = json.load(tf)
        
    # 1. 展平所有目标，生成“通缉名单”
    nodes = []
    target_titles = []
    for sub in toc_data.get("submodules", []):
        for obj in sub.get("objectives", []):
            for phasal in obj.get("phasal_objectives", []):
                nodes.append(phasal)
                full_title = f"{phasal.get('index', '')} {phasal.get('title', '')}".strip()
                target_titles.append(full_title)

    print(f"👁️ 正在呼叫 Gemini 视觉模型，阅读目录图片并提取页码 (共需查找 {len(target_titles)} 个条目)...")
    
    prompt = [
        *toc_images,
        "这是一份儿童教材的扫描版目录图片。请用你的视觉能力阅读图片，并找出我提供的下列标题在目录中所对应的页码数字。\n",
        "【目标标题列表】\n" + json.dumps(target_titles, ensure_ascii=False) + "\n\n",
        "请严格返回一个 JSON 对象。JSON的键（Key）必须是目标标题列表中的原话，值（Value）是你在图片目录中看到的对应整数页码。\n",
        "切记：不要包含任何 Markdown 标记（如 ```json），只输出纯合法的 JSON 文本！"
    ]

    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        generation_config={"response_mime_type": "application/json", "temperature": 0.1}
    )
    
    try:
        response = model.generate_content(prompt)
        mapping = json.loads(response.text)
        print("✅ 成功！大模型已看图识别并提取出页码映射关系。")
    except Exception as e:
        print(f"❌ 大模型识别失败: {e}")
        return
        
    # 2. 将页码塞回 JSON 节点中
    last_page = 1
    for node in nodes:
        full_title = f"{node.get('index', '')} {node.get('title', '')}".strip()
        page = mapping.get(full_title)
        
        if page and str(page).isdigit():
            node["_start_page"] = int(page)
            last_page = int(page)
        else:
            node["_start_page"] = last_page
            
    # 3. 自动计算页码区间
    for i in range(len(nodes)):
        start_pg = nodes[i]["_start_page"]
        next_pg = start_pg
        for j in range(i+1, len(nodes)):
            if nodes[j]["_start_page"] > start_pg:
                next_pg = nodes[j]["_start_page"]
                break
        
        if next_pg > start_pg:
            end_pg = next_pg - 1
        else:
            end_pg = start_pg
        
        nodes[i]["_range_start"] = start_pg
        nodes[i]["_range_end"] = end_pg

    # 4. 生成 Markdown (应用【容纳原则】与【标签包裹】)
    with open(output_md, 'w', encoding='utf-8') as f:
        current_range = None

        def close_chunk(file_obj):
            nonlocal current_range
            if current_range is not None:
                file_obj.write("</>\n\n")
                current_range = None

        def open_chunk(file_obj, start, end):
            nonlocal current_range
            if current_range != (start, end):
                close_chunk(file_obj)
                current_range = (start, end)
                file_obj.write(f"<{start},{end}>\n\n")

        module_name = toc_data.get("module", "")
        if module_name:
            close_chunk(f) # 确保宏观标题在标签外
            f.write(f"# Module: {module_name}\n\n")
        
        for sub in toc_data.get("submodules", []):
            close_chunk(f)
            f.write(f"## Submodule: {sub.get('title', '')}\n\n")
            
            for obj in sub.get("objectives", []):
                close_chunk(f)
                f.write(f"### Objective: {obj.get('title', '')}\n\n")
                
                for phasal in obj.get("phasal_objectives", []):
                    start = phasal.get('_range_start', 1)
                    end = phasal.get('_range_end', 1)
                    
                    # 动态打开或复用当前的 <页码> 标签
                    open_chunk(f, start, end)
                    
                    idx = phasal.get("index", "")
                    p_title = phasal.get("title", "")
                    header = f"#### {idx} {p_title}".strip()
                    
                    # 关键修改：将 header 写在 <页码> 标签内部！
                    f.write(f"{header}\n\n")
        
        # 结尾必须关闭最后一个标签
        close_chunk(f)

    print(f"✅ Workspace 完美生成: {output_md}")
    print("🎉 魔法完成！所有 #### 标题已被精准包裹在 <页码> 标签内，且同页标题已合并！")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a smart Markdown workspace with Vision AI OCR mapped page tags.")
    parser.add_argument("pdf_file", help="Path to the TOC PDF file (纯图片扫描版)")
    parser.add_argument("--toc_json", required=True, help="Path to the TOC skeleton JSON file")
    parser.add_argument("-o", "--output", help="Path to the output Markdown file", default=None)
    
    args = parser.parse_args()
    output_file = args.output
    if not output_file:
        base_name = os.path.splitext(os.path.basename(args.pdf_file))[0]
        output_file = f"{base_name}_workspace.md"
        
    generate_workspace(args.pdf_file, output_file, args.toc_json)
