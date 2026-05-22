"""聚合 DB / Redis / 向量库 / 对象存储健康探测。"""

from app.utils.health_checks import collect_health_status
from app.common.response import fail, ok
from app.common.schema import ApiResponse


class HealthService:
    @staticmethod
    async def check() -> ApiResponse[dict]:
        result = await collect_health_status()
        data = {"status": result["status"], "components": result["components"]}
        if result["healthy"]:
            return ok(data=data)
        return fail(message="degraded", code=1, data=data)
