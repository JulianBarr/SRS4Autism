import os
import sys

# 把项目根目录加到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scripts.data_extraction.heep_hong_extractor import HeepHongOntologyExtractor
import json

from dotenv import load_dotenv
load_dotenv() # 尝试加载 .env
# load_dotenv("gemini.env") # 根据您的环境配置取消注释


def run_test():
    extractor = HeepHongOntologyExtractor() 

    # 把你从 Markdown 里复制出来的那一小节贴在这里
    test_markdown_chunk = """
    ## 发声能力

    1. 会发出 2 个至 3 个不同的母音（如：a, o, e, i, u）。 (0岁 - 1岁)
    训练目标：能够发出不同的母音。
    训练方法：
    - 家长可以模仿各种动物的叫声（如：猫叫“喵”、狗叫“汪”），鼓励孩子模仿。
    - 用手指着自己的嘴型，夸张地发出母音，让孩子看着并模仿。

    2. 会发出 2 个至 3 个不同的子音（如：b, p, m, d, t, n, l, g, k, h）。 (1岁 - 2岁)
    训练目标：能够发出不同的子音。
    训练方法：
    - 与孩子玩“吹泡泡”游戏，在吹泡泡时发出“噗”、“波”等声音。
    - 模仿汽车的喇叭声“哔哔”，或火车的“哐哐”声。
    """

    print("正在呼叫大模型进行结构化提取...")
    result = extractor.extract_from_text(
        text_chunk=test_markdown_chunk, 
        current_path="语言 -> 语言表达 -> 发声能力" # 手动设定当前切片的绝对路径
    )

    if result["valid"]:
        print("✅ 提取并校验成功！生成的 JSON 如下：")
        print(json.dumps(result["data"], indent=2, ensure_ascii=False))
    else:
        print(f"❌ 提取失败或校验不通过: {result['errors']}")
        # 即使失败也打印出原始输出方便调试
        print("原始输出：")
        print(result.get("raw_output", "无"))

if __name__ == "__main__":
    run_test()
