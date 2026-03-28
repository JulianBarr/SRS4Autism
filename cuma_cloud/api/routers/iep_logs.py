from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cuma_cloud.core.database import get_db
from cuma_cloud.models import ChildProfile, IepCommunicationLog, User
from cuma_cloud.api.dependencies import verify_child_access, get_current_user_abac
from cuma_cloud.api.schemas import IepLogCreate, IepLogResponse
from cuma_cloud.services.ai_agent import trigger_ai_assistant

router = APIRouter(prefix="/children", tags=["IEP Logs"])

@router.get("/{child_id}/logs", response_model=list[IepLogResponse])
async def get_iep_logs(
    child_id: int,
    child: ChildProfile = Depends(verify_child_access),
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定儿童的 IEP 沟通记录。
    依赖 verify_child_access 拦截器，确保只有授权的老师/家长/AI能访问。
    """
    stmt = (
        select(IepCommunicationLog, User.role.label("sender_role"))
        .join(User, IepCommunicationLog.sender_id == User.id)
        .where(IepCommunicationLog.child_id == child_id)
        .order_by(IepCommunicationLog.created_at.desc())
    )
    result = await db.execute(stmt)
    
    logs = []
    for log, role in result:
        log_data = IepLogResponse.model_validate(log)
        log_data.sender_role = role.value if hasattr(role, 'value') else str(role)
        logs.append(log_data)
        
    return logs

@router.post("/{child_id}/logs")
async def create_iep_log(
    child_id: int,
    log_in: IepLogCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_abac),
    child: ChildProfile = Depends(verify_child_access),
    db: AsyncSession = Depends(get_db)
):
    """
    发送一条 IEP 沟通记录。
    如果包含 "@AI"、"@助教" 或 "@超级助教"，将触发后台 AI 任务回复。
    依赖 verify_child_access 进行鉴权。
    """
    new_log = IepCommunicationLog(
        child_id=child_id,
        sender_id=current_user.id,
        content=log_in.content
    )
    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)
    
    # 获取创建后的信息并附加 role
    response_data = IepLogResponse.model_validate(new_log)
    response_data.sender_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    
    # 检测触发 AI 关键词
    trigger_keywords = ["@AI", "@助教", "@超级助教"]
    if any(keyword in log_in.content for keyword in trigger_keywords):
        background_tasks.add_task(trigger_ai_assistant, child_id, new_log.id)
        return {
            "status": "draft_created",
            "message": "已通知老师审核",
            "log": response_data
        }
    
    return response_data
