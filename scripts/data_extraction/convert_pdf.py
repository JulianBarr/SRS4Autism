import google.generativeai as genai
import os
import time
import json
from pypdf import PdfReader, PdfWriter

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# 🎯 换回主公指定的 3.1 预览版，视觉能力最强
model_name = "gemini-3.1-pro-preview" 

pdf_path = "21-学前儿童训练指南（语言）—协康会_sample.pdf"
chunk_size = 3 

reader = PdfReader(pdf_path)
total_pages = len(reader.pages)
print(f"📊 启动 CUMA 视觉提炼流水线。总页数: {total_pages}，模型: {model_name}")

# 🚀 优化 Prompt：让它不要轻易放弃任何一页，尽量挖掘层级关系
prompt = """
你是顶级特殊教育专家。阅读 PDF 扫描件，提取训练目标和活动建议。
即便这一页是目录或简介，也请提取出 L1/L2/L3 的层级框架，这对构建完整图谱至关重要。

【JSON 结构】
- name: 节点名称
- level: L1(次范畴)/L2(学习重点)/L3(项目)/L4(里程碑)/L5(活动建议)/L6(材料)
- parent_name: 父节点名称 (顶级为 null)
- age_min_months / age_max_months: 整数或 null
- prompt_corpus: 活动详情

必须输出纯 JSON 数组。不要包含任何 Markdown 标签或解释文字。
"""

model = genai.GenerativeModel(
    model_name=model_name,
    generation_config={"response_mime_type": "application/json"}
)

master_json_list = []

for start_page in range(0, total_pages, chunk_size):
    end_page = min(start_page + chunk_size, total_pages)
    print(f"\n🔍 处理中: 第 {start_page + 1}-{end_page} 页...")
    
    writer = PdfWriter()
    for i in range(start_page, end_page):
        writer.add_page(reader.pages[i])
        
    chunk_filename = f"temp_chunk.pdf"
    with open(chunk_filename, "wb") as f:
        writer.write(f)
        
    try:
        sample_file = genai.upload_file(path=chunk_filename)
        while sample_file.state.name == 'PROCESSING':
            time.sleep(2)
            sample_file = genai.get_file(sample_file.name)
            
        # 🎯 增加 timeout 保证长 JSON 不被掐断
        response = model.generate_content([prompt, sample_file], request_options={"timeout": 300})
        
        # 🎯 健壮的 JSON 解析：直接解析 text，不带任何切割逻辑
        chunk_data = json.loads(response.text)
        
        if isinstance(chunk_data, list):
            print(f"✅ 捕获到 {len(chunk_data)} 个节点")
            master_json_list.extend(chunk_data)
        else:
            print("⚠️ 模型返回了非数组格式，跳过本块")
        
    except Exception as e:
        print(f"❌ 出错: {e}")
    finally:
        if 'sample_file' in locals():
            genai.delete_file(sample_file.name)
        if os.path.exists(chunk_filename):
            os.remove(chunk_filename)

# 保存总表
with open("vision_ontology_result_final.json", "w", encoding="utf-8") as f:
    json.dump(master_json_list, f, indent=2, ensure_ascii=False)

print(f"\n🏆 炼金完成！总计获得 {len(master_json_list)} 个知识节点。文件: vision_ontology_result_final.json")
