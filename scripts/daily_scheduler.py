#!/usr/bin/env python3
"""
CUMA (Lingxi) Daily Scheduler - 基于 PEP-3 短板靶向推送的智能调度器

核心逻辑：
1. 从 SQLite profiles 表读取 extracted_data，解析 pep3_baseline，找出最短板领域
2. 跨图谱 SPARQL 查询：命中该领域的 PhasalObjective 任务作为靶向候选池
3. 结合 FSRS 记忆状态，优先推送到期或未做过的靶向任务

用法：
    # 生成每日靶向任务（默认）
    python scripts/daily_scheduler.py [--child 小明] [--date 2026-02-27] [--count 3]

    # 记录家长反馈
    python scripts/daily_scheduler.py record <quest_id> <全辅助|部分辅助|独立完成> [--child 小明]

依赖：pip install fsrs rdflib
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta

# rdflib SPARQL parser 非线程安全 (RDFLib/rdflib#765)，需串行化
_sparql_lock = threading.Lock()
from pathlib import Path
from typing import Optional

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# PEP-3 领域代码 → 图谱 domain URI 后缀 映射
DOMAIN_CODE_TO_URI_SUFFIX: dict[str, str] = {
    "CVP": "domain_cvp",   # 认知(语言/语前)
    "EL": "domain_el",     # 语言表达
    "RL": "domain_rl",     # 语言理解
    "FM": "domain_fm",     # 小肌肉
    "GM": "domain_gm",     # 大肌肉
    "VMI": "domain_vmi",   # 模仿(视觉/动作)
    "AE": "domain_ae",     # 情感表达
    "SR": "domain_sr",     # 社交互动
    "CMB": "domain_cmb",   # 行为特征-非语言
    "CVB": "domain_cvb",   # 行为特征-语言
}


def get_db_path() -> Path:
    """获取 content_db 下的 SQLite 路径（与 backend 配置一致）。"""
    # 优先 content_db，其次 data
    for subdir in ("content_db", ""):
        base = BASE_DIR / "data" / subdir if subdir else BASE_DIR / "data"
        db_path = base / "srs4autism.db"
        if db_path.exists():
            return db_path
    return BASE_DIR / "data" / "content_db" / "srs4autism.db"


def find_child_profile(db_path: Path, child_query: str) -> Optional[tuple[str, str, dict]]:
    """
    从 SQLite 查找儿童档案。支持模糊匹配 name 或精确 id。
    返回: (profile_id, name, extracted_data_dict) 或 None
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, extracted_data FROM profiles WHERE id LIKE ? OR name LIKE ?",
        (f"%{child_query}%", f"%{child_query}%"),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    raw = row["extracted_data"]
    data = json.loads(raw) if raw else {}
    return (row["id"], row["name"], data)


def find_weakest_domain(extracted_data: dict) -> Optional[tuple[str, str, int]]:
    """
    从 extracted_data 解析 pep3_baseline，找出 age_equivalent_months 最低的领域。
    返回: (domain_code, domain_name, age_months) 或 None
    """
    baseline = extracted_data.get("pep3_baseline", {})
    metrics = baseline.get("metrics", {})
    if not metrics:
        return None

    weakest_code: Optional[str] = None
    weakest_name: str = ""
    min_months: int = 9999

    for code, info in metrics.items():
        if not isinstance(info, dict):
            continue
        months = info.get("age_equivalent_months")
        if months is None:
            continue
        try:
            m = int(months) if isinstance(months, (int, float)) else int(float(months))
        except (ValueError, TypeError):
            continue
        name = info.get("domain_name") or code
        if m < min_months:
            min_months = m
            weakest_code = code
            weakest_name = name

    if weakest_code is None:
        return None
    return (weakest_code, weakest_name, min_months)


