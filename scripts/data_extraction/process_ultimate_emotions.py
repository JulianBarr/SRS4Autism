import os
import re
import json
import io
import time
import argparse
from PIL import Image
import fitz  # PyMuPDF
import google.generativeai as genai

# 【社交与情绪专属提示词】：强化语义分配、强制繁转简
SYSTEM_INSTRUCTION = """
你是一个专业的教材数据提取、语义分类与结构化助手。

【最高准则：保留框架 与 语义重组分配】
用户提供了一段包含了高层级目录（如 `#`, `##`, `###`, `####`）的工作区文本，以及对应的教材扫描图片。
教材图片中存在严重的排版分离问题：目标（Goals）通常在页面上方，而具体的活动建议（Activities）集中在页面下方，两者之间往往没有明确的编号对应。
你必须发挥你的【语义理解与逻辑推理能力】：
1. 仔细阅读每个「活动」的具体玩法、教具和句型。
2. 将页面底部的这些活动精准匹配，并根据语义自动分配、归类到它专属的「子目标（即 ##### 5级标题）」之下。
3. 绝对不能让子目标和它对应的活动脱节，严禁将所有活动统一堆砌在末尾！

【严格格式规范】
1. 原样保留框架标题：必须原封不动地保留用户工作区文本中的所有原有标题（如 `#### 项目一 认识次序`）。绝对不能删除或篡改它们。
2. 强制补充 5 级子目标：在对应的 `####` 标题下方，根据图片内容提取具体的子目标，并强制使用 `##### 5级标题` 格式。
   格式示例：##### [A] 目标名称 / 年龄段
3. 目标标签：将空白的 `[]` 替换为 `[A]`, `[B]`, `[C]` 等。
4. 语言统一 (强制简体)：图片内容为繁体中文，请你在输出所有新生成的活动建议、注意事项、教具材料时，**全部转换为简体中文**！
5. 标点统一：西式双引号变直角引号 「」。列表符号统一为 *。半角括号变全角 （）。
6. 粤语规范：补齐漏掉的「粤」字，格式如 （粤 唔该），字后加空格。
7. 输出要求：直接输出 Markdown 纯文本，不要包含在任何代码块包裹（如 ```markdown）中。
"""

def load_checkpoint(checkpoint_file):
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
            except: pass
    return {}

def save_checkpoint(data_dict, checkpoint_file):
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)

def get_images_from_pdf(pdf_doc, start_pg, end_pg, offset):
    images = []
    # PDF 是 0 索引，计算物理页码 = 传入页码 - offset - 1
    start_idx = int(start_pg) - offset - 1
    end_idx = int(end_pg) - offset - 1
    for pg_idx in range(start_idx, end_idx + 1):
        if 0 <= pg_idx < len(pdf_doc):
            page = pdf_doc.load_page(pg_idx)
            # 提高 DPI 以确保 OCR 准确
            pix = page.get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

def write_full_file(output_file, chunks, results_cache):
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for chunk in chunks:
            if chunk["type"] == "raw":
                out_f.write(chunk["text"])
            elif chunk["type"] == "gemini":
                block_id = chunk["id"]
                # 重新包裹回原本的标签
                out_f.write(f"<{chunk['start_pg']},{chunk['end_pg']}>\n\n")
                if block_id in results_cache:
                    out_f.write(results_cache[block_id] + "\n\n")
                else:
                    out_f.write(chunk["text"] + "\n\n")
                    out_f.write(f"<!-- ⏳ 待处理: <{block_id}> -->\n\n")
                out_f.write("</>\n\n")
        out_f.flush()
        os.fsync(out_f.fileno())

