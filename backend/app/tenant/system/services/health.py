"""聚合 DB / Redis / 向量库 / 对象存储健康探测。"""

from app.utils.health_checks import collect_health_status
from app.common.response import fail, ok
from app.common.schema import ApiResponse


class HealthService:
    """/health 无鉴权探测；components 含 postgres/redis/vector_store/object_storage。"""

    @staticmethod
    async def check() -> ApiResponse[dict]:
        """healthy 时 code=0；降级时 code=1 且 data 仍带组件明细。"""
        result = await collect_health_status()
        data = {"status": result["status"], "components": result["components"]}
        if result["healthy"]:
            return ok(data=data)
        return fail(message="degraded", code=1, data=data)