def load_graph():
    """加载 ECTA + PEP-3 知识图谱。"""
    from rdflib import Graph

    g = Graph()
    quest_path = BASE_DIR / "knowledge_graph" / "quest_full.ttl"
    pep3_path = BASE_DIR / "knowledge_graph" / "pep3_master.ttl"

    if not quest_path.exists():
        raise FileNotFoundError(f"找不到 quest_full.ttl: {quest_path}")
    if not pep3_path.exists():
        raise FileNotFoundError(f"找不到 pep3_master.ttl: {pep3_path}")

    g.parse(str(quest_path), format="turtle")
    g.parse(str(pep3_path), format="turtle")
    return g


def get_targeted_quests(graph, domain_code: str) -> list[dict]:
    """
    跨图谱 SPARQL：查询所有通过 alignsWithStandard 命中该领域的 PhasalObjective 任务。
    返回: [{quest_id, label, pep3_items, pep3_item_nums, suggested_materials}, ...]
    """
    uri_suffix = DOMAIN_CODE_TO_URI_SUFFIX.get(domain_code.upper())
    if not uri_suffix:
        return []

    domain_uri = f"http://ecta.ai/pep3/instance/{uri_suffix}"

    sparql = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX ecta-kg: <http://ecta.ai/schema/>
    PREFIX ecta-inst: <http://ecta.ai/instance/>
    PREFIX pep3: <http://ecta.ai/pep3/schema/>
    PREFIX pep3-inst: <http://ecta.ai/pep3/instance/>

    SELECT ?task ?taskLabel ?pep3Item ?pep3Label ?itemNum ?material
           ?teachingSteps ?groupClassGeneralization ?homeGeneralization ?ecumenicalIntegration
    WHERE {{
        ?task a ecta-kg:PhasalObjective ;
              ecta-kg:alignsWithStandard ?pep3Item ;
              rdfs:label ?taskLabel .
        ?pep3Item pep3:belongsToDomain <{domain_uri}> ;
                  pep3:itemNumber ?itemNum ;
                  rdfs:label ?pep3Label .
        OPTIONAL {{ ?task ecta-kg:suggestedMaterials ?material . }}
        OPTIONAL {{ ?task ecta-kg:teachingSteps ?teachingSteps . }}
        OPTIONAL {{ ?task ecta-kg:groupClassGeneralization ?groupClassGeneralization . }}
        OPTIONAL {{ ?task ecta-kg:homeGeneralization ?homeGeneralization . }}
        OPTIONAL {{ ?task ecta-kg:ecumenicalIntegration ?ecumenicalIntegration . }}
    }}
    """

    with _sparql_lock:
        results = list(graph.query(sparql))

    # 按 task 聚合
    task_data: dict[str, dict] = {}
    for row in results:
        task_uri = str(row.task)
        task_id = task_uri.split("/")[-1] if "/" in task_uri else task_uri
        label = str(row.taskLabel) if row.taskLabel else task_id
        pep3_label = str(row.pep3Label) if row.pep3Label else ""
        item_num = row.itemNum
        material = str(row.material) if row.material else None
        teaching_steps = str(row.teachingSteps) if getattr(row, "teachingSteps", None) else None
        group_class_gen = str(row.groupClassGeneralization) if getattr(row, "groupClassGeneralization", None) else None
        home_gen = str(row.homeGeneralization) if getattr(row, "homeGeneralization", None) else None
        
        raw_integration = str(row.ecumenicalIntegration) if getattr(row, "ecumenicalIntegration", None) else None
        parsed_integration = None
        if raw_integration:
            try:
                # 尝试修复多行字符串导致的 JSON 解析问题
                if '\n' in raw_integration and '\\n' not in raw_integration:
                    raw_integration = raw_integration.replace('\n', '\\n')
                parsed_integration = json.loads(raw_integration)
                # 处理如果解析后还是字符串的情况（双重序列化）
                if isinstance(parsed_integration, str):
                    parsed_integration = json.loads(parsed_integration)
            except Exception as e:
                # print(f"DEBUG: Failed to parse JSON for {task_id}: {e}")
                parsed_integration = None

        if task_id not in task_data:
            task_data[task_id] = {
                "quest_id": task_id,
                "label": label,
                "pep3_items": [],
                "pep3_item_nums": [],
                "suggested_materials": [],
                "teaching_steps": None,
                "group_class_generalization": None,
                "home_generalization": None,
                "ecumenical_integration": None,
            }
        if pep3_label and pep3_label not in task_data[task_id]["pep3_items"]:
            task_data[task_id]["pep3_items"].append(pep3_label)
            if item_num is not None:
                task_data[task_id]["pep3_item_nums"].append(int(item_num))
        if material and material not in task_data[task_id]["suggested_materials"]:
            task_data[task_id]["suggested_materials"].append(material)
        if teaching_steps:
            task_data[task_id]["teaching_steps"] = teaching_steps
        if group_class_gen:
            task_data[task_id]["group_class_generalization"] = group_class_gen
        if home_gen:
            task_data[task_id]["home_generalization"] = home_gen
        if parsed_integration:
            task_data[task_id]["ecumenical_integration"] = parsed_integration

    return list(task_data.values())


def get_child_profile_path(child_name: str) -> Path:
    """儿童 FSRS 状态档案路径。"""
    profiles_dir = BASE_DIR / "data" / "child_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return profiles_dir / f"{child_name}.json"


def load_child_profile(child_name: str) -> dict:
    """加载儿童 FSRS 状态档案。"""
    path = get_child_profile_path(child_name)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"child_name": child_name, "quest_cards": {}, "created_at": datetime.now(timezone.utc).isoformat()}


def save_child_profile(child_name: str, profile: dict) -> None:
    """保存儿童档案。"""
    path = get_child_profile_path(child_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def prompt_level_to_fsrs_rating(prompt_level: str) -> int:
    """特教辅助层级 → FSRS Rating 映射。"""
    mapping = {"全辅助": 1, "部分辅助": 2, "独立完成": 3}
    return mapping.get(prompt_level, 3)


def _parse_due_from_fsrs_state(state: dict) -> Optional[datetime]:
    """从 fsrs_states 中的单条记录解析 due 日期。"""
    due_val = state.get("due")
    if due_val is None:
        return None
    if isinstance(due_val, datetime):
        return due_val
    if isinstance(due_val, str):
        try:
            return datetime.fromisoformat(due_val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_last_review_date(state: dict) -> Optional[datetime]:
    """从 fsrs_states 中的单条记录解析 last_review 日期。"""
    lr_val = state.get("last_review")
    if lr_val is None:
        return None
    if isinstance(lr_val, datetime):
        return lr_val
    if isinstance(lr_val, str):
        try:
            return datetime.fromisoformat(lr_val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def run_targeted_scheduler(
    child_name: str,
    target_date: datetime,
    count: int = 3,
    db_path: Optional[Path] = None,
) -> tuple[dict, Optional[tuple[str, str, int]]]:
    """
    运行靶向调度：找最短板 → SPARQL 靶向任务池 → 严格 FSRS 过滤 → 排序。
    严格从 extracted_data['fsrs_states'] 读取：due > --date 的任务坚决剔除。
    今日已打卡（last_review 日期 == target_date）的任务放入 completed_today；未打卡且到期的放入 pending。
    名额计算：pending 最多 count - len(completed_today) 个。
    返回: ({"pending": [...], "completed_today": [...]}, weakest_domain_info)
    """
    from fsrs import FSRS, Card

    db_path = db_path or get_db_path()
    profile_row = find_child_profile(db_path, child_name)

    weakest: Optional[tuple[str, str, int]] = None
    fsrs_states: dict = {}
    if profile_row:
        _, _, extracted = profile_row
        weakest = find_weakest_domain(extracted)
        fsrs_states = extracted.get("fsrs_states") or {}

    graph = load_graph()

    if weakest:
        domain_code, domain_name, age_months = weakest
        quest_pool = get_targeted_quests(graph, domain_code)
        if not quest_pool:
            quest_pool = _get_fallback_quest_pool(graph)
    else:
        quest_pool = _get_fallback_quest_pool(graph)

    target_date_d = target_date.date()
    target_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    # 严格校验“今天”：使用本地时间的 YYYY-MM-DD，避免将昨天或更早的任务误判为今日已打卡
    today_local_str = datetime.now().strftime("%Y-%m-%d")
    completed_today: list[dict] = []
    pending_unsorted: list[tuple[datetime, dict, Card | None]] = []

    for quest in quest_pool:
        qid = quest["quest_id"]
        card_data = fsrs_states.get(qid)

        if card_data:
            due = _parse_due_from_fsrs_state(card_data)
            if due is not None and due.date() > target_date_d:
                continue
            last_review = _parse_last_review_date(card_data)
            if last_review is not None:
                last_review_local_str = (
                    last_review.astimezone().strftime("%Y-%m-%d")
                    if last_review.tzinfo
                    else last_review.strftime("%Y-%m-%d")
                )
                if last_review_local_str == today_local_str:
                    try:
                        card = Card.from_dict(card_data)
                    except Exception:
                        card = Card()
                    completed_today.append({"quest": quest, "card": card, "due": due or target_dt})
                    continue
            try:
                card = Card.from_dict(card_data)
            except Exception:
                card = Card()
            sort_due = due if due else target_dt
            pending_unsorted.append((sort_due, quest, card))
        else:
            card = Card()
            pending_unsorted.append((target_dt, quest, card))

    def _sort_key(item: tuple) -> float:
        d = item[0]
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()

    pending_unsorted.sort(key=_sort_key)
    quota = max(0, count - len(completed_today))
    selected_pending = pending_unsorted[:quota]
    pending = [{"quest": q, "card": c, "due": d} for d, q, c in selected_pending]

    # 历史打卡任务：last_review 存在且日期 != 今天
    quest_map = {q["quest_id"]: q for q in _get_fallback_quest_pool(graph)}
    history_quests: list[dict] = []
    for qid, card_data in fsrs_states.items():
        last_review = _parse_last_review_date(card_data)
        if last_review is None:
            continue
        last_review_local_str = (
            last_review.astimezone().strftime("%Y-%m-%d")
            if last_review.tzinfo
            else last_review.strftime("%Y-%m-%d")
        )
        if last_review_local_str == today_local_str:
            continue
        quest = quest_map.get(qid) or {"quest_id": qid, "label": qid}
        history_quests.append({"quest": quest, "last_review": last_review})
    history_quests.sort(key=lambda x: x["last_review"].timestamp(), reverse=True)
    history_quests = history_quests[:20]

    return {
        "pending": pending,
        "completed_today": completed_today,
        "history_quests": history_quests,
    }, weakest


def _get_fallback_quest_pool(graph) -> list[dict]:
    """无最短板或靶向池为空时，返回全部有 alignsWithStandard 的任务。"""
    sparql = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX ecta-kg: <http://ecta.ai/schema/>
    PREFIX ecta-inst: <http://ecta.ai/instance/>

    SELECT ?task ?taskLabel ?pep3Label ?material
           ?teachingSteps ?groupClassGeneralization ?homeGeneralization ?ecumenicalIntegration
    WHERE {
        ?task a ecta-kg:PhasalObjective ;
              ecta-kg:alignsWithStandard ?pep3Item ;
              rdfs:label ?taskLabel .
        ?pep3Item rdfs:label ?pep3Label .
        OPTIONAL { ?task ecta-kg:suggestedMaterials ?material . }
        OPTIONAL { ?task ecta-kg:teachingSteps ?teachingSteps . }
        OPTIONAL { ?task ecta-kg:groupClassGeneralization ?groupClassGeneralization . }
        OPTIONAL { ?task ecta-kg:homeGeneralization ?homeGeneralization . }
        OPTIONAL { ?task ecta-kg:ecumenicalIntegration ?ecumenicalIntegration . }
    }
    """
    with _sparql_lock:
        results = list(graph.query(sparql))
    task_data: dict[str, dict] = {}
    for row in results:
        task_uri = str(row.task)
        task_id = task_uri.split("/")[-1] if "/" in task_uri else task_uri
        label = str(row.taskLabel) if row.taskLabel else task_id
        pep3_label = str(row.pep3Label) if row.pep3Label else ""
        material = str(row.material) if row.material else None
        teaching_steps = str(row.teachingSteps) if getattr(row, "teachingSteps", None) else None
        group_class_gen = str(row.groupClassGeneralization) if getattr(row, "groupClassGeneralization", None) else None
        home_gen = str(row.homeGeneralization) if getattr(row, "homeGeneralization", None) else None
        
        raw_integration = str(row.ecumenicalIntegration) if getattr(row, "ecumenicalIntegration", None) else None
        parsed_integration = None
        if raw_integration:
            try:
                # 尝试修复多行字符串导致的 JSON 解析问题
                if '\n' in raw_integration and '\\n' not in raw_integration:
                    raw_integration = raw_integration.replace('\n', '\\n')
                parsed_integration = json.loads(raw_integration)
                # 处理如果解析后还是字符串的情况（双重序列化）
                if isinstance(parsed_integration, str):
                    parsed_integration = json.loads(parsed_integration)
            except Exception as e:
                # print(f"DEBUG: Failed to parse JSON for {task_id}: {e}")
                parsed_integration = None

        if task_id not in task_data:
            task_data[task_id] = {
                "quest_id": task_id,
                "label": label,
                "pep3_items": [],
                "pep3_item_nums": [],
                "suggested_materials": [],
                "teaching_steps": None,
                "group_class_generalization": None,
                "home_generalization": None,
                "ecumenical_integration": None,
            }
        if pep3_label and pep3_label not in task_data[task_id]["pep3_items"]:
            task_data[task_id]["pep3_items"].append(pep3_label)
            if "." in str(pep3_label):
                try:
                    num = int(pep3_label.split(".")[0].strip())
                    task_data[task_id]["pep3_item_nums"].append(num)
                except ValueError:
                    pass
        if material and material not in task_data[task_id]["suggested_materials"]:
            task_data[task_id]["suggested_materials"].append(material)
        if teaching_steps:
            task_data[task_id]["teaching_steps"] = teaching_steps
        if group_class_gen:
            task_data[task_id]["group_class_generalization"] = group_class_gen
        if home_gen:
            task_data[task_id]["home_generalization"] = home_gen
        if parsed_integration:
            task_data[task_id]["ecumenical_integration"] = parsed_integration
    return list(task_data.values())