def process_document(input_file, pdf_file, output_file, checkpoint_file, offset):
    if not os.path.exists(pdf_file): 
        return print(f"❌ 找不到 PDF 文件: {pdf_file}")
    if not os.path.exists(input_file):
        return print(f"❌ 找不到 Input 文件: {input_file}")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("未找到 GEMINI_API_KEY 环境变量，请先设置！")

    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel(
        model_name='gemini-3.1-pro-preview',
        system_instruction=SYSTEM_INSTRUCTION,
        generation_config=genai.GenerationConfig(temperature=0.1)
    )
    
    pdf_doc = fitz.open(pdf_file)
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 匹配 <页码> ... </>
    pattern = re.compile(r'<(\d+)(?:,(\d+))?>(.*?)</>', re.DOTALL)
    last_end, chunks = 0, []
    
    for match in pattern.finditer(content):
        if match.start() > last_end:
            chunks.append({"type": "raw", "text": content[last_end:match.start()]})
        
        start_pg = match.group(1)
        end_pg = match.group(2) if match.group(2) else start_pg
        chunks.append({
            "type": "gemini", "id": f"{start_pg}-{end_pg}",
            "start_pg": start_pg, "end_pg": end_pg, "text": match.group(3).strip()
        })
        last_end = match.end()
        
    if last_end < len(content):
        chunks.append({"type": "raw", "text": content[last_end:]})

    results_cache = load_checkpoint(checkpoint_file)
    write_full_file(output_file, chunks, results_cache)

    print(f"🚀 开始处理《社交与情绪》，共 {len([c for c in chunks if c['type']=='gemini'])} 个区块...")

    for chunk in chunks:
        if chunk["type"] == "gemini":
            bid = chunk["id"]
            if bid in results_cache: continue
            
            print(f"⚙️ 正在使用 3.1-Pro 处理页码 <{bid}> (强制简体版)...")
            images = get_images_from_pdf(pdf_doc, chunk["start_pg"], chunk["end_pg"], offset)
            
            prompt = [
                *images,
                f"这是工作区文本，里面包含了你必须【原样保留】的目录结构标题。请仔细阅读图片，将繁体内容转为简体，并将活动建议根据语义精准分配到对应的目标下方，使用 ##### 5级标题结构。\n\n工作区文本：\n{chunk['text']}"
            ]
            
            try:
                # 设定 600秒超时，保证长任务顺利执行
                response = model.generate_content(prompt, request_options={"timeout": 600})
                res_text = response.text.strip()
                
                # 清洗 Markdown 包裹
                res_text = re.sub(r'^```markdown\s*', '', res_text)
                res_text = re.sub(r'^```\s*', '', res_text)
                res_text = re.sub(r'\s*```$', '', res_text)
                
                results_cache[bid] = res_text.strip()
                save_checkpoint(results_cache, checkpoint_file)
                write_full_file(output_file, chunks, results_cache)
                print(f"✅ 页码 <{bid}> 处理并同步成功！")
                
                # 成功后稍微等一下，避免请求过快
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ 页码 <{bid}> 失败（将跳过并继续）: {e}")
                continue

    pdf_doc.close()
    print("\n🎉 处理任务结束。未成功的区块将在下次运行时重新尝试。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Workspace Markdown with Gemini Vision (Emotions Edition)")
    
    parser.add_argument("input_md", help="人工预处理后的 Markdown workspace 文件")
    parser.add_argument("pdf_file", help="原始整本教材的 PDF 文件")
    parser.add_argument("-o", "--output", default=None, help="输出清洗后的 Markdown 文件")
    parser.add_argument("--offset", type=int, default=0, help="PDF页码与MD页码的差值，如 MD 记为15但PDF是14页，则 offset=1")
    parser.add_argument("--checkpoint", default=None, help="指定 checkpoint 文件的名称")
    
    args = parser.parse_args()
    
    # 自动生成 output 和 checkpoint 名称
    base_name = os.path.splitext(os.path.basename(args.input_md))[0]
    output_file = args.output if args.output else f"{base_name}_reworked.md"
    checkpoint_file = args.checkpoint if args.checkpoint else f"{base_name}_checkpoint.json"
    
    process_document(args.input_md, args.pdf_file, output_file, checkpoint_file, args.offset)
