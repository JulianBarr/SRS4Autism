import google.generativeai as genai
import os
import time
import json
from pypdf import PdfReader, PdfWriter

# --- 基础配置 ---
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model_name = "gemini-3.1-pro-preview" 

# 🎯 请在此修改为你那本全书的文件名
pdf_path = "21-学前儿童训练指南（语言）—协康会_sample.pdf" 
checkpoint_file = "extraction_progress.json"
output_file = "final_book_ontology.json"

# 为了绝对稳定性，全书模式建议 1 页 1 吞，彻底杜绝 504 报错
CHUNK_SIZE = 1 

# --- 核心逻辑 ---
reader = PdfReader(pdf_path)
total_pages = len(reader.pages)

# 1. 加载断点
processed_data = []
last_processed_page = -1

if os.path.exists(checkpoint_file):
    with open(checkpoint_file, "r", encoding="utf-8") as f:
        checkpoint_data = json.load(f)
        processed_data = checkpoint_data.get("nodes", [])
        last_processed_page = checkpoint_data.get("last_page", -1)
    print(f"♻️ 发现断点：已处理至第 {last_processed_page + 1} 页，已捕获 {len(processed_data)} 个节点。")
else:
    print(f"🚀 开始全新任务：共 {total_pages} 页。")

# 2. 定义 Prompt
prompt = """
你是顶级特殊教育专家。阅读 PDF 扫描件片段，提取训练目标和活动建议。
即便这一页是目录或简介，也请提取出 L1/L2/L3 的层级框架。

【JSON 结构】
- name: 节点名称 (统一使用繁体中文)
- level: L1/L2/L3/L4/L5/L6
- parent_name: 父节点名称 (顶级为 null)
- age_min_months / age_max_months: 整数或 null
- prompt_corpus: 完整活动详情描述

必须输出纯 JSON 数组，严禁任何解释性文字。
"""

model = genai.GenerativeModel(
    model_name=model_name,
    generation_config={"response_mime_type": "application/json"}
)

# 3. 循环处理
# 从断点的下一页开始
start_idx = last_processed_page + 1

for i in range(start_idx, total_pages, CHUNK_SIZE):
    end_idx = min(i + CHUNK_SIZE, total_pages)
    print(f"\n[进度 {end_idx}/{total_pages}] 正在炼金: 第 {i+1} - {end_idx} 页...")
    
    # 切片
    writer = PdfWriter()
    for page_num in range(i, end_idx):
        writer.add_page(reader.pages[page_num])
    
    tmp_pdf = f"tmp_processing.pdf"
    with open(tmp_pdf, "wb") as f:
        writer.write(f)
        
    try:
        # 上传并等待
        sample_file = genai.upload_file(path=tmp_pdf)
        while sample_file.state.name == 'PROCESSING':
            time.sleep(2)
            sample_file = genai.get_file(sample_file.name)
            
        # 推理
        response = model.generate_content([prompt, sample_file], request_options={"timeout": 300})
        chunk_nodes = json.loads(response.text)
        
        if isinstance(chunk_nodes, list):
            processed_data.extend(chunk_nodes)
            print(f"✅ 成功：捕获 {len(chunk_nodes)} 个节点。")
        
        # 💾 立即保存断点（关键步骤）
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump({
                "last_page": end_idx - 1,
                "nodes": processed_data
            }, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"❌ 警告：第 {i+1} 页处理失败: {e}")
        print("程序将暂停 10 秒后尝试下一页。您可以随时 Ctrl+C 停止，下次运行会自动重试失败页。")
        time.sleep(10)
    finally:
        if 'sample_file' in locals():
            genai.delete_file(sample_file.name)
        if os.path.exists(tmp_pdf):
            os.remove(tmp_pdf)

# 4. 导出最终结果
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(processed_data, f, indent=2, ensure_ascii=False)

print(f"\n🏆 全书炼金圆满完成！总计 {len(processed_data)} 个节点。")
print(f"最终产物已存入: {output_file}")