def format_pep3_short(quest: dict) -> str:
    """生成 PEP-3 题号简写，如 '86题、133题'。"""
    nums = quest.get("pep3_item_nums")
    if nums:
        return "、".join(f"{n}题" for n in sorted(set(nums)))
    items = quest.get("pep3_items", [])
    if items:
        parts = []
        for p in items:
            if "." in str(p):
                parts.append(p.split(".")[0].strip() + "题")
        return "、".join(parts) if parts else "、".join(items)
    return "—"


def format_materials(quest: dict) -> str:
    """格式化推荐教具。"""
    mats = quest.get("suggested_materials", [])
    if mats:
        return "、".join(mats)
    return "利用自然环境"


# ---------------------------------------------------------------------------
# Quest Logs (Topic Chat) - 家校接力沟通记录
# ---------------------------------------------------------------------------


def get_quest_logs(
    child_name: str,
    quest_id: str,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """
    获取某任务的历史沟通日志。
    返回: [{"role": "system|parent|teacher|ai", "content": "...", "timestamp": "..."}, ...]
    """
    db_path = db_path or get_db_path()
    profile_row = find_child_profile(db_path, child_name)
    if not profile_row:
        return []
    _, _, extracted = profile_row
    quest_logs = extracted.get("quest_logs", {})
    return quest_logs.get(quest_id, [])


def append_quest_log(
    child_name: str,
    quest_id: str,
    role: str,
    content: str,
    db_path: Optional[Path] = None,
    file_url: Optional[str] = None,
    file_type: Optional[str] = None,
) -> None:
    """
    向某任务的 quest_logs 追加一条日志。
    role: "system" | "parent" | "teacher" | "ai"
    file_url: 可选，上传文件的相对路径，如 /uploads/xxx.jpg
    file_type: 可选，MIME 类型，如 image/jpeg、video/mp4
    """
    db_path = db_path or get_db_path()
    profile_row = find_child_profile(db_path, child_name)
    if not profile_row:
        raise ValueError(f"找不到儿童档案: {child_name}")

    profile_id, _, extracted = profile_row
    quest_logs = extracted.setdefault("quest_logs", {})
    logs = quest_logs.setdefault(quest_id, [])

    entry: dict = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if file_url:
        entry["file_url"] = file_url
    if file_type:
        entry["file_type"] = file_type
    logs.append(entry)
    quest_logs[quest_id] = logs
    extracted["quest_logs"] = quest_logs

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "UPDATE profiles SET extracted_data = ?, updated_at = ? WHERE id = ?",
        (json.dumps(extracted, ensure_ascii=False), now_str, profile_id),
    )
    conn.commit()
    conn.close()


