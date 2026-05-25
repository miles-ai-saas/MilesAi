"""画布 LLM 节点：解析 ModelConfig 后走 integrations.langchain.chat_models。

未配置 model_config_id 时返回占位文本（仅展示检索上下文），不调用远程 API。
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import AsyncSessionLocal
from app.common.exceptions import BadRequestError
from app.integrations.langchain.chat_models import ainvoke_chat
from app.tenant.models.services.model_resolve import resolve_model_for_invoke
from app.flow_runtime.types import RunContext
from app.models.model import ModelConfig


async def llm_call(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """画布 LLMCall：resolve 模型后 ainvoke_chat。"""
    prompt = str(inputs.get("prompt") or inputs.get("input") or "")
    if not prompt:
        raise BadRequestError("LLM 节点缺少输入")
    model_id = node_data.get("model_config_id") or ctx.model_config_id
    if not model_id:
        return f"[未配置模型，仅返回检索上下文]\n\n{prompt}"

    async with AsyncSessionLocal() as db:
        model = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == model_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not model:
            raise BadRequestError("模型配置不存在或已禁用")
        model = await resolve_model_for_invoke(db, model, UUID(str(ctx.tenant_id)))
        temperature = float(node_data.get("temperature") or 0.7)
        messages = [{"role": "user", "content": prompt}]
        return await ainvoke_chat(model, messages, temperature=temperature)
