"""
CUMA Daily Deck API - 靶向任务调度接口
对接 scripts/daily_scheduler.py，供前端 DailyDeck 组件调用。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

router = APIRouter(prefix="/api", tags=["daily-deck"])


def _import_scheduler():
    from scripts.daily_scheduler import (
        run_targeted_scheduler,
        record_feedback,
        format_pep3_short,
        format_materials,
        get_quest_logs,
        append_quest_log,
    )
    return run_targeted_scheduler, record_feedback, format_pep3_short, format_materials, get_quest_logs, append_quest_log


class RecordFeedbackBody(BaseModel):
    child_name: str
    quest_id: str
    prompt_level: str


class QuestLogBody(BaseModel):
    child_name: str
    quest_id: str
    role: str  # "parent" | "teacher" | "ai"
    content: str


def _quest_to_api_item(q: dict, format_pep3_short, format_materials) -> dict:
    """将 quest 转为 API 返回格式。"""
    return {
        "quest_id": q["quest_id"],
        "label": q["label"],
        "pep3_standard": format_pep3_short(q),
        "pep3_items": q.get("pep3_items") or [],
        "suggested_materials": format_materials(q),
        "teaching_steps": q.get("teaching_steps"),
        "group_class_generalization": q.get("group_class_generalization"),
        "home_generalization": q.get("home_generalization"),
    }


@router.get("/daily_quests")
def get_daily_quests(child_name: str = "小明", count: int = 3):
    """获取今日靶向任务课表。默认 3 个任务，可通过 count 参数自定义数量。
    返回 pending（待完成）和 completed_today（今日已打卡）两个列表。"""
    run_targeted_scheduler, _, format_pep3_short, format_materials, _, _ = _import_scheduler()
    target_date = datetime.now(timezone.utc)
    count = max(1, min(count, 20))  # Clamp 1–20

    try:
        result, weakest = run_targeted_scheduler(
            child_name=child_name,
            target_date=target_date,
            count=count,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    pending = [_quest_to_api_item(item["quest"], format_pep3_short, format_materials) for item in result["pending"]]
    completed_today = [
        _quest_to_api_item(item["quest"], format_pep3_short, format_materials)
        for item in result["completed_today"]
    ]

    weakest_info = None
    if weakest:
        domain_code, domain_name, age_months = weakest
        weakest_info = {
            "domain_code": domain_code,
            "domain_name": domain_name,
            "age_months": age_months,
        }

    return {
        "pending": pending,
        "completed_today": completed_today,
        "weakest_domain_info": weakest_info,
    }


@router.post("/record_feedback")
def post_record_feedback(body: RecordFeedbackBody):
    """记录家长反馈。"""
    valid_levels = {"全辅助", "部分辅助", "独立完成"}
    if body.prompt_level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"prompt_level 必须是 {valid_levels} 之一",
        )

    _, record_feedback, _, _, _, _ = _import_scheduler()

    try:
        record_feedback(
            child_name=body.child_name,
            quest_id=body.quest_id,
            prompt_level=body.prompt_level,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success"}


@router.get("/quest_logs")
def get_quest_logs_api(child_name: str, quest_id: str):
    """获取某任务的历史沟通日志（Topic Chat）。"""
    _, _, _, _, get_quest_logs, _ = _import_scheduler()
    try:
        logs = get_quest_logs(child_name=child_name, quest_id=quest_id)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quest_logs")
def post_quest_log(body: QuestLogBody):
    """追加一条沟通日志。role 为 parent / teacher /ai 之一。"""
    valid_roles = {"parent", "teacher", "ai"}
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"role 必须是 {valid_roles} 之一",
        )
    _, _, _, _, _, append_quest_log = _import_scheduler()
    try:
        append_quest_log(
            child_name=body.child_name,
            quest_id=body.quest_id,
            role=body.role,
            content=body.content,
        )
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
