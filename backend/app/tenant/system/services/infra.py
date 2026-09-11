"""部署级基础设施只读状态与连接探测。"""

from app.core.service import BaseService
from app.tenant.system.schemas.infra import (
    InfraComponentStatusOut,
    InfraStatusOut,
    InfraTestConnectionOut,
)
from app.core.utils.health_checks import (
    COMPONENT_IDS,
    collect_infra_status,
    probe_components,
)


class InfraService(BaseService):
    """L1 部署基础设施：只读展示 + 连接测试（不写配置）。"""

    async def get_status(self) -> InfraStatusOut:
        """聚合各组件 probe 结果与 settings_preview。"""
        data = await collect_infra_status()
        return InfraStatusOut(
            healthy=data["healthy"],
            status=data["status"],
            components=[InfraComponentStatusOut.model_validate(c) for c in data["components"]],
            settings_preview=data["settings_preview"],
        )

    async def test_connection(self, components: list[str] | None = None) -> InfraTestConnectionOut:
        """按需探测指定组件；未知 id 标记为 skipped。"""
        ids = components if components else list(COMPONENT_IDS)
        unknown = [c for c in ids if c not in COMPONENT_IDS]
        results = [InfraComponentStatusOut.model_validate(r) for r in await probe_components(ids)]
        for name in unknown:
            results.append(
                InfraComponentStatusOut(
                    id=name,
                    label=name,
                    status="skipped",
                    message="未知组件",
                )
            )
        return InfraTestConnectionOut(results=results)
