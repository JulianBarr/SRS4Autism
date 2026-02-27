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
    )
    return run_targeted_scheduler, record_feedback, format_pep3_short, format_materials


class RecordFeedbackBody(BaseModel):
    child_name: str
    quest_id: str
    prompt_level: str


@router.get("/daily_quests")
def get_daily_quests(child_name: str = "小明", count: int = 3):
    """获取今日靶向任务课表。默认 3 个任务，可通过 count 参数自定义数量。"""
    run_targeted_scheduler, _, format_pep3_short, format_materials = _import_scheduler()
    target_date = datetime.now(timezone.utc)
    count = max(1, min(count, 20))  # Clamp 1–20

    try:
        selected_quests, weakest = run_targeted_scheduler(
            child_name=child_name,
            target_date=target_date,
            count=count,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    quests = []
    for item in selected_quests:
        q = item["quest"]
        quests.append({
            "quest_id": q["quest_id"],
            "label": q["label"],
            "pep3_standard": format_pep3_short(q),
            "suggested_materials": format_materials(q),
            "teaching_steps": q.get("teaching_steps"),
            "group_class_generalization": q.get("group_class_generalization"),
            "home_generalization": q.get("home_generalization"),
        })

    weakest_info = None
    if weakest:
        domain_code, domain_name, age_months = weakest
        weakest_info = {
            "domain_code": domain_code,
            "domain_name": domain_name,
            "age_months": age_months,
        }

    return {
        "quests": quests,
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

    _, record_feedback, _, _ = _import_scheduler()

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
