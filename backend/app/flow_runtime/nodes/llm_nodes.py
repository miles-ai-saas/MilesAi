"""
画布 LLM 节点（``LLMCall``）。

典型上游：``PromptTemplate`` 输出已嵌入检索结果的 prompt。
``model_config_id`` 优先取节点配置，否则 ``RunContext.model_config_id``（Agent 对话注入）。

模型解析由运行入口注入的 ``RunContext.resolve_model`` 回调完成（见
``tenant.flows.services.run_context.make_flow_model_resolver``）；节点不再自行查询。
未配置模型或回调缺失时返回占位字符串 / 抛 ``BadRequestError``，便于调试与兜底。
支持 ``RunContext.media`` 附图（vision，base64 data URL）。
"""

from typing import Any

from app.common.exceptions import BadRequestError
from app.common.schemas.media import MediaRefIn
from app.flow_runtime.context_utils import media_refs_from_run, tenant_context_from_run
from app.flow_runtime.types import RunContext
from app.infra.db import AsyncSessionLocal
from app.integrations.chat.multimodal import build_user_message, resolve_media_refs
from app.integrations.langchain.chat_models import ainvoke_chat


async def llm_call(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """画布 LLMCall：经 ``ctx.resolve_model`` 解析模型后 ainvoke_chat（可选多模态 user content）。"""
    prompt = str(inputs.get("prompt") or inputs.get("input") or "").strip()
    include_run_media = node_data.get("include_run_media", True)
    media_refs: list[MediaRefIn] = []
    if include_run_media:
        media_refs = media_refs_from_run(ctx)

    if not prompt and not media_refs:
        raise BadRequestError("LLM 节点缺少输入")

    model_id = node_data.get("model_config_id") or ctx.model_config_id
    if not model_id:
        suffix = "\n\n[附图已忽略：未配置模型]" if media_refs else ""
        return f"[未配置模型，仅返回检索上下文]\n\n{prompt or '（无文本）'}{suffix}"

    if ctx.resolve_model is None:
        raise BadRequestError("运行上下文未提供模型解析回调")
    model = await ctx.resolve_model(str(model_id))

    temperature = float(node_data.get("temperature") or 0.7)
    max_tokens_raw = node_data.get("max_tokens")
    max_tokens = int(max_tokens_raw) if max_tokens_raw is not None else 2048

    tenant_ctx = tenant_context_from_run(ctx)
    max_media = int((ctx.agent_config or {}).get("max_media_per_turn", 10))
    media_parts: list[dict[str, Any]] = []
    if media_refs:
        async with AsyncSessionLocal() as db:
            media_parts = await resolve_media_refs(db, tenant_ctx, media_refs, max_count=max_media)

    user_msg = build_user_message(
        query=prompt or "请根据附图回答。",
        media_parts=media_parts,
    )
    messages: list[dict[str, Any]] = []
    system = (ctx.system_prompt or "").strip()
    if system:
        messages.append({"role": "system", "content": system})
    messages.append(user_msg)

    return await ainvoke_chat(
        model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        usage_sink=ctx.usage_sink,
    )
