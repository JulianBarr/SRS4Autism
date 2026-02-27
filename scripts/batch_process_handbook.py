import os
import json
import time
import google.generativeai as genai
from PIL import Image

# ==========================================
# 1. 网络代理与 API 配置
# ==========================================
os.environ["HTTP_PROXY"] = "socks5://127.0.0.1:49682"
os.environ["HTTPS_PROXY"] = "socks5://127.0.0.1:49682"

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 GEMINI_API_KEY，请先在终端运行 export GEMINI_API_KEY='你的key'")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3-pro-preview')

# ==========================================
# 2. 目录配置
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, "data_prep", "QCQ_handbook")
OUTPUT_DIR = os.path.join(BASE_DIR, "data_prep", "extracted_json")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ==========================================
# 3. 核心 Prompt
# ==========================================
SYSTEM_PROMPT = """
你是一个顶级的特殊教育数据结构化专家。
我将给你发送《孤独症儿童训练指南》的扫描页。请仔细阅读图片，提取其中的训练目标，并将其严格转换为 JSON 格式。
必须且只能返回合法的 JSON 对象。不要包含 ```json 标签，直接返回 JSON 文本本身。

JSON 结构必须严格遵循以下 Schema：
{
  "domain": "提取所属的领域，如 '认知发展', 如果本页没有写，可留空",
  "age_range": "提取适用的年龄段，如 '2-3岁', 如果本页没有写，可留空",
  "macro_objective": "提取当前页面的大标题或主目标名称",
  "quests": [
    {
      "quest_name": "提取具体的训练项目名称或步骤",
      "materials": ["提取或推测需要的教具"],
      "teaching_steps": "仅提取【教学步骤】或核心的操作指南（极其重要）",
      "group_class_generalization": "仅提取【小组课】中的建议或内容，如果没有则填 null",
      "home_generalization": "仅提取【家庭泛化】中的建议或内容，如果没有则填 null"
    }
  ]
}
"""

def process_image(image_path, filename, max_retries=3):
    output_file = os.path.join(OUTPUT_DIR, f"{os.path.splitext(filename)[0]}.json")
    
    # 🌟 1. Checkpoint: 如果文件已存在，直接跳过
    if os.path.exists(output_file):
        print(f"⏩ {filename} 已存在，跳过...")
        return

    print(f"👀 正在让 Gemini Pro 解析缺失的: {filename} ...")
    
    # 🌟 2. Auto-Retry: 自动重试机制
    for attempt in range(max_retries):
        try:
            img = Image.open(image_path)
            response = model.generate_content(
                [SYSTEM_PROMPT, img],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1 
                )
            )
            
            json_data = response.text
            parsed_json = json.loads(json_data)
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(parsed_json, f, ensure_ascii=False, indent=2)
                
            print(f"✅ 提取成功，已保存至: {output_file}")
            return  # 成功后直接退出重试循环
            
        except json.JSONDecodeError:
            print(f"❌ 解析 {filename} 时 JSON 格式错误。")
            break  # JSON 格式错误通常是模型幻觉，重试意义不大，直接跳出
            
        except Exception as e:
            print(f"⚠️ 第 {attempt + 1} 次尝试失败 ({filename}): 网络超时或被拒绝")
            if attempt < max_retries - 1:
                sleep_time = 5 * (attempt + 1)  # 阶梯式等待: 5秒, 10秒...
                print(f"⏳ 等待 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
            else:
                print(f"❌ {filename} 连续 {max_retries} 次失败，请检查网络。")

# ==========================================
# 4. 执行批量处理
# ==========================================
def main():
    if not os.path.exists(INPUT_DIR):
        print(f"❌ 找不到图片目录: {INPUT_DIR}")
        return

    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    images = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(valid_extensions)]
    
    print(f"🚀 启动查漏补缺模式，共 {len(images)} 张图片待检查...")
    
    for filename in sorted(images):
        image_path = os.path.join(INPUT_DIR, filename)
        process_image(image_path, filename)
        time.sleep(2)  # 每次请求间隔2秒，保护 API 额度

if __name__ == "__main__":
    main()
