#!/usr/bin/env python3
"""
CUMA (Lingxi) Daily Scheduler - FSRS 调度引擎概念验证版

核心逻辑：
1. 从 quest_full.ttl 读取 ECTA 认知任务池（Level 3 任务）
2. 特教反馈映射：全辅助→Again, 部分辅助→Hard, 独立完成→Good
3. 使用 FSRS 算法计算 due_date，每日推送最需复习的任务

用法：
    # 生成每日任务（默认）
    python scripts/daily_scheduler.py [--child 小明] [--date 2026-02-26] [--count 3]

    # 记录家长反馈
    python scripts/daily_scheduler.py record <quest_id> <全辅助|部分辅助|独立完成> [--child 小明]

依赖：pip install fsrs rdflib
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# Level 3 任务显示名称（quest_full.ttl 中 phase 无 rdfs:label 时的回退）
TASK_LABELS: dict[str, str] = {
    "task_count_1_2": "数数 1-2",
    "task_match_num_1_5": "数字配数字(1-5)",
    "task_color_match_identical": "颜色配对 (基础)",
    "task_color_match_distractor": "抗干扰颜色配对",
}

# 建议环境（来自 cognitionQuestService，后续可从 KG 读取）
TASK_ENVIRONMENTS: dict[str, str] = {
    "task_count_1_2": "桌面结构化；居家自然 (洗手液挤两下)",
    "task_match_num_1_5": "桌面结构化；居家自然 (看病拿号排队)",
    "task_color_match_identical": "桌面结构化",
    "task_color_match_distractor": "桌面结构化",
}


def load_graph():
    """加载 ECTA + PEP-3 知识图谱并执行对齐。"""
    from rdflib import Graph, Namespace

    g = Graph()
    quest_path = BASE_DIR / "knowledge_graph" / "quest_full.ttl"
    pep3_path = BASE_DIR / "knowledge_graph" / "pep3_master.ttl"

    if not quest_path.exists():
        raise FileNotFoundError(f"找不到 quest_full.ttl: {quest_path}")

    g.parse(str(quest_path), format="turtle")
    g.parse(str(pep3_path), format="turtle")

    # 对齐规则（与 align_pep3.py 一致）
    ECTA_INST = Namespace("http://ecta.ai/instance/")
    ECTA_KG = Namespace("http://ecta.ai/schema/")
    PEP3_INST = Namespace("http://ecta.ai/pep3/instance/")

    g.add((ECTA_INST.obj_cog_032, ECTA_KG.alignsWithStandard, PEP3_INST.item_105))
    g.add((ECTA_INST.obj_cog_032, ECTA_KG.alignsWithStandard, PEP3_INST.item_108))
    g.add((ECTA_INST.obj_cog_044, ECTA_KG.alignsWithStandard, PEP3_INST.item_101))
    g.add((ECTA_INST.obj_cog_044, ECTA_KG.alignsWithStandard, PEP3_INST.item_102))

    return g


def get_quest_pool(graph) -> list[dict]:
    """
    从图谱中提取 Level 3 任务池，含 PEP-3 对齐信息。
    返回: [{quest_id, label, pep3_items, macro_label}, ...]
    """
    sparql = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX ecta-kg: <http://ecta.ai/schema/>
    PREFIX ecta-inst: <http://ecta.ai/instance/>

    SELECT ?phase ?macro ?macroLabel ?pep3Label
    WHERE {
        ?macro ecta-kg:hasPhase ?phase ;
               rdfs:label ?macroLabel .
        OPTIONAL {
            ?macro ecta-kg:alignsWithStandard ?pep3Item .
            ?pep3Item rdfs:label ?pep3Label .
        }
    }
    """
    results = list(graph.query(sparql))

    # 按 phase 聚合 PEP-3 项
    phase_to_pep3: dict[str, list[str]] = {}
    phase_to_macro: dict[str, tuple[str, str]] = {}

    for row in results:
        phase_uri = str(row.phase)
        phase_id = phase_uri.split("/")[-1] if "/" in phase_uri else phase_uri
        macro_label = str(row.macroLabel) if row.macroLabel else ""
        pep3_label = str(row.pep3Label) if row.pep3Label else ""

        phase_to_macro[phase_id] = (macro_label, phase_id)
        if phase_id not in phase_to_pep3:
            phase_to_pep3[phase_id] = []
        if pep3_label:
            phase_to_pep3[phase_id].append(pep3_label)

    quests = []
    seen = set()
    for phase_id, (macro_label, _) in phase_to_macro.items():
        if phase_id in seen:
            continue
        seen.add(phase_id)
        label = TASK_LABELS.get(phase_id, macro_label or phase_id)
        env = TASK_ENVIRONMENTS.get(phase_id, "")
        pep3_items = phase_to_pep3.get(phase_id, [])

        quests.append({
            "quest_id": phase_id,
            "label": label,
            "macro_label": macro_label,
            "pep3_items": pep3_items,
            "environment": env,
        })

    return quests


