from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.common.exceptions import BadRequestError
from app.core.llm_client import chat_completion
from app.flow_runtime.types import RunContext
from app.models.model import ModelConfig


async def llm_call(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
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

    temperature = float(node_data.get("temperature") or 0.7)
    messages = [{"role": "user", "content": prompt}]
    return await chat_completion(model, messages, temperature=temperature)
