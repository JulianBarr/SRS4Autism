import glob
import json
import opencc
import os

print("🚀 启动全量繁转简清洗流水线...")

# 初始化繁转简转换器
converter = opencc.OpenCC('t2s.json')

# 抓取所有本体文件（排除已经转过的，防止重复嵌套）
target_files = [f for f in glob.glob("*_ontology.json") if "_zh_CN" not in f]

for input_file in target_files:
    output_file = input_file.replace(".json", "_zh_CN.json")
    print(f"🔄 正在转换: {input_file} ...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_text = f.read()
        
    simplified_text = converter.convert(raw_text)
    
    # 验证并保存
    try:
        data = json.loads(simplified_text)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 完成 -> {output_file}")
    except json.JSONDecodeError as e:
        print(f"   ❌ 转换失败，JSON 格式受损: {e}")

print("🎉 六大领域全量繁转简完毕！")
