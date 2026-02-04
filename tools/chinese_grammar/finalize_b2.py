import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
APPROVED_FILE = BASE_DIR / "grammar_approved.json"
STAGING_FILE = BASE_DIR / "grammar_staging.json"

def finalize_b2():
    if not STAGING_FILE.exists() or not APPROVED_FILE.exists():
        print("❌ Files missing.")
        return

    # 1. 读取 Approved (此时应该是 A1+A2+B1)
    with open(APPROVED_FILE, 'r', encoding='utf-8') as f:
        approved_data = json.load(f)
    
    # 建立现有 ID 集合，防止重复
    existing_ids = {item['id'] for item in approved_data}

    # 2. 读取 Staging (寻找 B2 数据)
    with open(STAGING_FILE, 'r', encoding='utf-8') as f:
        staging_data = json.load(f)

    new_b2_count = 0
    
    for item in staging_data:
        # 识别 B2 数据的特征：
        # 1. 有明确的 level="B2"
        # 2. 或者状态是 "approved" 但不在 existing_ids 里
        # 3. 这里的逻辑是：只要是新批准的，且 ID 冲突或者是新的 B2，就处理
        
        is_b2 = item.get('level') == 'B2'
        # 如果没有 level 字段，也可以根据 summary_cn 或其他特征判断，这里假设您之前的步骤加了 level
        
        if is_b2:
            # 关键：如果 ID 只是 'pdf_0'，会和 B1 的 'pdf_0' 冲突！
            # 我们强制重命名 ID
            old_id = item.get('id', 'unknown')
            
            # 如果 ID 还没改过名 (不包含 b2 标记)
            if 'b2' not in str(old_id):
                # 提取数字后缀 (假设格式是 pdf_123)
                suffix = old_id.split('_')[-1] if '_' in str(old_id) else str(new_b2_count)
                new_id = f"pdf_b2_{suffix}"
                item['id'] = new_id
            
            # 确保它还没被加进去
            if item['id'] not in existing_ids:
                approved_data.append(item)
                existing_ids.add(item['id'])
                new_b2_count += 1

    # 3. 保存
    with open(APPROVED_FILE, 'w', encoding='utf-8') as f:
        json.dump(approved_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Successfully added {new_b2_count} new B2 items to approved list.")
    print(f"📊 New Total: {len(approved_data)}")

if __name__ == "__main__":
    finalize_b2()