def get_child_profile_path(child_name: str) -> Path:
    """儿童档案路径。"""
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
    """
    特教辅助层级 → FSRS Rating 映射（The Magic Mapping）
    全辅助 → Again(1), 部分辅助 → Hard(2), 独立完成 → Good(3)
    """
    mapping = {
        "全辅助": 1,  # Rating.Again
        "部分辅助": 2,  # Rating.Hard
        "独立完成": 3,  # Rating.Good
    }
    return mapping.get(prompt_level, 3)


def run_scheduler(child_name: str, target_date: datetime, count: int = 3) -> list[dict]:
    """
    运行 FSRS 调度，返回当日应完成的 quest 列表。
    """
    from fsrs import FSRS, Card

    graph = load_graph()
    quest_pool = get_quest_pool(graph)
    profile = load_child_profile(child_name)
    scheduler = FSRS()

    now = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    now_utc = now.astimezone(timezone.utc)

    quest_cards = profile.get("quest_cards", {})
    due_quests: list[tuple[datetime, dict, Card | None]] = []

    for quest in quest_pool:
        qid = quest["quest_id"]
        card_data = quest_cards.get(qid)

        if card_data:
            card = Card.from_dict(card_data)
            due = card.due
            if due and due.astimezone(now_utc.tzinfo) <= now_utc + timedelta(days=1):
                due_quests.append((due, quest, card))
            elif due:
                due_quests.append((due, quest, card))
        else:
            # 新任务：due 为现在，应优先安排
            card = Card()
            due_quests.append((now_utc, quest, card))

    # 按 due 时间排序，取最紧急的 count 个
    due_quests.sort(key=lambda x: x[0])
    selected = due_quests[:count]

    return [{"quest": q, "card": c, "due": d} for d, q, c in selected]


def print_daily_quests(child_name: str, target_date: datetime, count: int = 3) -> None:
    """在终端打印每日任务。"""
    results = run_scheduler(child_name, target_date, count)
    date_str = target_date.strftime("%Y-%m-%d")

    print()
    print("=" * 64)
    print(f"📅 今天是 {date_str}，{child_name} 的 Daily Quests：")
    print("=" * 64)

    for i, item in enumerate(results, 1):
        quest = item["quest"]
        pep3_str = "、".join(quest["pep3_items"]) if quest["pep3_items"] else "—"
        env = quest.get("environment", "")
        # PEP-3 题号简写（如 "105. 颜色配对" -> "105题"）
        pep3_short = "、".join(
            p.split(".")[0].strip() + "题" for p in quest["pep3_items"] if "." in str(p)
        ) or pep3_str

        print(f"\n{i}. [认知] {quest['label']} —— 🎯 支撑 PEP-3 {pep3_short}")
        if env:
            print(f"   ↳ 建议环境：{env}")

    print("\n" + "=" * 64)
    print("💡 家长反馈后，系统将映射为 FSRS 评级并更新下次复习时间。")
    print("=" * 64 + "\n")


def record_feedback(child_name: str, quest_id: str, prompt_level: str) -> None:
    """
    记录家长反馈并更新 FSRS 状态（供后续扩展）。
    全辅助→Again, 部分辅助→Hard, 独立完成→Good
    """
    from fsrs import FSRS, Card, Rating

    profile = load_child_profile(child_name)
    quest_cards = profile.setdefault("quest_cards", {})
    scheduler = FSRS()

    card_data = quest_cards.get(quest_id)
    card = Card.from_dict(card_data) if card_data else Card()

    rating_val = prompt_level_to_fsrs_rating(prompt_level)
    rating = Rating(rating_val)

    new_card, _ = scheduler.review_card(card, rating)
    quest_cards[quest_id] = new_card.to_dict()
    profile["quest_cards"] = quest_cards
    save_child_profile(child_name, profile)
    print(f"✅ 已记录：{quest_id} → {prompt_level} (FSRS {rating_val})")


def main() -> None:
    parser = argparse.ArgumentParser(description="CUMA 每日任务调度器 (FSRS 概念验证)")
    parser.add_argument("--child", default="小明", help="儿童姓名")
    parser.add_argument("--date", default=None, help="目标日期 YYYY-MM-DD")
    parser.add_argument("--count", type=int, default=3, help="每日任务数量")
    subparsers = parser.add_subparsers(dest="cmd", help="子命令")

    # schedule: 生成每日任务 (默认，可不写)
    subparsers.add_parser("schedule", help="生成每日任务 (默认)")

    # record: 记录家长反馈
    sp_record = subparsers.add_parser("record", help="记录家长反馈")
    sp_record.add_argument("quest_id", help="任务 ID，如 task_count_1_2")
    sp_record.add_argument(
        "prompt_level",
        choices=["全辅助", "部分辅助", "独立完成"],
        help="家长反馈的辅助层级",
    )

    args = parser.parse_args()
    # 无子命令时默认 schedule
    if args.cmd is None:
        target = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()
        print_daily_quests(args.child, target, args.count)
    elif args.cmd == "schedule":
        target = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()
        print_daily_quests(args.child, target, args.count)
    elif args.cmd == "record":
        record_feedback(args.child, args.quest_id, args.prompt_level)


if __name__ == "__main__":
    main()