def print_daily_quests(
    child_name: str,
    target_date: datetime,
    count: int = 3,
    db_path: Optional[Path] = None,
) -> None:
    """在终端打印靶向 Daily Quests。"""
    result, weakest = run_targeted_scheduler(child_name, target_date, count, db_path)
    pending = result["pending"]
    completed_today = result["completed_today"]
    date_str = target_date.strftime("%Y-%m-%d")

    # 解析显示用 child 名称（优先 DB 中的 name）
    db_path = db_path or get_db_path()
    profile_row = find_child_profile(db_path, child_name)
    display_name = profile_row[1] if profile_row else child_name

    print()
    print("=" * 64)
    print(f"📅 今天是 {date_str}，{display_name} 的靶向 Daily Quests：")
    if weakest:
        domain_code, domain_name, age_months = weakest
        print(f"📊 算法诊断：当前最短板为【{domain_name} ({domain_code})】(年龄当量{age_months}个月)，已倾斜推荐权重。")
    else:
        print("📊 算法诊断：未检测到 PEP-3 基线数据，使用全任务池推荐。")
    print("=" * 64)

    for i, item in enumerate(pending, 1):
        quest = item["quest"]
        task_id = quest["quest_id"]
        pep3_short = format_pep3_short(quest)
        materials = format_materials(quest)
        print(f"\n{i}. [待完成] [{task_id}] {quest['label']} —— 🎯 支撑 PEP-3 {pep3_short}")
        print(f"   ↳ 推荐教具：{materials}")
        if quest.get("ecumenical_integration"):
            print("   ↳ 🌟 已融合多源生态教案 (ecumenical_integration)！")

    for i, item in enumerate(completed_today, 1):
        quest = item["quest"]
        task_id = quest["quest_id"]
        pep3_short = format_pep3_short(quest)
        materials = format_materials(quest)
        print(f"\n{i}. [已打卡] [{task_id}] {quest['label']} —— 🎯 支撑 PEP-3 {pep3_short}")
        print(f"   ↳ 推荐教具：{materials}")
        if quest.get("ecumenical_integration"):
            print("   ↳ 🌟 已融合多源生态教案 (ecumenical_integration)！")

    print("\n" + "=" * 64)
    print("💡 家长反馈后，系统将映射为 FSRS 评级并更新下次复习时间。")
    print("=" * 64 + "\n")


