"""
CUMA Daily Deck API - 靶向任务调度接口
对接 scripts/daily_scheduler.py，供前端 DailyDeck 组件调用。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

import uuid
from fastapi import APIRouter, HTTPException, Form, File, UploadFile, Query
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
    file_url: Optional[str] = None
    file_type: Optional[str] = None


def _quest_to_api_item(q: dict, format_pep3_short, format_materials) -> dict:
    """将 quest 转为 API 返回格式。"""
    import json
    raw_integration = q.get("ecumenical_integration")
    parsed_integration = None
    if raw_integration:
        try:
            # 如果已经是字典就不需要再 loads
            if isinstance(raw_integration, str):
                parsed_integration = json.loads(raw_integration)
            elif isinstance(raw_integration, dict):
                parsed_integration = raw_integration
        except Exception:
            parsed_integration = None

    raw_materials = q.get("suggested_materials")
    if isinstance(raw_materials, list):
        suggested_materials = [str(v).strip() for v in raw_materials if str(v).strip()]
    elif isinstance(raw_materials, str) and raw_materials.strip():
        suggested_materials = [raw_materials.strip()]
    else:
        formatted = format_materials(q)
        suggested_materials = [formatted] if formatted else []

    item = {
        "quest_id": q["quest_id"],
        "label": q["label"],
        "pep3_standard": format_pep3_short(q),
        "pep3_items": q.get("pep3_items") or [],
        "suggested_materials": suggested_materials,
        "teaching_steps": q.get("teaching_steps"),
        "group_class_generalization": q.get("group_class_generalization"),
        "home_generalization": q.get("home_generalization"),
        "ecumenical_integration": parsed_integration,
        "activities": q.get("activities") or [],
        "precautions": q.get("precautions") or [],
        "source": "hhs" if q.get("content_source") == "HHS" else "qcq",
    }
    if q.get("content_source") == "HHS":
        item["content_source"] = "HHS"
        item["hhs_module"] = q.get("hhs_module")
        item["age_group"] = q.get("age_group")
    return item


@router.get("/daily_quests")
def get_daily_quests(
    child_name: str = "小明",
    count: int = 3,
    source: str = Query(
        "qcq",
        description="任务池：qcq=仅 ECTA/QCQ 手册；hhs=仅 Heep Hong；mixed=两者合并",
    ),
):
    """获取今日靶向任务课表。默认 3 个任务，可通过 count 参数自定义数量。
    返回 pending（待完成）和 completed_today（今日已打卡）两个列表。"""
    run_targeted_scheduler, _, format_pep3_short, format_materials, _, _ = _import_scheduler()
    target_date = datetime.now(timezone.utc)
    count = max(1, min(count, 20))  # Clamp 1–20

    src = (source or "qcq").strip().lower()
    if src not in ("qcq", "hhs", "mixed"):
        src = "qcq"

    try:
        result, weakest = run_targeted_scheduler(
            child_name=child_name,
            target_date=target_date,
            count=count,
            schedule_source=src,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    pending = [_quest_to_api_item(item["quest"], format_pep3_short, format_materials) for item in result["pending"]]
    
    # Insert custom quests from drafts
    try:
        import json
        import os
        custom_quests_file = os.path.join(os.path.dirname(__file__), "../../../data/custom_quests.json")
        if os.path.exists(custom_quests_file):
            with open(custom_quests_file, 'r', encoding='utf-8') as f:
                custom_quests = json.load(f)
                
            existing_quest_ids = {item["quest"]["quest_id"] for item in result["pending"]} | \
                                 {item["quest"]["quest_id"] for item in result["completed_today"]}
            seen_custom_signatures = set()
            for q in custom_quests:
                # Child-scoped custom quests only
                q_child_name = str(q.get("child_name") or "")
                # Legacy custom quests without child_name are kept visible for cleanup.
                if q_child_name and q_child_name != str(child_name):
                    continue

                signature = (
                    str(q.get("label") or "").strip(),
                    str(q.get("teaching_steps") or "").strip(),
                )
                if signature in seen_custom_signatures:
                    continue
                seen_custom_signatures.add(signature)

                if q["quest_id"] not in existing_quest_ids:
                    pending.insert(0, q)
    except Exception as e:
        print(f"Error loading custom quests: {e}")

    completed_today = [
        _quest_to_api_item(item["quest"], format_pep3_short, format_materials)
        for item in result["completed_today"]
    ]
    history_quests = [
        {
            "quest": _quest_to_api_item(item["quest"], format_pep3_short, format_materials),
            "last_review": (
                item["last_review"].astimezone().strftime("%Y-%m-%d")
                if item["last_review"].tzinfo
                else item["last_review"].strftime("%Y-%m-%d")
            ),
        }
        for item in result.get("history_quests", [])
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
        "history_quests": history_quests,
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
async def post_quest_log(
    child_name: str = Form(...),
    quest_id: str = Form(...),
    role: str = Form(...),
    content: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """追加一条沟通日志。role 为 parent / teacher / ai 之一。支持 multipart/form-data 上传图片或短视频。"""
    valid_roles = {"parent", "teacher", "ai"}
    if role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"role 必须是 {valid_roles} 之一",
        )
    _, _, _, _, _, append_quest_log = _import_scheduler()

    file_url: Optional[str] = None
    file_type: Optional[str] = None

    if file and file.filename:
        uploads_dir = PROJECT_ROOT / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename).suffix or ""
        safe_ext = ext.lower() if ext else ".bin"
        unique_name = f"{uuid.uuid4().hex}{safe_ext}"
        dest_path = uploads_dir / unique_name
        try:
            contents = await file.read()
            dest_path.write_bytes(contents)
            file_url = f"/uploads/{unique_name}"
            file_type = file.content_type or "application/octet-stream"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")

    try:
        append_quest_log(
            child_name=child_name,
            quest_id=quest_id,
            role=role,
            content=content,
            file_url=file_url,
            file_type=file_type,
        )
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
