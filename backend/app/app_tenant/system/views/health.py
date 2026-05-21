from fastapi import APIRouter

from app.common.schema import ApiResponse
from app.app_tenant.system.services.health import HealthService

router = APIRouter()


@router.get("/health")
async def health() -> ApiResponse[dict]:
    return await HealthService.check()
