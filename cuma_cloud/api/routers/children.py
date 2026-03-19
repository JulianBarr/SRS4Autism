"""儿童档案路由：受 ABAC 保护的资源访问。"""

from fastapi import APIRouter, Depends

from cuma_cloud.api.dependencies import verify_child_access
from cuma_cloud.models import ChildProfile

router = APIRouter(tags=["Children"])


@router.get("/children/{child_id}")
async def get_child(child: ChildProfile = Depends(verify_child_access)) -> dict:
    """
    获取儿童档案（id、name）。
    通过 verify_child_access 注入，鉴权通过后返回。
    """
    return {"id": child.id, "name": child.name}
