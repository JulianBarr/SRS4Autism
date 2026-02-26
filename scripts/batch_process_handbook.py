import os
import json
import time
import google.generativeai as genai
from PIL import Image

# ==========================================
# 1. 网络代理与 API 配置 (专为国内环境定制)
# ==========================================
# 强制让底层的网络请求走 v2box 的真实端口
os.environ["HTTP_PROXY"] = "socks5://127.0.0.1:49682"
os.environ["HTTPS_PROXY"] = "socks5://127.0.0.1:49682"

# 获取 API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 GEMINI_API_KEY，请先在终端运行 export GEMINI_API_KEY='你的key'")

genai.configure(api_key=api_key)

# ==========================================
# 🚀 切换至 Gemini 最强视觉推理模型 (Pro 系列)
# ==========================================
# 注意：Google API 的模型名称可能随版本迭代变动。
# 目前官方最强的生产级多模态模型通常为 gemini-1.5-pro 
# 如果您的账号已经开通了更高版本的内测权限，可以将其替换为对应的最新模型字符串 (如 gemini-2.0-pro-exp 等)
model = genai.GenerativeModel('gemini-3-pro-image-preview')

# ==========================================
# 2. 目录配置
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, "data_prep", "QCQ_handbook")
#INPUT_DIR = os.path.join(BASE_DIR, "data_prep", "handbook_sample")
OUTPUT_DIR = os.path.join(BASE_DIR, "data_prep", "extracted_json")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ==========================================
# 3. 核心 Prompt：教 Gemini 如何提取特教知识
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

def process_image(image_path, filename):
    print(f"👀 正在让 Gemini Pro 深度解析: {filename} ...")
    
    try:
        # 使用 PIL 打开图片
        img = Image.open(image_path)
        
        # 调用 Gemini Pro API
        response = model.generate_content(
            [SYSTEM_PROMPT, img],
            # 强制模型只返回 JSON 格式
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1 # 保持极低的温度，确保提取内容的严谨性和确定性
            )
        )
        
        # 获取返回的文本 (此时已是纯 JSON 字符串)
        json_data = response.text
        
        # 尝试解析验证一下是否是合法 JSON
        parsed_json = json.loads(json_data)
        
        output_file = os.path.join(OUTPUT_DIR, f"{os.path.splitext(filename)[0]}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            # 格式化并写入文件
            json.dump(parsed_json, f, ensure_ascii=False, indent=2)
            
        print(f"✅ 提取成功，已保存至: {output_file}")
        
    except json.JSONDecodeError:
        print(f"❌ 解析 {filename} 时 JSON 格式错误，模型返回了非标准 JSON。")
        print(f"原始返回内容:\n{json_data}")
    except Exception as e:
        print(f"❌ 处理 {filename} 时网络或接口出错: {str(e)}")

# ==========================================
# 4. 执行批量处理
# ==========================================
def main():
    if not os.path.exists(INPUT_DIR):
        print(f"❌ 找不到图片目录: {INPUT_DIR}")
        return

    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    images = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(valid_extensions)]
    
    print(f"🚀 找到 {len(images)} 张教案照片，准备启动 Gemini Pro 视觉推理引擎...")
    
    for filename in sorted(images):
        image_path = os.path.join(INPUT_DIR, filename)
        process_image(image_path, filename)
        # 稍微停顿一下，防止并发过快触发 API 的速率限制 (Rate Limit)
        time.sleep(3)

if __name__ == "__main__":
    main()
