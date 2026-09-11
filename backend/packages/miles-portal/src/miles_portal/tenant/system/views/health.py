"""依赖健康检查 HTTP API（DB/Redis/向量库/对象存储）。"""

from fastapi import APIRouter

from miles_common.schema import ApiResponse
from miles_portal.tenant.system.services.health import HealthService

router = APIRouter()


@router.get("/health")
async def health() -> ApiResponse[dict]:
    return await HealthService.check()
