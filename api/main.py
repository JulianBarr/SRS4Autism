"""
CUMA Daily Deck MVP API - 极简靶向任务调度接口

提供每日课表获取与家长反馈记录，对接 scripts/daily_scheduler.py。

运行方式（项目根目录）：
    uvicorn api.main:app --reload --port 8000

或集成到主后端：将本文件中的 router 挂载到 backend/app/main.py。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _import_scheduler():
    """延迟导入，避免启动时加载 rdflib 等重量级依赖。"""
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.daily_scheduler import (
        run_targeted_scheduler,
        record_feedback,
        format_pep3_short,
        format_materials,
    )
    return run_targeted_scheduler, record_feedback, format_pep3_short, format_materials


app = FastAPI(title="CUMA Daily Deck API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class RecordFeedbackBody(BaseModel):
    child_name: str
    quest_id: str
    prompt_level: str  # "全辅助" | "部分辅助" | "独立完成"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/daily_quests")
def get_daily_quests(child_name: str = "小明", count: int = 3):
    """
    获取今日靶向任务课表。
    返回课表数组和诊断信息（最短板领域）。
    """
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

    # 序列化为前端友好格式
    quests = []
    for item in selected_quests:
        q = item["quest"]
        quests.append({
            "quest_id": q["quest_id"],
            "label": q["label"],
            "pep3_standard": format_pep3_short(q),
            "suggested_materials": format_materials(q),
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


@app.post("/api/record_feedback")
def post_record_feedback(body: RecordFeedbackBody):
    """
    记录家长反馈（全辅助 / 部分辅助 / 独立完成），更新 FSRS 状态。
    """
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