def record_feedback(
    child_name: str,
    quest_id: str,
    prompt_level: str,
    db_path: Optional[Path] = None,
) -> None:
    """记录家长反馈并真实更新至 SQLite 数据库的 FSRS 状态中。"""
    from fsrs import FSRS, Card, Rating

    db_path = db_path or get_db_path()
    profile_row = find_child_profile(db_path, child_name)

    if not profile_row:
        raise ValueError(f"找不到儿童档案: {child_name}")

    profile_id, name, extracted = profile_row

    # 获取或初始化数据库中的 fsrs_states
    fsrs_states = extracted.setdefault("fsrs_states", {})
    scheduler = FSRS()

    # 读取卡片历史状态
    card_data = fsrs_states.get(quest_id)
    card = Card.from_dict(card_data) if card_data else Card()

    # FSRS 要求：state != New 时必须有 last_review，否则 review_card 会报错
    if card.state != 0 and not getattr(card, "last_review", None):
        card.last_review = card.due

    # 映射评级并复习
    rating_val = prompt_level_to_fsrs_rating(prompt_level)
    rating = Rating(rating_val)
    new_card, _ = scheduler.review_card(card, rating)

    # 将更新后的卡片存回 extracted_data
    fsrs_states[quest_id] = new_card.to_dict()
    extracted["fsrs_states"] = fsrs_states

    # 自动追加系统打卡日志到 quest_logs（Topic Chat），供家校接力查看
    system_content = f"✅ 打卡完成: {prompt_level}"
    quest_logs = extracted.setdefault("quest_logs", {})
    logs = quest_logs.setdefault(quest_id, [])
    logs.append({
        "role": "system",
        "content": system_content,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    quest_logs[quest_id] = logs
    extracted["quest_logs"] = quest_logs

    # 执行 SQL 真正落盘到数据库（extracted_data 已用 json.loads 解析，修改后用 json.dumps 转回）
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "UPDATE profiles SET extracted_data = ?, updated_at = ? WHERE id = ?",
        (json.dumps(extracted, ensure_ascii=False), now_str, profile_id),
    )
    conn.commit()
    conn.close()

    print(f"✅ 已持久化记录：{quest_id} → {prompt_level} (FSRS {rating_val})")
    due_str = new_card.due.strftime("%Y-%m-%d") if new_card.due else "—"
    print(f"📅 该任务下次复习时间已推迟至: {due_str}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CUMA 靶向每日任务调度器 (PEP-3 短板)")
    parser.add_argument("--child", default="小明", help="儿童姓名或 ID（支持模糊匹配）")
    parser.add_argument("--date", default=None, help="目标日期 YYYY-MM-DD")
    parser.add_argument("--count", type=int, default=3, help="每日任务数量")
    parser.add_argument("--db", default=None, help="SQLite 数据库路径（默认 data/content_db/srs4autism.db）")
    subparsers = parser.add_subparsers(dest="cmd", help="子命令")

    subparsers.add_parser("schedule", help="生成每日靶向任务 (默认)")
    sp_record = subparsers.add_parser("record", help="记录家长反馈")
    sp_record.add_argument("quest_id", help="任务 ID，如 task_1001")
    sp_record.add_argument(
        "prompt_level",
        choices=["全辅助", "部分辅助", "独立完成"],
        help="家长反馈的辅助层级",
    )

    args = parser.parse_args()
    db_path = Path(args.db) if args.db else None

    if args.cmd is None or args.cmd == "schedule":
        target = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()
        print_daily_quests(args.child, target, args.count, db_path)
    elif args.cmd == "record":
        record_feedback(args.child, args.quest_id, args.prompt_level, db_path)


if __name__ == "__main__":
    main()
