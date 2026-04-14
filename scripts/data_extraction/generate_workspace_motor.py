import fitz  # PyMuPDF
import os
import argparse
import json
import io
import time
from PIL import Image
import google.generativeai as genai

def extract_toc_images(pdf_path):
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    doc.close()
    return images

def generate_workspace(pdf_path, output_md, toc_json, batch_size=60):
    if not os.path.exists(pdf_path) or not os.path.exists(toc_json):
        return print("❌ Error: 找不到 PDF 或 JSON 文件")

    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)

    print(f"📄 正在解析目录图片: {pdf_path}...")
    toc_images = extract_toc_images(pdf_path)
    
    with open(toc_json, 'r', encoding='utf-8') as tf:
        toc_data = json.load(tf)
        
    if isinstance(toc_data, list):
        toc_data = toc_data[0] if toc_data else {}
        
    nodes = []
    target_titles = []
    for sub in toc_data.get("submodules", []):
        for obj in sub.get("objectives", []):
            for phasal in obj.get("phasal_objectives", []):
                goals = phasal.get("goals", [])
                phasal_title = f"#### {phasal.get('index', '')} {phasal.get('title', '')}".strip()
                if not goals:
                    nodes.append({
                        "sub_title": sub.get("title", ""),
                        "obj_title": obj.get("title", ""),
                        "phasal_title": phasal_title,
                        "type": "phasal",
                        "title": phasal_title
                    })
                    target_titles.append(phasal_title)
                else:
                    for g in goals:
                        title = g.get('description', '').strip()
                        nodes.append({
                            "sub_title": sub.get("title", ""),
                            "obj_title": obj.get("title", ""),
                            "phasal_title": phasal_title,
                            "type": "goal",
                            "title": title
                        })
                        target_titles.append(title)

    print(f"👁️ 正在调用 Gemini 3.1 Pro (全局扫描模式，总锚点: {len(target_titles)})...")
    
    model = genai.GenerativeModel(
        model_name='gemini-3.1-pro-preview',
        generation_config={"response_mime_type": "application/json", "temperature": 0.0}
    )
    
    checkpoint_file = f"{os.path.splitext(os.path.basename(pdf_path))[0]}_mapping_checkpoint.json"
    mapping = {}
    
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
            pending_titles = [t for t in target_titles if t not in mapping]
            print(f"📥 成功加载进度存档！已恢复 {len(mapping)} 个页码，剩余待找目标: {len(pending_titles)} 个。")
        except Exception as e:
            print(f"⚠️ 无法读取进度存档: {e}，将重新开始。")
            pending_titles = target_titles.copy()
    else:
        pending_titles = target_titles.copy()

    # 【核心改动：不再按页码循环，而是按目标名单分块循环】
    for i in range(0, len(pending_titles), batch_size):
        current_targets = pending_titles[i:i+batch_size]
        
        chunk_start = i + 1
        chunk_end = min(i + batch_size, len(pending_titles))
        print(f"\n🔄 正在全局扫描第 {chunk_start}-{chunk_end} 项目标 (发送窗口: {len(current_targets)} 项)...")
        
        # 每次都把完整的 toc_images 塞进去！
        prompt = [
            *toc_images,
            "这是一份完整的教材目录图片。\n",
            "【🚨 致命警告 🚨】:\n",
            "1. 绝不能自己编造连续的页码。\n",
            "2. 必须严格读取图片中每一项旁边 **实际印刷的数字**（如 27, 222）！\n",
            "3. 只返回你确实在图片里看到的项目及页码，没看到的千万不要瞎编！\n\n",
            "【待寻找的目标列表】\n" + json.dumps(current_targets, ensure_ascii=False),
            "\n请严格返回一个 JSON 字典对象。格式示范：{\"A 仰卧时头部保持在中线 / 0-2 个月\": 28}。Key 是目标列表中的原话，Value 是对应的真实整数页码。"
        ]
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt, request_options={"timeout": 600})
                batch_mapping_raw = json.loads(response.text)
                
                batch_mapping = {}
                if isinstance(batch_mapping_raw, list):
                    for item in batch_mapping_raw:
                        if isinstance(item, dict):
                            if "title" in item and "page" in item:
                                batch_mapping[item["title"]] = item["page"]
                            else:
                                batch_mapping.update(item)
                elif isinstance(batch_mapping_raw, dict):
                    batch_mapping = batch_mapping_raw
                
                found_count = 0
                for k, v in batch_mapping.items():
                    if k in current_targets:
                        mapping[k] = v
                        found_count += 1
                
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)
                        
                print(f"✅ 本批次成功提取了 {found_count}/{len(current_targets)} 个页码 (进度已存档 💾)。")
                time.sleep(2)
                break
            except Exception as e:
                print(f"⚠️ 第 {chunk_start}-{chunk_end} 批次 第 {attempt+1} 次失败: {e}")
                if attempt == max_retries - 1:
                    print(f"❌ 该批次彻底失败。如果需要接续，请重新运行。")
                    return
                else:
                    time.sleep(5)
                    
    # 强制分配页码并按物理页排序
    for node in nodes:
        page = mapping.get(node["title"])
        node["_page"] = int(page) if page and str(page).isdigit() else None

    # 向下继承页码（如果个别没找到，直接继承上一个目标的页码，完美保底）
    last_known = 1
    for node in nodes:
        if node["_page"] is not None:
            last_known = node["_page"]
        else:
            node["_page"] = last_known

    nodes.sort(key=lambda x: x["_page"])

    for i in range(len(nodes)):
        start = nodes[i]["_page"]
        next_start = start
        for j in range(i+1, len(nodes)):
            if nodes[j]["_page"] > start:
                next_start = nodes[j]["_page"]
                break
        nodes[i]["_range_end"] = (next_start - 1) if next_start > start else start

    # 生成 Markdown
    with open(output_md, 'w', encoding='utf-8') as f:
        current_range = None
        current_sub = None
        current_obj = None
        current_h4 = None

        def close_tag():
            nonlocal current_range
            if current_range:
                f.write("</>\n\n")
                current_range = None

        def open_tag(s, e):
            nonlocal current_range, current_sub, current_obj, current_h4
            if current_range != (s, e):
                close_tag()
                f.write(f"<{s},{e}>\n\n")
                current_range = (s, e)
                current_sub = None
                current_obj = None
                current_h4 = None

        module_name = toc_data.get("module", "")
        if module_name:
            f.write(f"# Module: {module_name}\n\n")
        
        for node in nodes:
            s, e = node["_page"], node["_range_end"]
            open_tag(s, e)

            if node["sub_title"] != current_sub:
                f.write(f"## Submodule: {node['sub_title']}\n\n")
                current_sub = node["sub_title"]
                current_obj = None
                current_h4 = None
            if node["obj_title"] != current_obj:
                f.write(f"### Objective: {node['obj_title']}\n\n")
                current_obj = node["obj_title"]
                current_h4 = None
            if node["phasal_title"] != current_h4:
                f.write(f"{node['phasal_title']}\n\n")
                current_h4 = node["phasal_title"]

            if node["type"] == "goal":
                f.write(f"##### {node['title']}\n\n")
            else:
                f.write("##### [] \n\n")
        
        close_tag()

    print(f"\n✅ Workspace 完美生成: {output_md}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_file", help="TOC PDF")
    parser.add_argument("--toc_json", required=True, help="Skeleton JSON")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("-b", "--batch", type=int, default=60, help="每次发送的目标数量，默认 60")
    args = parser.parse_args()
    
    out = args.output if args.output else f"{os.path.splitext(os.path.basename(args.pdf_file))[0]}_workspace.md"
    generate_workspace(args.pdf_file, out, args.toc_json, args.batch)
