from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cuma_cloud.core.database import get_db
from cuma_cloud.models import ChildProfile, IepCommunicationLog, IepAiDraft, User, RoleEnum
from cuma_cloud.api.dependencies import get_current_user_abac
from cuma_cloud.api.schemas import PendingDraftResponse, ApproveDraftRequest

router = APIRouter(prefix="/teacher/drafts", tags=["Teacher Drafts"])

@router.get("/pending", response_model=list[PendingDraftResponse])
async def get_pending_drafts(
    current_user: User = Depends(get_current_user_abac),
    db: AsyncSession = Depends(get_db)
):
    """
    拉取待审批列表。
    查询 IepAiDraft 表中 status == 'PENDING' 的记录。
    返回 draft id, 内容, 关联的儿童名字, 以及触发此草稿的家长原始发言。
    """
    stmt = (
        select(
            IepAiDraft.id,
            IepAiDraft.draft_content,
            IepAiDraft.created_at,
            ChildProfile.name.label("child_name"),
            IepCommunicationLog.content.label("parent_log_content")
        )
        .join(ChildProfile, IepAiDraft.child_id == ChildProfile.id)
        .join(IepCommunicationLog, IepAiDraft.parent_log_id == IepCommunicationLog.id)
        .where(IepAiDraft.status == "PENDING")
        .order_by(IepAiDraft.created_at.desc())
    )

    # 权限控制：老师只能看自己负责的学生，机构管理员看本机构的学生
    if current_user.role == RoleEnum.TEACHER:
        stmt = stmt.where(ChildProfile.assigned_teacher_id == current_user.id)
    elif current_user.role == RoleEnum.QCQ_ADMIN:
        stmt = stmt.where(ChildProfile.institution_id == current_user.institution_id)
    elif current_user.role == RoleEnum.PARENT:
        # 家长不能审批草稿
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问待审批草稿")

    result = await db.execute(stmt)
    
    drafts = []
    for row in result:
        drafts.append(
            PendingDraftResponse(
                id=row.id,
                draft_content=row.draft_content,
                child_name=row.child_name,
                parent_log_content=row.parent_log_content,
                created_at=row.created_at
            )
        )
        
    return drafts

@router.post("/{draft_id}/approve")
async def approve_draft(
    draft_id: int,
    request: ApproveDraftRequest,
    current_user: User = Depends(get_current_user_abac),
    db: AsyncSession = Depends(get_db)
):
    """
    审批并发送草稿。
    将草稿状态更新为 APPROVED，并使用 edited_content 新建一条 IepCommunicationLog，
    使得家长端能看到这条最终回复。
    """
    # 权限检查放宽到查找 draft 阶段
    stmt = select(IepAiDraft).where(IepAiDraft.id == draft_id)
    result = await db.execute(stmt)
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="草稿不存在")
        
    if draft.status != "PENDING":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该草稿已被处理")

    # 检查当前用户是否有权限处理该儿童的数据
    child_stmt = select(ChildProfile).where(ChildProfile.id == draft.child_id)
    child_result = await db.execute(child_stmt)
    child = child_result.scalar_one_or_none()
    
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联儿童不存在")

    if current_user.role == RoleEnum.TEACHER and child.assigned_teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权审批该儿童的草稿")
    elif current_user.role == RoleEnum.QCQ_ADMIN and child.institution_id != current_user.institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权审批该儿童的草稿")
    elif current_user.role == RoleEnum.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="家长无权审批草稿")

    # 1. 更新草稿状态
    draft.status = "APPROVED"

    # 2. 新建 IEP 沟通记录
    new_log = IepCommunicationLog(
        child_id=draft.child_id,
        sender_id=current_user.id,
        content=request.edited_content
    )
    db.add(new_log)
    
    # 3. 提交事务
    await db.commit()
    
    return {"status": "success", "message": "草稿已审批并发送"}
