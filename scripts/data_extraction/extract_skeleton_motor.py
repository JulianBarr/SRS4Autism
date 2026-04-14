import fitz  # PyMuPDF
import os
import argparse
import json
import io
import time
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

def deep_merge_submodules(main_list, new_list):
    """深度合并增量数据，解决跨页的 Submodule 断层问题"""
    for new_sub in new_list:
        existing_sub = next((s for s in main_list if s.get('title') == new_sub.get('title')), None)
        if not existing_sub:
            main_list.append(new_sub)
            continue

        for new_obj in new_sub.get('objectives', []):
            existing_obj = next((o for o in existing_sub.get('objectives', []) if o.get('title') == new_obj.get('title')), None)
            if not existing_obj:
                existing_sub.setdefault('objectives', []).append(new_obj)
                continue

            for new_phasal in new_obj.get('phasal_objectives', []):
                existing_phasal = next((p for p in existing_obj.get('phasal_objectives', []) 
                                        if p.get('title') == new_phasal.get('title') and p.get('index') == new_phasal.get('index')), None)
                if not existing_phasal:
                    existing_obj.setdefault('phasal_objectives', []).append(new_phasal)
                    continue

                for new_goal in new_phasal.get('goals', []):
                    existing_goals_desc = [g.get('description') for g in existing_phasal.get('goals', [])]
                    if new_goal.get('description') not in existing_goals_desc:
                        existing_phasal.setdefault('goals', []).append(new_goal)

def extract_skeleton_incremental(pdf_path, output_json, module_name, batch_size=1, start_page=1):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return print("❌ Error: 请先设置 GEMINI_API_KEY 环境变量")
    
    genai.configure(api_key=api_key)

    print(f"📄 正在读取目录 PDF: {pdf_path}...")
    toc_images = extract_toc_images(pdf_path)
    total_pages = len(toc_images)
    
    system_prompt = f"""
    你是一个教材结构化专家。你将收到一份长目录的部分页码图片。
    请提取该页的层级结构，并转换为特定的 JSON **数组 (Array)**。

    【🚨 重要强制指令 🚨】
    1. 语言：请将所有繁体中文全部转换为 **简体中文** 输出！
    2. 提取第 5 级目标 (Goals)：如果目录中明确列出了具体目标 (A, B, C...)，务必提取到 `goals` 数组中。
    3. 第 6 级子项拍平：遇到不带字母的细分要求，与主目标合并拍平！(如 `[C-i] 骑单车：骑有辅助轮子的单车 / 4-5岁`)
    4. 跨页推断：如果某个项目看起来是上一页的延续，请尽量推断并写出它所属的 Submodule 和 Objective 标题。

    【严格格式】：请返回一个 JSON 数组，**不要在外层套 module 字典**：
    [
      {{
        "title": "次模块名称",
        "objectives": [
          {{
            "title": "重点名称",
            "phasal_objectives": [
              {{
                "index": "项目一",
                "title": "标题名称",
                "goals": [ {{ "description": "[A] 目标详情 / 0-2 个月" }} ]
              }}
            ]
          }}
        ]
      }}
    ]
    """

    model = genai.GenerativeModel(
        model_name='gemini-3.1-pro-preview',
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json", "temperature": 0.1}
    )

    all_submodules = []
    
    # 【断点续传加载逻辑】
    if start_page > 1 and os.path.exists(output_json):
        try:
            with open(output_json, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                all_submodules = existing_data.get("submodules", [])
            print(f"📥 成功加载之前的数据 (已包含 {len(all_submodules)} 个主模块)，将从第 {start_page} 页继续合并！")
        except Exception as e:
            print(f"⚠️ 无法读取已有进度: {e}，将重新开始。")

    # 增量循环处理
    for i in range(start_page - 1, total_pages, batch_size):
        batch_images = toc_images[i:i+batch_size]
        current_start = i + 1
        current_end = min(i + batch_size, total_pages)
        print(f"\n🔄 正在处理第 {current_start} 到 {current_end} 页 (共 {total_pages} 页)...")
        
        prompt_parts = [*batch_images, f"请解析这 {len(batch_images)} 页的目录结构，转为简体中文 JSON 数组返回。"]
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 设定更长的超时以防万一
                response = model.generate_content(prompt_parts, request_options={"timeout": 600})
                batch_data = json.loads(response.text)
                
                # 容错：如果大模型没听话，手动扒壳
                if isinstance(batch_data, dict) and "submodules" in batch_data:
                    batch_data = batch_data["submodules"]
                if not isinstance(batch_data, list):
                    batch_data = [batch_data]

                # 深度合并到主列表
                deep_merge_submodules(all_submodules, batch_data)
                
                # 【实时存档逻辑】
                final_skeleton = {
                    "module": module_name,
                    "submodules": all_submodules
                }
                with open(output_json, 'w', encoding='utf-8') as f:
                    json.dump(final_skeleton, f, ensure_ascii=False, indent=2)
                
                print(f"✅ 第 {current_start}-{current_end} 页提取成功！(进度已实时保存 💾)")
                
                time.sleep(2) # 停顿一下防限流
                break
                
            except Exception as e:
                print(f"⚠️ 批次 {current_start}-{current_end} 第 {attempt+1} 次尝试失败: {e}")
                if attempt == max_retries - 1:
                    print(f"❌ 该批次彻底失败。如果需要接续，请使用参数: --start_page {current_start}")
                    return # 彻底失败则停止脚本，保护已有进度
                else:
                    time.sleep(5) # 退避重试

    print(f"\n🎉 完美！全部 {total_pages} 页解析完成，全量 JSON 稳稳当当：{output_json}")
    print("➡️ 现在你可以继续运行 generate_workspace.py 了！")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Skeleton JSON from TOC PDF (Page-by-Page & Resume)")
    parser.add_argument("pdf_file", help="TOC PDF 文件的路径")
    parser.add_argument("-o", "--output", help="输出的 JSON 文件名", required=True)
    parser.add_argument("-m", "--module_name", help="强制设定的 Module 名称", required=True)
    parser.add_argument("-b", "--batch", type=int, default=1, help="每次处理的页数，默认 1 页")
    parser.add_argument("--start_page", type=int, default=1, help="从哪一页开始处理 (用于断点续传)")
    
    args = parser.parse_args()
    extract_skeleton_incremental(args.pdf_file, args.output, args.module_name, args.batch, args.start_page)
