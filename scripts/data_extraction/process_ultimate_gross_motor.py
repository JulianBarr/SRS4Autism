import os
import re
import json
import io
import time
import argparse
from PIL import Image
import fitz  # PyMuPDF
import google.generativeai as genai

# 【大/小肌肉专属提示词】：精准填充、强制克隆、提取通过准则
SYSTEM_INSTRUCTION = """
你是一个专业的特教教材数据提取、语义分类与结构化助手。

【最高准则：精准填充 与 共享克隆】
用户提供的工作区文本中，已经包含了【完全拍平】的具体训练目标（如 `##### [A-i] ...`）。
你必须发挥你的【语义理解与逻辑推理能力】，阅读提供的教材扫描图片，完成以下任务：

1. 提取并分配内容：将图片下方的「活动建议(Activities)」、「注意事项(Precautions)」和「材料/教具(Materials)」精准分配到对应的 `#####` 目标下方。
2. 提取通过准则：仔细寻找每个目标特有的评估标准（通常在表格或目标的后缀说明中），必须提取并置于对应的 `#####` 目标下方，使用前缀 `* **Passing Criteria:**`。
3. 共享内容克隆 (Crucial)：在大/小肌肉教材中，多个子目标（如 A-i, A-ii, A-iii）通常共用同一套活动建议和材料。你必须将这些共享内容【完整复制一份】，分配给每一个对应的 `#####` 目标。绝不能让任何一个目标成为没有活动的“空壳”。
4. 原样保留框架标题：工作区中的 `#`, `##`, `###`, `####`, `#####` 标题必须原封不动保留，严禁篡改或删除！
5. 语言统一 (强制简体)：图片内容为繁体中文，输出的新内容必须【全部转换为简体中文】。西式双引号变直角引号 「」。
6. 直接输出纯文本：不要包含在任何 ```markdown 代码块中。
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
    # PyMuPDF 是 0 索引，计算物理索引 = 传入标签页码 - offset - 1
    # 例如：标签 <178>, offset=-1 -> 178 - (-1) - 1 = 178。索引 178 代表第 179 页物理页。
    start_idx = int(start_pg) - offset - 1
    end_idx = int(end_pg) - offset - 1
    for pg_idx in range(start_idx, end_idx + 1):
        if 0 <= pg_idx < len(pdf_doc):
            page = pdf_doc.load_page(pg_idx)
            # 提高 DPI 保证 OCR 清晰度
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

    print(f"🚀 开始处理《大肌肉》，共 {len([c for c in chunks if c['type']=='gemini'])} 个区块...")

    for chunk in chunks:
        if chunk["type"] == "gemini":
            bid = chunk["id"]
            if bid in results_cache: continue
            
            print(f"⚙️ 正在使用 3.1-Pro 处理页码 <{bid}>...")
            images = get_images_from_pdf(pdf_doc, chunk["start_pg"], chunk["end_pg"], offset)
            
            prompt = [
                *images,
                f"这是工作区文本，请仔细阅读图片。根据图片把活动建议、教具和 Passing Criteria 分配到已经建立好的 ##### 标题下。记住：共享的内容必须克隆给每一个对应的子标题！转化为简体中文。\n\n工作区文本：\n{chunk['text']}"
            ]
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = model.generate_content(prompt, request_options={"timeout": 600})
                    res_text = response.text.strip()
                    
                    res_text = re.sub(r'^```markdown\s*', '', res_text)
                    res_text = re.sub(r'^```\s*', '', res_text)
                    res_text = re.sub(r'\s*```$', '', res_text)
                    
                    results_cache[bid] = res_text.strip()
                    save_checkpoint(results_cache, checkpoint_file)
                    write_full_file(output_file, chunks, results_cache)
                    print(f"✅ 页码 <{bid}> 处理并同步成功！")
                    
                    time.sleep(1.5)
                    break
                except Exception as e:
                    print(f"⚠️ 页码 <{bid}> 第 {attempt+1} 次失败: {e}")
                    if attempt == max_retries - 1:
                        print(f"❌ 彻底失败，将跳过。")
                    else:
                        time.sleep(5)

    pdf_doc.close()
    print("\n🎉 处理任务结束。未成功的区块可在下次运行时重试。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Motor Workspace Markdown with Gemini Vision")
    
    parser.add_argument("input_md", help="人工预处理后的 Markdown workspace 文件")
    parser.add_argument("pdf_file", help="原始整本教材的 PDF 文件")
    parser.add_argument("-o", "--output", default=None, help="输出清洗后的 Markdown 文件")
    parser.add_argument("--offset", type=int, default=0, help="PDF物理页与印刷页码的差值")
    parser.add_argument("--checkpoint", default=None, help="指定 checkpoint 文件的名称")
    
    args = parser.parse_args()
    
    base_name = os.path.splitext(os.path.basename(args.input_md))[0]
    output_file = args.output if args.output else f"{base_name}_reworked.md"
    checkpoint_file = args.checkpoint if args.checkpoint else f"{base_name}_checkpoint.json"
    
    process_document(args.input_md, args.pdf_file, output_file, checkpoint_file, args.offset)
