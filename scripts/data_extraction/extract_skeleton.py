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

def extract_skeleton(pdf_path, output_json):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return print("❌ Error: 请先设置 GEMINI_API_KEY 环境变量")
    
    genai.configure(api_key=api_key)

    print(f"📄 正在读取目录 PDF: {pdf_path}...")
    toc_images = extract_toc_images(pdf_path)

    system_prompt = """
    你是一个教材结构化专家。你的任务是阅读目录图片，并将其转换为特定的 JSON 结构。
    教材层级如下：
    1. Module (最高层级)
    2. Submodule (次高层级)
    3. Objective (学习重点/项目组)
    4. Phasal Objective (具体的项目，通常带有'项目一'、'项目二'等前缀)

    【🚨 重要强制指令 🚨】
    1. 语言：请将图片中的所有繁体中文全部翻译/转换为 **简体中文** 输出！
    2. 模块名：不管图片上怎么写，请强制将最高层级的 `module` 字段的值设定为 "社交与情绪"。

    请严格按照以下 JSON 格式输出，不要包含任何额外的解释或 Markdown 代码块：
    {
      "module": "社交与情绪",
      "submodules": [
        {
          "title": "次模块名称",
          "objectives": [
            {
              "title": "项目组/重点名称",
              "phasal_objectives": [
                {
                  "index": "项目一",
                  "title": "具体标题名称"
                }
              ]
            }
          ]
        }
      ]
    }
    """

    print("👁️ 正在呼叫 Gemini 3.1 Pro 视觉模型解析目录结构(强制简体版)...")
    model = genai.GenerativeModel(
        model_name='gemini-3.1-pro-preview',
        system_instruction=system_prompt
    )

    prompt_parts = [*toc_images, "请根据这些图片，完整提取目录结构并生成 JSON。记得转成简体中文！"]
    
    generation_config = {
        "response_mime_type": "application/json"
    }

    try:
        response = model.generate_content(prompt_parts, generation_config=generation_config)
        skeleton_data = json.loads(response.text)
        
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(skeleton_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Skeleton JSON 成功生成 (全简体): {output_json}")
        print("🎉 结构化完成！现在你可以运行 generate_workspace.py 了。")
        
    except Exception as e:
        print(f"❌ 解析失败: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Skeleton JSON from TOC PDF via Vision AI")
    parser.add_argument("pdf_file", help="TOC PDF 文件的路径")
    parser.add_argument("-o", "--output", help="输出的 JSON 文件名", default="24-social-emotions_skeleton.json")
    
    args = parser.parse_args()
    extract_skeleton(args.pdf_file, args.output)
