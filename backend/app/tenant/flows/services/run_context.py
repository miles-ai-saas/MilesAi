"""Flow 运行上下文装配：为画布节点注入模型解析与用量回调。

画布 LLM 节点不再自行查询/解析模型（见 ``llm_nodes.llm_call``），改由运行入口
（Agent 对话 / 工作台调试）通过本模块构造的 ``resolve_model`` 回调注入
``RunContext``；回调自开会话按 ``model_config_id`` 解析可用模型（合并 BYOK）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import select

from app.common.exceptions import BadRequestError
from app.infra.db import AsyncSessionLocal
from app.models.model import ModelConfig
from app.tenant.models.services.model_resolve import resolve_model_for_invoke


def make_flow_model_resolver(tenant_id: UUID) -> Callable[[str], Awaitable[ModelConfig]]:
    """构造按 ``model_config_id`` 解析可用模型的回调（自开会话，合并 BYOK）。"""

    async def _resolve(model_id: str) -> ModelConfig:
        async with AsyncSessionLocal() as db:
            model = (
                await db.execute(
                    select(ModelConfig).where(
                        ModelConfig.id == UUID(model_id),
                        ModelConfig.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if not model:
                raise BadRequestError("模型配置不存在或已禁用")
            return await resolve_model_for_invoke(db, model, tenant_id)

    return _resolve
