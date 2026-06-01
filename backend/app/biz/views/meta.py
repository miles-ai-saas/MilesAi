"""业务中心元数据 HTTP API，路由前缀 `/biz/meta`。

提供业务模块的枚举元数据，包括服务线、状态、阶段等下拉选项值。
"""

from fastapi import APIRouter

from app.common.response import ok
from app.common.schema import ApiResponse
from app.biz.schemas.meta import BizMetaOut
from app.biz.services.meta import BizMetaService

router = APIRouter()


@router.get("", response_model=ApiResponse[BizMetaOut])
async def get_biz_meta():
    """获取业务中心枚举元数据，如服务线、状态、阶段等。"""
    return ok(BizMetaService.get_meta())
